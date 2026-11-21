<script setup>
import { nextTick, computed, ref, watch, onMounted, onUnmounted } from 'vue'
import SearchSelect from './SearchSelect.vue'

const pageParams = new URLSearchParams(window.location.search)
const requestedFrom = pageParams.get('from')
const requestedTo = pageParams.get('to')
const requestedSpan = Math.round((Date.parse(`${requestedTo}T12:00:00Z`) - Date.parse(`${requestedFrom}T12:00:00Z`)) / 86400000)
const initialRange = /^\d{4}-\d{2}-\d{2}$/.test(requestedFrom || '') && /^\d{4}-\d{2}-\d{2}$/.test(requestedTo || '') && requestedSpan >= 0 && requestedSpan <= 120
  ? { start: requestedFrom, end: requestedTo } : null
const sourceEvents = ref([])
const selected = ref(null)
const detailDialog = ref(null)

async function openDetails(event) {
  selected.value = event
  await nextTick()
  detailDialog.value.showModal()
}
function cycleDialogFocus(event) {
  const controls = detailDialog.value.querySelectorAll('button, a[href]')
  const first = controls[0]
  const last = controls[controls.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}
function closeOnBackdrop(event) {
  if (event.target !== detailDialog.value) return
  const bounds = detailDialog.value.getBoundingClientRect()
  if (event.clientX < bounds.left || event.clientX > bounds.right ||
      event.clientY < bounds.top || event.clientY > bounds.bottom) detailDialog.value.close()
}

const loading = ref(false)
const error = ref('')
const view = ref(initialRange ? 'Custom' : 'Month')
const groupBy = ref('Crane')
const advanced = ref(false)
const scrollElement = ref(null)
const trackSpace = ref(Math.max(320, window.innerWidth - 290))
const arabic = (window.her_language || '').startsWith('ar')
const locale = arabic ? 'ar-EG' : undefined
const words = { 'Booked':'محجوز', 'Draft':'مسودة', 'Submitted':'معتمد', 'Cancelled':'ملغى', 'Planned':'مخطط', 'In Progress':'قيد التنفيذ', 'Completed':'مكتمل', 'Timeline':'الجدول الزمني', 'Workspace':'مساحة العمل', 'Calendar':'التقويم', 'Rental Contract':'عقد ايجار معدة', 'Crane':'المعدة', 'Week':'أسبوع', 'Month':'شهر', 'Today':'اليوم', 'Fit contract':'مدة العقد', 'Filters':'تصفية', 'From':'من', 'To':'إلى', 'Apply':'عرض', 'Search events':'بحث في الأنشطة', 'All contracts':'كل العقود', 'All cranes':'كل المعدات', 'Reservations':'الحجوزات', 'Timesheets':'تايم شيت', 'Maintenance':'الصيانة', 'Loading…':'جارٍ التحميل…', 'No activity in this period':'لا توجد أنشطة في هذه الفترة', 'Try another date range or clear the filters.':'غيّر الفترة أو امسح عوامل التصفية.', 'Reset filters':'مسح التصفية', 'Retry':'إعادة المحاولة', 'Close':'إغلاق', 'When':'التاريخ', 'Location':'الموقع', 'Technician':'الفني', 'Operator':'السائق', 'Open record':'فتح المستند', 'Custom':'فترة مخصصة', 'Previous period':'الفترة السابقة', 'Next period':'الفترة التالية', 'Select an activity for details':'اضغط على النشاط لعرض التفاصيل', 'Unable to load the resource timeline.':'تعذر تحميل الجدول الزمني.', 'Choose both a From and a To date.':'حدد تاريخ البداية والنهاية.', 'The To date must be on or after the From date.':'يجب أن تكون النهاية بعد البداية أو في نفس اليوم.', 'Choose a range of at most 120 days.':'اختر فترة لا تتجاوز ١٢٠ يومًا.' }
const t = text => arabic ? words[text] || text : text
const anchor = ref(new Date())
const customRange = ref(initialRange)
const fromDate = ref('')
const toDate = ref('')
const rangeError = ref('')
const search = ref('')
const assignmentFilter = ref(pageParams.get('assignment') || '')
const craneFilter = ref(pageParams.get('crane') || '')
const enabled = ref({ reservation: true, timesheet: true, maintenance: true })
let requestNumber = 0

const categories = [
  { key: 'reservation', label: 'Reservations', color: '#1265d8' },
  { key: 'timesheet', label: 'Timesheets', color: '#22a4e8' },
  { key: 'maintenance', label: 'Maintenance', color: '#d98532' },
]
const assignmentCranes = computed(() => {
  const result = new Map()
  for (const event of sourceEvents.value) {
    if (!event.assignment || !event.crane) continue
    if (!result.has(event.assignment)) result.set(event.assignment, new Set())
    result.get(event.assignment).add(event.crane)
  }
  return result
})
const assignmentOptions = computed(() => {
  const names = new Map()
  for (const event of sourceEvents.value) {
    if (event.assignment) names.set(event.assignment, event.assignment_name || names.get(event.assignment) || event.assignment)
  }
  if (assignmentFilter.value && !names.has(assignmentFilter.value)) names.set(assignmentFilter.value, assignmentFilter.value)
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
  (!assignmentFilter.value || event.assignment === assignmentFilter.value) &&
  (!craneFilter.value || event.crane === craneFilter.value ||
    (!event.crane && assignmentCranes.value.get(event.assignment)?.has(craneFilter.value)))
))
const counts = computed(() => Object.fromEntries(categories.map(item => [
  item.key,
  new Set(recordFilteredEvents.value.filter(event => event.type === item.key).map(event => ['timesheet', 'maintenance'].includes(event.type) ? event.docname : event.id)).size,
])))
const activeCategories = computed(() => categories.filter(item => counts.value[item.key] > 0))
const shown = computed(() => recordFilteredEvents.value.filter(event =>
  enabled.value[event.type] && `${event.title} ${event.participant || ''} ${event.venue || ''} ${event.status || ''}`.toLowerCase().includes(search.value.trim().toLowerCase())
))
const dayWidth = computed(() => Math.max(36, Math.floor(trackSpace.value / days.value.length)))
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
    return { key: formatDate(date), day: date.getDate(), weekday: date.toLocaleDateString(locale, { weekday: 'short' }), isToday: formatDate(date) === formatDate(new Date()), isWeekend: [5, 6].includes(date.getDay()) }
  })
})
const rangeEnd = computed(() => days.value.at(-1)?.key)
const title = computed(() => view.value === 'Month'
  ? rangeStart.value.toLocaleDateString(locale, { month: 'long', year: 'numeric' })
  : `${rangeStart.value.toLocaleDateString(locale, { month: 'short', day: 'numeric' })} – ${new Date(`${rangeEnd.value}T12:00:00`).toLocaleDateString(locale, { month: 'short', day: 'numeric', year: 'numeric' })}`)
