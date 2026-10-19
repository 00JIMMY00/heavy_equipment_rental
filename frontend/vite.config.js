import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'

export default defineConfig({
  plugins: [frappeui({ frontendRoute: '/rental-calendar', buildConfig: { indexHtmlPath: '../heavy_equipment_rental/www/rental_calendar.html' } }), vue()],
})
