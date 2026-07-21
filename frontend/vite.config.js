import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  // The shared deployment variables live beside backend/, not inside frontend/.
  envDir: fileURLToPath(new URL('../', import.meta.url)),
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
