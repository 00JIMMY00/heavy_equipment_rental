<script setup>
import { computed, ref, watch } from 'vue'
import SearchSelect from './SearchSelect.vue'

const pageParams = new URLSearchParams(window.location.search)
const requestedFrom = pageParams.get('from')
const requestedTo = pageParams.get('to')
const requestedSpan = Math.round((Date.parse(`${requestedTo}T12:00:00Z`) - Date.parse(`${requestedFrom}T12:00:00Z`)) / 86400000)
const initialRange = /^\d{4}-\d{2}-\d{2}$/.test(requestedFrom || '') && /^\d{4}-\d{2}-\d{2}$/.test(requestedTo || '') && requestedSpan >= 0 && requestedSpan <= 120
  ? { start: requestedFrom, end: requestedTo } : null
const sourceEvents = ref([])
const selected = ref(null)
const loading = ref(false)
const error = ref('')
const view = ref(initialRange ? 'Custom' : 'Month')
const groupBy = ref('Project')
const anchor = ref(new Date())
const customRange = ref(initialRange)
const fromDate = ref('')
const toDate = ref('')
const rangeError = ref('')
const search = ref('')
const projectFilter = ref(pageParams.get('project') || '')
const craneFilter = ref(pageParams.get('crane') || '')
const enabled = ref({ reservation: true, project: true, timesheet: true, maintenance: true })
let requestNumber = 0

