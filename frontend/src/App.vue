<script setup>
import { computed, ref } from 'vue'
import { Calendar } from 'frappe-ui/experimental'
import { FrappeUIProvider } from 'frappe-ui'

const events = ref([])
const loading = ref(false)
const error = ref('')
const query = ref('')
const visible = ref({ reservation: true, project: true, timesheet: true })
const range = ref(null)
let requestNumber = 0

const categories = [
  { key: 'reservation', label: 'Reservations', color: '#3972df' },
  { key: 'project', label: 'Projects', color: '#8255ce' },
  { key: 'timesheet', label: 'Timesheets', color: '#219b75' },
]
const filteredEvents = computed(() => events.value.filter(event =>
  visible.value[event.type] &&
  `${event.title} ${event.participant || ''} ${event.venue || ''} ${event.status || ''}`
    .toLowerCase().includes(query.value.toLowerCase().trim())
))
const counts = computed(() => Object.fromEntries(categories.map(category => [
  category.key, events.value.filter(event => event.type === category.key).length,
])))
const visibleCount = computed(() => filteredEvents.value.length)
const rangeLabel = computed(() => {
  if (!range.value) return 'Loading your schedule'
  const format = value => new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  return `${format(range.value.startDate)} – ${format(range.value.endDate)}`
})

async function loadRange(nextRange = range.value) {
  if (!nextRange) return
  range.value = nextRange
  const request = ++requestNumber
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({ start_date: nextRange.startDate, end_date: nextRange.endDate })
    const response = await fetch(`/api/method/heavy_equipment_rental.calendar.get_calendar_events?${params}`, {
      credentials: 'same-origin',
    })
    const payload = await response.json()
    if (!response.ok || payload.exc) throw new Error(payload._server_messages ? 'Unable to load calendar events.' : (payload.message || 'Unable to load calendar events.'))
    if (request === requestNumber) events.value = payload.message || []
  } catch (reason) {
    if (request === requestNumber) error.value = reason.message || 'Unable to load calendar events.'
  } finally {
    if (request === requestNumber) loading.value = false
  }
}
function toggle(key) { visible.value[key] = !visible.value[key] }
function documentUrl(event) {
  return `/app/${event.doctype.toLowerCase().replaceAll(' ', '-')}/${encodeURIComponent(event.docname)}`
}
function dateLabel(event) {
  const format = date => new Date(`${date}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  const dates = event.fromDate === event.toDate ? format(event.fromDate) : `${format(event.fromDate)} – ${format(event.toDate)}`
  return event.isFullDay ? dates : `${dates} · ${event.fromTime}–${event.toTime}`
}
</script>

<template>
  <FrappeUIProvider>
  <div class="rental-page">
    <header class="hero">
      <div class="hero-copy">
        <div class="eyebrow"><span class="eyebrow-mark"></span> FLEET OPERATIONS</div>
        <h1>Rental calendar</h1>
        <p>One clear view of crane reservations, project schedules, and completed work.</p>
        <div class="hero-links"><a href="/app/crane-operations">← Crane Operations</a><span>·</span><a href="/app/crane-project-gantt">Fleet timeline ↗</a></div>
      </div>
      <div class="hero-art" aria-hidden="true"><span class="art-ring one"></span><span class="art-ring two"></span><span class="art-bar a"></span><span class="art-bar b"></span><span class="art-bar c"></span></div>
      <div class="hero-date"><span>VISIBLE RANGE</span><strong>{{ rangeLabel }}</strong></div>
    </header>

    <section class="overview" aria-label="Calendar summary">
      <div v-for="category in categories" :key="category.key" class="summary-card" :style="{ '--accent': category.color }">
        <span class="summary-icon"></span><div><strong>{{ counts[category.key] || 0 }}</strong><span>{{ category.label }}</span></div>
      </div>
      <div class="summary-card total-card"><span class="summary-icon"></span><div><strong>{{ visibleCount }}</strong><span>Visible events</span></div></div>
    </section>

    <section class="calendar-panel">
      <div class="panel-heading">
        <div><div class="panel-eyebrow">SCHEDULE</div><h2>Plan at a glance</h2><p>Switch between month, week, day, and agenda views.</p></div>
        <button class="refresh-button" type="button" :disabled="loading" @click="loadRange()"><span aria-hidden="true">↻</span> {{ loading ? 'Loading…' : 'Refresh' }}</button>
      </div>
      <div class="toolbar">
        <div class="filter-pills" aria-label="Event filters">
          <button v-for="category in categories" :key="category.key" type="button" class="filter-pill" :class="{ inactive: !visible[category.key] }" :aria-pressed="visible[category.key]" @click="toggle(category.key)">
            <span class="pill-dot" :style="{ background: category.color }"></span>{{ category.label }} <small>{{ counts[category.key] || 0 }}</small>
          </button>
        </div>
        <label class="search"><span aria-hidden="true">⌕</span><input v-model="query" type="search" placeholder="Search events" aria-label="Search events" /></label>
      </div>
      <div v-if="error" class="error" role="alert">{{ error }} <button type="button" @click="loadRange()">Try again</button></div>
      <div class="calendar-frame" :aria-busy="loading">
        <Calendar :events="filteredEvents" :loading="loading" :config="{ defaultMode: 'Month', isEditMode: false, weekends: ['friday', 'saturday'], timeFormat: '12h' }" @range-change="loadRange">
          <template #event-popover-content="{ calendarEvent, close }">
            <div class="event-detail">
              <div class="event-detail-top"><span class="event-kind" :class="calendarEvent.type">{{ calendarEvent.type }}</span><button type="button" class="detail-close" aria-label="Close event details" @click="close">×</button></div>
              <h3>{{ calendarEvent.title }}</h3>
              <div class="detail-status">{{ calendarEvent.status }}</div>
              <div class="detail-row"><span>Dates</span><strong>{{ dateLabel(calendarEvent) }}</strong></div>
              <div v-if="calendarEvent.participant" class="detail-row"><span>{{ calendarEvent.type === 'reservation' ? 'Driver' : calendarEvent.type === 'timesheet' && !calendarEvent.isFullDay ? 'Driver' : calendarEvent.type === 'timesheet' ? 'Crane' : 'Customer' }}</span><strong>{{ calendarEvent.participant }}</strong></div>
              <div v-if="calendarEvent.venue" class="detail-row"><span>{{ calendarEvent.type === 'reservation' ? 'Customer' : 'Project' }}</span><strong>{{ calendarEvent.venue }}</strong></div>
              <a class="open-record" :href="documentUrl(calendarEvent)">Open {{ calendarEvent.doctype }} <span>↗</span></a>
            </div>
          </template>
          <template #event-suffix="{ calendarEvent }"><span class="agenda-kind">{{ calendarEvent.type }}</span></template>
        </Calendar>
      </div>
      <p class="calendar-footnote">Drafts appear outlined. Cancelled reservations and projects are crossed out. Select an event to open its record.</p>
    </section>
  </div>
  </FrappeUIProvider>
</template>
