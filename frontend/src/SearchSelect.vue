<script setup>
import { computed, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  label: { type: String, required: true },
  placeholder: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])
const inputId = useId()
const listId = `${inputId}-list`
const root = ref(null)
const input = ref(null)
const query = ref('')
const open = ref(false)
const active = ref(0)
const selected = computed(() => props.options.find(option => option.id === props.modelValue))
const matches = computed(() => {
  const term = query.value.trim().toLocaleLowerCase()
  return props.options.filter(option =>
    !term || `${option.label} ${option.id}`.toLocaleLowerCase().includes(term)
  ).slice(0, 50)
})

watch(() => [props.modelValue, selected.value?.label], () => {
  if (!open.value) query.value = selected.value?.label || props.modelValue || ''
}, { immediate: true })

function show() {
  open.value = true
  active.value = 0
}
function onFocus() {
  show()
  if (props.modelValue) query.value = ''
}
function close() {
  open.value = false
  query.value = selected.value?.label || props.modelValue || ''
}
function choose(option) {
  if (!option) return
  emit('update:modelValue', option.id)
  query.value = option.label
  open.value = false
  input.value?.blur()
}
function clear() {
  emit('update:modelValue', '')
  query.value = ''
  show()
  input.value?.focus()
}
function chooseAll() {
  emit('update:modelValue', '')
  query.value = ''
  open.value = false
  input.value?.blur()
}
function onInput(event) {
  query.value = event.target.value
  if (props.modelValue) emit('update:modelValue', '')
  show()
}
function onKeydown(event) {
  if (event.key === 'Escape') { close(); input.value?.blur(); return }
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    if (!open.value) show()
    else active.value = (active.value + (event.key === 'ArrowDown' ? 1 : -1) + matches.value.length) % (matches.value.length || 1)
  }
  if (event.key === 'Enter' && open.value) {
    event.preventDefault()
    if (matches.value.length) choose(matches.value[active.value] || matches.value[0])
  }
}
function onOutside(event) {
  if (root.value && !root.value.contains(event.target)) close()
}
function onFocusOut(event) {
  if (open.value && root.value && !root.value.contains(event.relatedTarget)) close()
}
onMounted(() => document.addEventListener('pointerdown', onOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onOutside))
</script>

<template>
  <div ref="root" class="timeline-combobox" @focusout="onFocusOut">
    <label :for="inputId">{{ label }}</label>
    <div class="timeline-combobox-input">
      <input :id="inputId" ref="input" :value="query" :placeholder="placeholder" role="combobox" aria-autocomplete="list" :aria-expanded="open" :aria-controls="listId" :aria-activedescendant="open && matches.length ? `${listId}-${active}` : undefined" autocomplete="off" @focus="onFocus" @input="onInput" @keydown="onKeydown" />
      <button type="button" :aria-label="modelValue ? `Clear ${label} filter` : `Show ${label} choices`" @click="modelValue ? clear() : input?.focus()">{{ modelValue ? '×' : '⌄' }}</button>
    </div>
    <div v-if="open" :id="listId" class="timeline-combobox-list" role="listbox">
      <button type="button" class="timeline-combobox-option" :class="{ active: !modelValue && !query }" role="option" :aria-selected="!modelValue" @mousedown.prevent @click="chooseAll">All {{ label.toLowerCase() }}s</button>
      <button v-for="(option, index) in matches" :id="`${listId}-${index}`" :key="option.id" type="button" class="timeline-combobox-option" :class="{ active: index === active }" role="option" :aria-selected="option.id === modelValue" @mouseenter="active = index" @mousedown.prevent @click="choose(option)"><span>{{ option.label }}</span><small v-if="option.label !== option.id">{{ option.id }}</small></button>
      <div v-if="!matches.length" class="timeline-combobox-empty">No matches</div>
    </div>
  </div>
</template>