const categories = [
  { key: 'reservation', label: 'Reservations', color: '#1265d8' },
  { key: 'project', label: 'Projects', color: '#23487d' },
  { key: 'timesheet', label: 'Timesheets', color: '#22a4e8' },
  { key: 'maintenance', label: 'Maintenance', color: '#d98532' },
]
const projectCranes = computed(() => {
  const result = new Map()
  for (const event of sourceEvents.value) {
    if (!event.project || !event.crane) continue
    if (!result.has(event.project)) result.set(event.project, new Set())
    result.get(event.project).add(event.crane)
  }
  return result
})
const projectOptions = computed(() => {
  const names = new Map()
  for (const event of sourceEvents.value) {
    if (event.project) names.set(event.project, event.project_name || names.get(event.project) || event.project)
  }
  if (projectFilter.value && !names.has(projectFilter.value)) names.set(projectFilter.value, projectFilter.value)
  return [...names].map(([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }))
})
const craneOptions = computed(() => {
  const names = new Map()
  for (const event of sourceEvents.value) {
    if (event.crane) names.set(event.crane, event.crane_name || names.get(event.crane) || event.crane)
  }
  if (craneFilter.value && !names.has(craneFilter.value)) names.set(craneFilter.value, craneFilter.value)
  return [...names].map(([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }))
})
const recordFilteredEvents = computed(() => sourceEvents.value.filter(event =>
  (!projectFilter.value || event.project === projectFilter.value) &&
  (!craneFilter.value || event.crane === craneFilter.value ||
    (!event.crane && projectCranes.value.get(event.project)?.has(craneFilter.value)))
))
const counts = computed(() => Object.fromEntries(categories.map(item => [
  item.key,
  new Set(recordFilteredEvents.value.filter(event => event.type === item.key).map(event => ['timesheet', 'maintenance'].includes(event.type) ? event.docname : event.id)).size,
])))
const shown = computed(() => recordFilteredEvents.value.filter(event =>
  enabled.value[event.type] && `${event.title} ${event.participant || ''} ${event.venue || ''} ${event.status || ''}`.toLowerCase().includes(search.value.trim().toLowerCase())
))
const dayWidth = computed(() => view.value === 'Week' || (view.value === 'Custom' && days.value.length <= 14) ? 96 : 42)
const rangeStart = computed(() => {
  if (view.value === 'Custom' && customRange.value) return new Date(`${customRange.value.start}T12:00:00`)
  const date = new Date(anchor.value.getFullYear(), anchor.value.getMonth(), anchor.value.getDate())
  if (view.value === 'Month') return new Date(date.getFullYear(), date.getMonth(), 1)
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7))
  return date
})
const days = computed(() => {
  const count = view.value === 'Custom' && customRange.value
    ? Math.round((Date.parse(`${customRange.value.end}T12:00:00Z`) - Date.parse(`${customRange.value.start}T12:00:00Z`)) / 86400000) + 1
    : view.value === 'Week' ? 7 : new Date(rangeStart.value.getFullYear(), rangeStart.value.getMonth() + 1, 0).getDate()
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
const records = computed(() => {
  const result = new Map()
  const projectNames = new Map()
  const craneNames = new Map()
  for (const event of sourceEvents.value) {
    if (event.project && event.project_name) projectNames.set(event.project, event.project_name)
    if (event.crane && event.crane_name) craneNames.set(event.crane, event.crane_name)
  }
  for (const event of shown.value) {
    let keys
    if (groupBy.value === 'Project') {
      keys = event.project ? [`project:${event.project}`] : event.crane ? [`unassigned-crane:${event.crane}`] : ['unassigned']
    } else {
      const cranes = event.crane ? [event.crane] : [...(projectCranes.value.get(event.project) || [])]
      keys = cranes.length ? cranes.map(crane => `crane:${crane}`) : event.project ? [`unassigned-project:${event.project}`] : ['unassigned']
    }
    for (const id of keys) {
      if (!result.has(id)) {
        const [kind, value] = id.split(':')
        const isProject = kind === 'project' || kind === 'unassigned-project'
        const title = kind === 'project' ? (projectNames.get(value) || value)
          : kind === 'crane' || kind === 'unassigned-crane' ? (craneNames.get(value) || value)
            : 'Unassigned'
        const detail = kind === 'project' ? [value, sourceEvents.value.find(item => item.type === 'project' && item.project === value)?.participant].filter(Boolean).join(' · ')
          : kind === 'unassigned-crane' ? 'No linked project'
            : kind === 'unassigned-project' ? `No linked crane · ${projectNames.get(value) || value}`
              : isProject ? value : kind === 'crane' ? value : 'No linked project or crane'
        result.set(id, { id, title, detail, events: [] })
      }
      result.get(id).events.push(event)
    }
  }
  return [...result.values()].sort((a, b) =>
    a.title.localeCompare(b.title, undefined, { numeric: true }))
})
const lanes = computed(() => records.value.map(record => {
  const segments = record.events.map(event => {
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
  return { ...record, segments, height: Math.max(52, 17 + occupied.length * 27) }
}))

function formatDate(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }
function shiftDate(value, amount) {
  const date = new Date(`${value}T12:00:00`)
  date.setDate(date.getDate() + amount)
  return formatDate(date)
}
function navigate(amount) {
  if (view.value === 'Custom' && customRange.value) {
    const span = days.value.length
    customRange.value = {
      start: shiftDate(customRange.value.start, amount * span),
      end: shiftDate(customRange.value.end, amount * span),
    }
    return
  }
  const date = new Date(anchor.value)
  if (view.value === 'Month') date.setMonth(date.getMonth() + amount, 1)
  else date.setDate(date.getDate() + amount * 7)
  anchor.value = date
}
function changeView(next) { view.value = next }
function goToday() {
  if (view.value === 'Custom' && customRange.value) {
    const today = formatDate(new Date())
    customRange.value = { start: today, end: shiftDate(today, days.value.length - 1) }
  } else anchor.value = new Date()
}
function applyRange() {
  rangeError.value = ''
  if (!fromDate.value || !toDate.value) {
    rangeError.value = 'Choose both a From and a To date.'
    return
  }
  const span = Math.round((Date.parse(`${toDate.value}T12:00:00Z`) - Date.parse(`${fromDate.value}T12:00:00Z`)) / 86400000)
  if (span < 0) rangeError.value = 'The To date must be on or after the From date.'
  else if (span > 120) rangeError.value = 'Choose a range of at most 120 days.'
  if (rangeError.value) return
  customRange.value = { start: fromDate.value, end: toDate.value }
  view.value = 'Custom'
}
watch(() => [days.value[0].key, rangeEnd.value], ([start, end]) => {
  fromDate.value = start
  toDate.value = end
  rangeError.value = ''
}, { immediate: true })
async function loadRange() {
  const request = ++requestNumber
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({ start_date: days.value[0].key, end_date: rangeEnd.value })
    const response = await fetch(`/api/method/heavy_equipment_rental.calendar.get_calendar_events?${params}`, { credentials: 'same-origin' })
    const payload = await response.json()
    if (!response.ok || payload.exc) throw new Error('Unable to load the resource timeline.')
    if (request === requestNumber) {
      sourceEvents.value = payload.message || []
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
      <div><span class="timeline-kicker"><img class="hero-mark" :src="'/assets/heavy_equipment_rental/branding/ar-monogram-classic.png'" alt="AR logo" /> FLEET OPERATIONS / COMPARISON VIEW</span><h1>Operations timeline</h1><p>See the records you select, with their related equipment and people beside each date.</p>
        <div class="timeline-links"><a href="/rental-calendar">← Standard calendar</a><a href="/app/crane-operations">Crane Operations ↗</a></div>
      </div>
      <div class="timeline-hero-stat"><strong>{{ records.length }}</strong><span>{{ groupBy.toLowerCase() }} rows in view</span></div>
    </header>
    <section class="timeline-summary" aria-label="Timeline summary">
      <div v-for="item in categories" :key="item.key" class="timeline-summary-card" :style="{ '--tone': item.color }"><i></i><strong>{{ counts[item.key] || 0 }}</strong><span>{{ item.label }}</span></div>
    </section>
    <main class="timeline-panel">
      <div class="timeline-head"><div><span class="timeline-overline">OPERATIONS SCHEDULE</span><h2>{{ title }}</h2><p>Selected reservations, projects, timesheets, and maintenance share each {{ groupBy.toLowerCase() }} row.</p></div>
        <div class="timeline-nav"><button type="button" @click="navigate(-1)" aria-label="Previous period">‹</button><button type="button" @click="goToday">Today</button><button type="button" @click="navigate(1)" aria-label="Next period">›</button></div>
      </div>
      <div class="timeline-toolbar">
        <div class="timeline-category-row"><span class="timeline-control-label">Event types</span><div class="timeline-filters"><button v-for="item in categories" :key="item.key" type="button" :class="{ off: !enabled[item.key] }" :aria-pressed="enabled[item.key]" @click="enabled[item.key] = !enabled[item.key]"><i :style="{ background: item.color }"></i>{{ item.label }}</button></div>
          <div class="timeline-views"><div class="timeline-control-switch"><span class="timeline-control-label">Rows</span><div class="timeline-switch" aria-label="Group timeline rows"><button type="button" :class="{ active: groupBy === 'Project' }" :aria-pressed="groupBy === 'Project'" @click="groupBy = 'Project'">Project</button><button type="button" :class="{ active: groupBy === 'Crane' }" :aria-pressed="groupBy === 'Crane'" @click="groupBy = 'Crane'">Crane</button></div></div>
            <div class="timeline-control-switch"><span class="timeline-control-label">View</span><div class="timeline-switch" aria-label="Timeline period"><button type="button" :class="{ active: view === 'Week' }" @click="changeView('Week')">Week</button><button type="button" :class="{ active: view === 'Month' }" @click="changeView('Month')">Month</button><button v-if="customRange" type="button" :class="{ active: view === 'Custom' }" @click="changeView('Custom')">Custom</button></div></div></div>
        </div>
        <div class="timeline-control-row">
          <SearchSelect v-model="projectFilter" label="Project" placeholder="Search or choose project" :options="projectOptions" />
          <SearchSelect v-model="craneFilter" label="Crane" placeholder="Search or choose crane" :options="craneOptions" />
          <form class="timeline-inline-dates" @submit.prevent="applyRange"><label>From <input v-model="fromDate" type="date" aria-label="From date" required /></label><span aria-hidden="true">→</span><label>To <input v-model="toDate" type="date" aria-label="To date" required /></label><button type="submit">Show dates</button><span v-if="rangeError" class="timeline-range-error" role="alert">{{ rangeError }}</span></form>
          <label class="timeline-search"><span>⌕</span><input v-model="search" type="search" placeholder="Search events" aria-label="Search timeline events" /></label>
        </div>
      </div>
      <div v-if="error" class="timeline-error" role="alert">{{ error }} <button type="button" @click="loadRange">Try again</button></div>
      <div class="timeline-scroll" :aria-busy="loading">
        <div class="timeline-grid" :style="{ '--day-width': `${dayWidth}px`, '--track-width': `${totalWidth}px` }">
          <div class="timeline-row timeline-header"><div class="timeline-resource-head">{{ groupBy.toUpperCase() }} <span>RELATED DETAILS</span></div><div class="timeline-track timeline-dates"><div v-for="day in days" :key="day.key" class="timeline-day" :class="{ today: day.isToday, weekend: day.isWeekend }"><strong>{{ day.day }}</strong><small>{{ day.weekday }}</small></div></div></div>
          <div v-for="row in lanes" :key="row.id" class="timeline-row timeline-data-row" :style="{ height: `${row.height}px` }"><div class="timeline-resource"><strong :title="row.title">{{ row.title }}</strong><small :title="row.detail">{{ row.detail }}</small></div><div class="timeline-track timeline-lane"><span v-for="day in days" :key="day.key" class="timeline-cell" :class="{ today: day.isToday, weekend: day.isWeekend }"></span><button v-for="segment in row.segments" :key="segment.event.id" type="button" class="timeline-bar" :class="[segment.event.type, { draft: segment.event.isDraft, cancelled: segment.event.isDeclined }]" :style="{ left: `${segment.first * dayWidth + 3}px`, width: `${(segment.last - segment.first + 1) * dayWidth - 6}px`, top: `${10 + segment.lane * 27}px` }" :title="`${segment.event.title} · ${segment.event.status}`" @click="selected = segment.event">{{ segment.event.title }}</button></div></div>
          <div v-if="!lanes.length && !loading" class="timeline-empty">No matching activity. Change the project, crane, event type, dates, or search.</div>
        </div>
      </div>
      <div class="timeline-footer"><span><i class="footline today"></i> Today</span><span><i class="footline reservation"></i> Reservation</span><span><i class="footline project"></i> Project</span><span><i class="footline timesheet"></i> Timesheet work</span><span><i class="footline maintenance"></i> Maintenance</span><span class="timeline-tip">Select a bar for details · {{ loading ? 'Loading…' : `${shown.length} events across ${records.length} rows` }}</span></div>
    </main>
    <div v-if="selected" class="timeline-overlay" @click.self="selected = null"><section class="timeline-detail" role="dialog" aria-modal="true" aria-label="Event details"><button class="timeline-close" type="button" aria-label="Close details" @click="selected = null">×</button><span class="timeline-detail-kind" :class="selected.type">{{ selected.type }}{{ selected.phase ? ` · ${selected.phase}` : '' }}</span><h3>{{ selected.title }}</h3><span class="timeline-detail-status">{{ selected.status }}</span><dl><div><dt>When</dt><dd>{{ dateLabel(selected) }}</dd></div><div v-if="selected.participant"><dt>{{ selected.type === 'maintenance' ? 'Technician' : selected.type === 'timesheet' && !selected.isFullDay ? 'Driver' : selected.type === 'project' ? 'Customer' : 'Crane / driver' }}</dt><dd>{{ selected.participant }}</dd></div><div v-if="selected.venue"><dt>Project / customer</dt><dd>{{ selected.venue }}</dd></div></dl><a :href="documentUrl(selected)">Open {{ selected.doctype }} ↗</a></section></div>
  </div>
</template>
