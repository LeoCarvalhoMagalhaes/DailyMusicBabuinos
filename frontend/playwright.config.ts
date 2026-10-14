import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'

// Testes de ponta a ponta: sobem o backend real (modo demonstração, banco SQLite
// descartável) e o frontend, e jogam partidas completas em desktop e celular.
const API_PORT = 8011
const WEB_PORT = 5175
const backendDir = path.resolve(import.meta.dirname, '../backend')
const python = process.env.E2E_PYTHON ?? path.join(backendDir, '.venv/bin/python')
export const E2E_DB = path.join(backendDir, 'e2e.db')

const backendEnv = [
  `DATABASE_URL=sqlite:///${E2E_DB}`,
  'APP_ENV=test',
  'AUDIO_PROVIDER=demo',
  'CHALLENGE_SECRET=segredo-dos-testes-e2e-com-mais-de-32-chars',
  'RATE_LIMIT_PLAYERS_PER_HOUR=500',
  `CORS_ORIGINS=http://127.0.0.1:${WEB_PORT}`,
].join(' ')

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  timeout: 45_000,
  expect: { timeout: 8_000 },
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: 'retain-on-failure',
    permissions: ['clipboard-read', 'clipboard-write'],
    locale: 'pt-BR',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: [
    {
      command: `rm -f ${E2E_DB}* && ${backendEnv} ${python} -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: backendDir,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort --host 127.0.0.1`,
      env: { VITE_DEV_API_TARGET: `http://127.0.0.1:${API_PORT}` },
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
