import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'
import { E2E_DATABASE_URL, E2E_DB, backendDir, python } from './e2e/paths'

// Testes de ponta a ponta: sobem o backend real (modo demonstração, banco SQLite
// descartável) e o frontend, e jogam partidas completas em desktop e celular.
const API_PORT = 8011
const WEB_PORT = 5175
const cleanDb = path.resolve(import.meta.dirname, 'e2e/clean-db.mjs')

// Variáveis passadas pelo Playwright (e não como `VAR=x comando`), para funcionar em
// qualquer shell, inclusive o cmd.exe do Windows.
const backendEnv = {
  DATABASE_URL: E2E_DATABASE_URL,
  APP_ENV: 'test',
  AUDIO_PROVIDER: 'demo',
  CHALLENGE_SECRET: 'segredo-dos-testes-e2e-com-mais-de-32-chars',
  RATE_LIMIT_PLAYERS_PER_HOUR: '500',
  CORS_ORIGINS: `http://127.0.0.1:${WEB_PORT}`,
}

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
      command: `node "${cleanDb}" "${E2E_DB}" && "${python}" -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: backendDir,
      env: backendEnv,
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
