import { execFileSync } from 'node:child_process'
import { expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { E2E_DATABASE_URL, backendDir, python } from './paths'

/** Lê a resposta do dia direto no banco, pela CLI do servidor (não existe rota HTTP para isso). */
export function revealAnswer(category: string): { title: string; artist: string } {
  const output = execFileSync(python, ['-m', 'app.cli', 'reveal', '--category', category, '--json'], {
    cwd: backendDir,
    // Mesmo banco e mesmo provedor do servidor dos testes (modo demo).
    env: {
      ...process.env,
      DATABASE_URL: E2E_DATABASE_URL,
      AUDIO_PROVIDER: 'demo',
      // No Windows a saída do Python num pipe usaria a página de código local (cp1252).
      PYTHONUTF8: '1',
    },
  })
  return JSON.parse(output.toString())
}

export async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
}

export async function openChallenge(page: Page, category: string) {
  await page.goto(`/desafio/${category}`)
  await expect(page.getByRole('heading', { name: /Desafio #\d+/ })).toBeVisible()
}

export async function submitGuess(page: Page, text: string) {
  await page.getByRole('combobox', { name: 'Título da música' }).fill(text)
  await page.getByRole('button', { name: 'Confirmar' }).click()
}
