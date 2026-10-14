/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Em desenvolvimento, /api é encaminhado ao backend FastAPI local.
const apiTarget = process.env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  // GitHub Pages serve o site em /<repositório>/ (VITE_BASE_PATH=/DailyMusicBabuinos/).
  base: process.env.VITE_BASE_PATH ?? '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: apiTarget, changeOrigin: true } },
  },
  preview: {
    port: 4173,
    proxy: { '/api': { target: apiTarget, changeOrigin: true } },
  },
  build: { target: 'es2022', sourcemap: false },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: { modules: { classNameStrategy: 'non-scoped' } },
  },
})
