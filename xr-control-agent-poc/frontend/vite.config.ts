import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const BACKEND_ORIGIN = 'http://127.0.0.1:8001'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': {
        target: BACKEND_ORIGIN,
        changeOrigin: true,
      },
      '/health': {
        target: BACKEND_ORIGIN,
        changeOrigin: true,
      },
    },
  },
})