const totalWidth = computed(() => dayWidth.value * days.value.length)
const records = computed(() => {
  const result = new Map()
  const assignmentNames = new Map()
  const craneNames = new Map()
  for (const event of sourceEvents.value) {
    if (event.assignment && event.assignment_name) assignmentNames.set(event.assignment, event.assignment_name)
    if (event.crane && event.crane_name) craneNames.set(event.crane, event.crane_name)
  }
  for (const event of shown.value) {
    let keys
    if (groupBy.value === 'Rental Contract') {
      keys = event.assignment ? [`assignment:${event.assignment}`] : event.crane ? [`unassigned-crane:${event.crane}`] : ['unassigned']
    } else {
      const cranes = event.crane ? [event.crane] : [...(assignmentCranes.value.get(event.assignment) || [])]
      keys = cranes.length ? cranes.map(crane => `crane:${crane}`) : event.assignment ? [`unassigned-assignment:${event.assignment}`] : ['unassigned']
    }
    for (const id of keys) {
      if (!result.has(id)) {
        const [kind, value] = id.split(':')
        const isAssignment = kind === 'assignment' || kind === 'unassigned-assignment'
        const title = kind === 'assignment' ? (assignmentNames.get(value) || value)
          : kind === 'crane' || kind === 'unassigned-crane' ? (craneNames.get(value) || value)
            : 'Unassigned'
        const detail = kind === 'assignment' ? [value, sourceEvents.value.find(item => item.assignment === value)?.venue].filter(Boolean).join(' · ')
          : kind === 'unassigned-crane' ? 'No linked rental contract'
            : kind === 'unassigned-assignment' ? `No linked crane · ${assignmentNames.get(value) || value}`
              : isAssignment ? value : kind === 'crane' ? value : 'No linked rental contract or crane'
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
    rangeError.value = t('Choose both a From and a To date.')
    return
  }
  const span = Math.round((Date.parse(`${toDate.value}T12:00:00Z`) - Date.parse(`${fromDate.value}T12:00:00Z`)) / 86400000)
  if (span < 0) rangeError.value = t('The To date must be on or after the From date.')
  else if (span > 120) rangeError.value = t('Choose a range of at most 120 days.')
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
    if (!response.ok || payload.exc) throw new Error(t('Unable to load the resource timeline.'))
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
  const date = value => new Date(`${value}T12:00:00`).toLocaleDateString(locale, { month: 'short', day: 'numeric' })
  const dates = event.fromDate === event.toDate ? date(event.fromDate) : `${date(event.fromDate)} – ${date(event.toDate)}`
  return event.isFullDay ? dates : `${dates} · ${event.fromTime}–${event.toTime}`
}
async function fitContract() {
  if (!assignmentFilter.value) return
  const contract = assignmentFilter.value
  try {
    const response = await fetch(`/api/resource/Rental%20Contract/${encodeURIComponent(contract)}`, { credentials: 'same-origin' })
    const payload = await response.json()
    if (!response.ok || !payload.data) throw new Error(t('Unable to load the resource timeline.'))
    if (contract !== assignmentFilter.value) return
    const bookings = (payload.data.assigned_cranes || []).filter(row => !row.cancelled && row.start_date && row.expected_end_date)
    if (!bookings.length) return
    const start = bookings.map(row => row.start_date).sort()[0]
    const last = bookings.map(row => row.expected_end_date).sort().at(-1)
    customRange.value = { start: shiftDate(start, -1), end: last > shiftDate(start, 118) ? shiftDate(start, 118) : shiftDate(last, 1) }
    view.value = 'Custom'
  } catch (reason) { error.value = reason.message }
}
function resetFilters() {
  assignmentFilter.value = pageParams.get('assignment') || ''
  craneFilter.value = ''
  search.value = ''
  enabled.value = { reservation: true, timesheet: true, maintenance: true }
}
let resizeObserver
onMounted(() => {
  resizeObserver = new ResizeObserver(([entry]) => { trackSpace.value = Math.max(36, entry.contentRect.width - (window.innerWidth <= 650 ? 140 : 210)) })
  if (scrollElement.value) resizeObserver.observe(scrollElement.value)
  if (assignmentFilter.value && !initialRange) fitContract()
})
onUnmounted(() => resizeObserver?.disconnect())
</script>

<template>
  <div class="timeline-page timeline-simple" :lang="arabic ? 'ar' : 'en'">
    <header class="timeline-simple-header" :dir="arabic ? 'rtl' : 'ltr'">
      <div><h1>{{ t('Timeline') }}</h1><a v-if="assignmentFilter" class="timeline-contract" :href="`/app/rental-contract/${encodeURIComponent(assignmentFilter)}`">{{ t('Rental Contract') }} · {{ assignmentFilter }} ↗</a></div>
      <nav><a href="/rental-calendar">{{ t('Calendar') }}</a><a href="/app/crane-operations">{{ t('Workspace') }} ↗</a></nav>
    </header>
    <main class="timeline-panel">
      <div class="timeline-head" :dir="arabic ? 'rtl' : 'ltr'">
        <h2>{{ title }}</h2>
        <div class="timeline-nav"><button type="button" @click="navigate(-1)" :aria-label="t('Previous period')">‹</button><button type="button" @click="goToday">{{ t('Today') }}</button><button type="button" @click="navigate(1)" :aria-label="t('Next period')">›</button></div>
        <div class="timeline-switch"><button v-for="period in ['Week','Month']" :key="period" type="button" :class="{active:view===period}" @click="changeView(period)">{{ t(period) }}</button><button v-if="assignmentFilter" type="button" :class="{active:view==='Custom'}" @click="fitContract">{{ t('Fit contract') }}</button></div>
      </div>
      <div class="timeline-compact-controls" :dir="arabic ? 'rtl' : 'ltr'">
        <div class="timeline-filters"><button v-for="item in activeCategories" :key="item.key" type="button" :class="{ off: !enabled[item.key] }" :aria-pressed="enabled[item.key]" @click="enabled[item.key] = !enabled[item.key]"><i :style="{ background: item.color }"></i>{{ t(item.label) }} <small>{{ counts[item.key] || 0 }}</small></button></div>
        <button class="timeline-filter-toggle" type="button" :aria-expanded="advanced" @click="advanced=!advanced">{{ t('Filters') }} {{ advanced ? '−' : '+' }}<span v-if="craneFilter || search"> •</span></button>
      </div>
      <div v-if="advanced" class="timeline-control-row timeline-advanced" :dir="arabic ? 'rtl' : 'ltr'">
        <SearchSelect v-model="assignmentFilter" :label="t('Rental Contract')" :placeholder="t('All contracts')" :options="assignmentOptions" />
        <SearchSelect v-model="craneFilter" :label="t('Crane')" :placeholder="t('All cranes')" :options="craneOptions" />
        <form class="timeline-inline-dates" @submit.prevent="applyRange"><label>{{ t('From') }}<input v-model="fromDate" type="date" :aria-label="t('From')" required /></label><label>{{ t('To') }}<input v-model="toDate" type="date" :aria-label="t('To')" required /></label><button type="submit">{{ t('Apply') }}</button><span v-if="rangeError" class="timeline-range-error" role="alert">{{ rangeError }}</span></form>
        <label class="timeline-search"><input v-model="search" type="search" :placeholder="t('Search events')" :aria-label="t('Search events')" /></label>
        <button class="timeline-filter-toggle" type="button" @click="resetFilters">{{ t('Reset filters') }}</button>
      </div>
      <div v-if="error" class="timeline-error" role="alert">{{ error }} <button type="button" @click="loadRange">{{ t('Retry') }}</button></div>
      <div v-if="loading" class="timeline-loading" role="status">{{ t('Loading…') }}</div>
      <div ref="scrollElement" class="timeline-scroll" :aria-busy="loading">
        <div class="timeline-grid" :style="{ '--day-width': `${dayWidth}px`, '--track-width': `${totalWidth}px` }">
          <div class="timeline-row timeline-header"><div class="timeline-resource-head">{{ t('Crane') }}</div><div class="timeline-track timeline-dates"><div v-for="day in days" :key="day.key" class="timeline-day" :class="{ today: day.isToday, weekend: day.isWeekend }"><strong>{{ day.day }}</strong><small>{{ day.weekday }}</small></div></div></div>
          <div v-for="row in lanes" :key="row.id" class="timeline-row timeline-data-row" :style="{ height: `${row.height}px` }"><div class="timeline-resource"><strong :title="row.title">{{ row.title }}</strong><small :title="row.detail">{{ row.detail }}</small></div><div class="timeline-track timeline-lane"><span v-for="day in days" :key="day.key" class="timeline-cell" :class="{ today: day.isToday, weekend: day.isWeekend }"></span><button v-for="segment in row.segments" :key="segment.event.id" type="button" class="timeline-bar" :class="[segment.event.type, { draft: segment.event.isDraft, cancelled: segment.event.isDeclined }]" :style="{ left: `${segment.first * dayWidth + 3}px`, width: `${(segment.last - segment.first + 1) * dayWidth - 6}px`, top: `${10 + segment.lane * 27}px` }" :title="`${segment.event.title} · ${t(segment.event.status)}`" @click="openDetails(segment.event)">{{ segment.event.title }}</button></div></div>
          <div v-if="!lanes.length && !loading" class="timeline-empty"><strong>{{ t('No activity in this period') }}</strong><p>{{ t('Try another date range or clear the filters.') }}</p></div>
        </div>
      </div>
      <div class="timeline-footer" :dir="arabic ? 'rtl' : 'ltr'">{{ t('Select an activity for details') }}</div>
    </main>
    <dialog ref="detailDialog" class="timeline-detail" @close="selected = null" @keydown.tab="cycleDialogFocus" @click="closeOnBackdrop" :aria-label="selected?.title" :dir="arabic ? 'rtl' : 'ltr'"><template v-if="selected"><button class="timeline-close" type="button" autofocus :aria-label="t('Close')" @click="detailDialog.close()">×</button><span class="timeline-detail-kind" :class="selected.type">{{ t(categories.find(item=>item.key===selected.type)?.label || selected.type) }}</span><h3>{{ selected.title }}</h3><span class="timeline-detail-status">{{ t(selected.status) }}</span><dl><div><dt>{{ t('When') }}</dt><dd>{{ dateLabel(selected) }}</dd></div><div v-if="selected.participant"><dt>{{ t(selected.type === 'maintenance' ? 'Technician' : selected.type === 'timesheet' && !selected.isFullDay ? 'Operator' : 'Crane') }}</dt><dd>{{ selected.participant }}</dd></div><div v-if="selected.venue"><dt>{{ t('Location') }}</dt><dd>{{ selected.venue }}</dd></div></dl><a :href="documentUrl(selected)">{{ t('Open record') }} ↗</a></template></dialog>
  </div>
</template>
