import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, /api is proxied to the FastAPI server so no CORS setup is needed.
export default defineConfig({
  plugins: [react()],
  build: { rollupOptions: { output: { manualChunks: { charts: ['recharts'] } } } },
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
