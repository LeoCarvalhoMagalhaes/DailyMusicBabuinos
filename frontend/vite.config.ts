/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Em desenvolvimento, /api é encaminhado ao backend FastAPI local.
const apiTarget = process.env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:8000'

// No build de produção, o navegador já abre a conexão segura com a API enquanto o
// site carrega (a API fica em outro domínio).
const apiOrigin = process.env.VITE_API_BASE_URL ? new URL(process.env.VITE_API_BASE_URL).origin : null

export default defineConfig({
  // GitHub Pages serve o site em /<repositório>/ (VITE_BASE_PATH=/DailyMusicBabuinos/).
  base: process.env.VITE_BASE_PATH ?? '/',
  plugins: [
    react(),
    {
      name: 'preconnect-api',
      transformIndexHtml: (html) =>
        apiOrigin
          ? html.replace('</title>', `</title>\n    <link rel="preconnect" href="${apiOrigin}" crossorigin />`)
          : html,
    },
  ],
  server: {
    port: 5173,
    proxy: { '/api': { target: apiTarget, changeOrigin: true, ws: true } },
  },
  preview: {
    port: 4173,
    proxy: { '/api': { target: apiTarget, changeOrigin: true, ws: true } },
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
