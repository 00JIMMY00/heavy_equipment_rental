<script setup>
import { computed, ref, watch } from 'vue'

const sourceEvents = ref([])
const resources = ref([])
const selected = ref(null)
const loading = ref(false)
const error = ref('')
const view = ref('Month')
const anchor = ref(new Date())
const search = ref('')
const enabled = ref({ reservation: true, project: true, timesheet: true })
let requestNumber = 0

const categories = [
  { key: 'reservation', label: 'Reservations', color: '#3d76dd' },
  { key: 'project', label: 'Projects', color: '#8355cf' },
  { key: 'timesheet', label: 'Timesheets', color: '#218e70' },
]
const counts = computed(() => Object.fromEntries(categories.map(item => [item.key, sourceEvents.value.filter(event => event.type === item.key).length])))
const shown = computed(() => sourceEvents.value.filter(event =>
  enabled.value[event.type] && `${event.title} ${event.participant || ''} ${event.venue || ''} ${event.status || ''}`.toLowerCase().includes(search.value.trim().toLowerCase())
))
const dayWidth = computed(() => view.value === 'Week' ? 96 : 42)
const rangeStart = computed(() => {
  const date = new Date(anchor.value.getFullYear(), anchor.value.getMonth(), anchor.value.getDate())
  if (view.value === 'Month') return new Date(date.getFullYear(), date.getMonth(), 1)
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7))
  return date
})
const days = computed(() => {
  const count = view.value === 'Week' ? 7 : new Date(rangeStart.value.getFullYear(), rangeStart.value.getMonth() + 1, 0).getDate()
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(rangeStart.value)
    date.setDate(date.getDate() + index)
    return { key: formatDate(date), day: date.getDate(), weekday: date.toLocaleDateString(undefined, { weekday: 'short' }), isToday: formatDate(date) === formatDate(new Date()), isWeekend: [5, 6].includes(date.getDay()) }
  })
})
const rangeEnd = computed(() => days.value.at(-1)?.key)
const title = computed(() => view.value === 'Month'
  ? rangeStart.value.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  : `${rangeStart.value.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} – ${new Date(`${rangeEnd.value}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`)
const totalWidth = computed(() => dayWidth.value * days.value.length)
const lanes = computed(() => [...resources.value].sort((a, b) => a.group.localeCompare(b.group) || a.title.localeCompare(b.title, undefined, { numeric: true })).map(resource => {
  const matches = shown.value.filter(event => event.type === 'project'
    ? resource.id === `project:${event.docname}`
    : resource.id === `crane:${event.crane}` || resource.id === `project:${event.project}`)
  const segments = matches.map(event => {
    const lastDay = !event.isFullDay && event.toTime === '00:00' && event.toDate > event.fromDate ? shiftDate(event.toDate, -1) : event.toDate
    const first = Math.max(0, days.value.findIndex(day => day.key >= event.fromDate))
    const last = days.value.findLastIndex(day => day.key <= lastDay)
    if (last < first || last < 0 || event.fromDate > rangeEnd.value || lastDay < days.value[0].key) return null
    return { event, first, last }
  }).filter(Boolean).sort((a, b) => a.first - b.first || b.last - a.last)
  const occupied = []
  for (const segment of segments) {
    let lane = occupied.findIndex(end => end < segment.first)
    if (lane < 0) lane = occupied.length
    occupied[lane] = segment.last
    segment.lane = lane
  }
  return { ...resource, segments, height: Math.max(52, 17 + occupied.length * 27) }
}))
const groups = computed(() => [
  { name: 'Fleet', rows: lanes.value.filter(row => row.group === 'Fleet') },
  { name: 'Projects', rows: lanes.value.filter(row => row.group === 'Projects') },
].filter(group => group.rows.length))

function formatDate(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }
function shiftDate(value, amount) {
  const date = new Date(`${value}T12:00:00`)
  date.setDate(date.getDate() + amount)
  return formatDate(date)
}
function navigate(amount) {
  const date = new Date(anchor.value)
  if (view.value === 'Month') date.setMonth(date.getMonth() + amount, 1)
  else date.setDate(date.getDate() + amount * 7)
  anchor.value = date
}
function changeView(next) { view.value = next }
async function loadRange() {
  const request = ++requestNumber
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({ start_date: days.value[0].key, end_date: rangeEnd.value })
    const response = await fetch(`/api/method/heavy_equipment_rental.calendar.get_resource_calendar_data?${params}`, { credentials: 'same-origin' })
    const payload = await response.json()
    if (!response.ok || payload.exc) throw new Error('Unable to load the resource timeline.')
    if (request === requestNumber) {
      sourceEvents.value = payload.message?.events || []
      resources.value = payload.message?.resources || []
    }
  } catch (reason) {
    if (request === requestNumber) error.value = reason.message || 'Unable to load the resource timeline.'
  } finally {
    if (request === requestNumber) loading.value = false
  }
}
watch(() => `${days.value[0].key}:${rangeEnd.value}`, loadRange, { immediate: true })
function documentUrl(event) { return `/app/${event.doctype.toLowerCase().replaceAll(' ', '-')}/${encodeURIComponent(event.docname)}` }
function dateLabel(event) {
  const date = value => new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const dates = event.fromDate === event.toDate ? date(event.fromDate) : `${date(event.fromDate)} – ${date(event.toDate)}`
  return event.isFullDay ? dates : `${dates} · ${event.fromTime}–${event.toTime}`
}
</script>

<template>
  <div class="timeline-page">
    <header class="timeline-hero">
      <div><span class="timeline-kicker">FLEET OPERATIONS / COMPARISON VIEW</span><h1>Resource timeline</h1><p>See each crane and project on its own row, with bookings and work aligned to time.</p>
        <div class="timeline-links"><a href="/rental-calendar">← Standard calendar</a><a href="/app/crane-operations">Crane Operations ↗</a></div>
      </div>
      <div class="timeline-hero-stat"><strong>{{ resources.length }}</strong><span>resources in view</span></div>
    </header>
    <section class="timeline-summary" aria-label="Timeline summary">
      <div v-for="item in categories" :key="item.key" class="timeline-summary-card" :style="{ '--tone': item.color }"><i></i><strong>{{ counts[item.key] || 0 }}</strong><span>{{ item.label }}</span></div>
      <div class="timeline-summary-card resources-card"><i></i><strong>{{ resources.filter(item => item.group === 'Fleet').length }}</strong><span>Fleet rows</span></div>
    </section>
    <main class="timeline-panel">
      <div class="timeline-head"><div><span class="timeline-overline">RESOURCE SCHEDULE</span><h2>{{ title }}</h2><p>Project rows show the full project window. Fleet rows show crane bookings and recorded work.</p></div>
        <div class="timeline-nav"><button type="button" @click="navigate(-1)" aria-label="Previous period">‹</button><button type="button" @click="anchor = new Date()">Today</button><button type="button" @click="navigate(1)" aria-label="Next period">›</button></div>
      </div>
      <div class="timeline-toolbar"><div class="timeline-filters"><button v-for="item in categories" :key="item.key" type="button" :class="{ off: !enabled[item.key] }" :aria-pressed="enabled[item.key]" @click="enabled[item.key] = !enabled[item.key]"><i :style="{ background: item.color }"></i>{{ item.label }}</button></div>
        <div class="timeline-tools"><label class="timeline-search"><span>⌕</span><input v-model="search" type="search" placeholder="Search events" aria-label="Search timeline events" /></label><div class="timeline-switch"><button type="button" :class="{ active: view === 'Week' }" @click="changeView('Week')">Week</button><button type="button" :class="{ active: view === 'Month' }" @click="changeView('Month')">Month</button></div></div>
      </div>
      <div v-if="error" class="timeline-error" role="alert">{{ error }} <button type="button" @click="loadRange">Try again</button></div>
      <div class="timeline-scroll" :aria-busy="loading">
        <div class="timeline-grid" :style="{ '--day-width': `${dayWidth}px`, '--track-width': `${totalWidth}px` }">
          <div class="timeline-row timeline-header"><div class="timeline-resource-head">RESOURCE <span>DETAILS</span></div><div class="timeline-track timeline-dates"><div v-for="day in days" :key="day.key" class="timeline-day" :class="{ today: day.isToday, weekend: day.isWeekend }"><strong>{{ day.day }}</strong><small>{{ day.weekday }}</small></div></div></div>
          <template v-for="group in groups" :key="group.name"><div class="timeline-row timeline-group"><div class="timeline-group-name">{{ group.name }} <small>{{ group.rows.length }}</small></div><div class="timeline-track"></div></div>
            <div v-for="row in group.rows" :key="row.id" class="timeline-row timeline-data-row" :style="{ height: `${row.height}px` }"><div class="timeline-resource"><strong :title="row.title">{{ row.title }}</strong><small :title="row.detail">{{ row.detail }}</small></div><div class="timeline-track timeline-lane"><span v-for="day in days" :key="day.key" class="timeline-cell" :class="{ today: day.isToday, weekend: day.isWeekend }"></span><button v-for="segment in row.segments" :key="segment.event.id" type="button" class="timeline-bar" :class="[segment.event.type, { draft: segment.event.isDraft, cancelled: segment.event.isDeclined }]" :style="{ left: `${segment.first * dayWidth + 3}px`, width: `${(segment.last - segment.first + 1) * dayWidth - 6}px`, top: `${10 + segment.lane * 27}px` }" :title="`${segment.event.title} · ${segment.event.status}`" @click="selected = segment.event">{{ segment.event.title }}</button></div></div>
          </template>
          <div v-if="!groups.length && !loading" class="timeline-empty">No resources are visible for this period.</div>
        </div>
      </div>
      <div class="timeline-footer"><span><i class="footline today"></i> Today</span><span><i class="footline reservation"></i> Reservation</span><span><i class="footline project"></i> Project</span><span><i class="footline timesheet"></i> Timesheet work</span><span class="timeline-tip">Select a bar for details · {{ loading ? 'Loading…' : `${shown.length} events shown` }}</span></div>
    </main>
    <div v-if="selected" class="timeline-overlay" @click.self="selected = null"><section class="timeline-detail" role="dialog" aria-modal="true" aria-label="Event details"><button class="timeline-close" type="button" aria-label="Close details" @click="selected = null">×</button><span class="timeline-detail-kind" :class="selected.type">{{ selected.type }}</span><h3>{{ selected.title }}</h3><span class="timeline-detail-status">{{ selected.status }}</span><dl><div><dt>When</dt><dd>{{ dateLabel(selected) }}</dd></div><div v-if="selected.participant"><dt>{{ selected.type === 'timesheet' && !selected.isFullDay ? 'Driver' : selected.type === 'project' ? 'Customer' : 'Crane / driver' }}</dt><dd>{{ selected.participant }}</dd></div><div v-if="selected.venue"><dt>Project / customer</dt><dd>{{ selected.venue }}</dd></div></dl><a :href="documentUrl(selected)">Open {{ selected.doctype }} ↗</a></section></div>
  </div>
</template>
