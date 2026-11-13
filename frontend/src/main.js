import { createApp, h } from 'vue'
import { createRouter, createWebHistory, RouterView } from 'vue-router'
import App from './App.vue'
import ResourceTimeline from './ResourceTimeline.vue'
import './style.css'
import './timeline.css'
import '../../heavy_equipment_rental/public/css/industrial_tokens.css'
import './industrial.css'

// Match the user's existing Desk preference without changing or storing it.
const preferredTheme = (window.her_desk_theme || 'Automatic').toLowerCase()
const systemTheme = window.matchMedia('(prefers-color-scheme: dark)')
function applyTheme() {
  document.documentElement.dataset.theme = preferredTheme === 'automatic'
    ? (systemTheme.matches ? 'dark' : 'light')
    : preferredTheme
}
applyTheme()
if (preferredTheme === 'automatic') systemTheme.addEventListener('change', applyTheme)

const router = createRouter({
  history: createWebHistory('/rental-calendar'),
  routes: [
    { path: '/', component: App },
    { path: '/timeline', component: ResourceTimeline },
  ],
})

createApp({ render: () => h(RouterView) }).use(router).mount('#app')
