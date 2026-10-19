import { createApp, h } from 'vue'
import { createRouter, createWebHistory, RouterView } from 'vue-router'
import App from './App.vue'
import ResourceTimeline from './ResourceTimeline.vue'
import './style.css'
import './timeline.css'

const router = createRouter({
  history: createWebHistory('/rental-calendar'),
  routes: [
    { path: '/', component: App },
    { path: '/timeline', component: ResourceTimeline },
  ],
})

createApp({ render: () => h(RouterView) }).use(router).mount('#app')
