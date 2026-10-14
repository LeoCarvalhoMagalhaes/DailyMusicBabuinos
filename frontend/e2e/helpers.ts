import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const backendDir = path.resolve(import.meta.dirname, '../../backend')
const python = process.env.E2E_PYTHON ?? path.join(backendDir, '.venv/bin/python')

/** Lê a resposta do dia direto no banco, pela CLI do servidor (não existe rota HTTP para isso). */
export function revealAnswer(category: string): { title: string; artist: string } {
  const output = execFileSync(python, ['-m', 'app.cli', 'reveal', '--category', category, '--json'], {
    cwd: backendDir,
    env: { ...process.env, DATABASE_URL: `sqlite:///${path.join(backendDir, 'e2e.db')}` },
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
