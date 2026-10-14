import { execFileSync } from 'node:child_process'
import { expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { E2E_DATABASE_URL, backendDir, python } from './paths'

/** Resposta da rodada atual de uma sala multiplayer (CLI do servidor). */
export function revealRoom(code: string): { title: string; round: number } {
  return cli(['reveal', '--room', code, '--json']) as { title: string; round: number }
}

function cli(args: string[]): unknown {
  const output = execFileSync(python, ['-m', 'app.cli', ...args], {
    cwd: backendDir,
    env: { ...process.env, DATABASE_URL: E2E_DATABASE_URL, AUDIO_PROVIDER: 'demo', PYTHONUTF8: '1' },
  })
  return JSON.parse(output.toString())
}

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

/**
 * Guarda o texto compartilhado (Web Share API ou cópia) em `window.__shared`, sem depender
 * de ler a área de transferência — o WebKit do Playwright não permite essa leitura.
 * Os métodos originais continuam sendo chamados.
 */
export async function captureShares(page: Page) {
  await page.addInitScript(() => {
    const store = window as unknown as { __shared: string[] }
    store.__shared = []
    const nav = navigator as Navigator & { share?: (data: ShareData) => Promise<void> }
    if (typeof nav.share === 'function') {
      nav.share = async (data: ShareData) => {
        store.__shared.push(data.text ?? '')
      }
    }
    if (navigator.clipboard?.writeText) {
      const original = navigator.clipboard.writeText.bind(navigator.clipboard)
      navigator.clipboard.writeText = async (text: string) => {
        store.__shared.push(text)
        return original(text).catch(() => undefined)
      }
    }
  })
}

export async function sharedText(page: Page): Promise<string> {
  return page.evaluate(() => (window as unknown as { __shared: string[] }).__shared.join('\n'))
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
