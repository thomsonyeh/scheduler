import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': `http://127.0.0.1:${process.env.BACKEND_PORT ?? 8100}` },
    // examples/ lives at the repo root
    fs: { allow: ['..'] },
  },
})
