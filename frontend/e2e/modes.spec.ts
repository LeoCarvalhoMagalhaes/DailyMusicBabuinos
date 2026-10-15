import { expect, test } from '@playwright/test'
import type { Browser, Page } from '@playwright/test'
import { expectNoHorizontalScroll, revealRoom, submitGuess } from './helpers'

test.describe('Modos de jogo', () => {
  test('página inicial apresenta os três modos', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByTestId('mode-daily')).toContainText('Desafio Diário')
    await expect(page.getByTestId('mode-endless')).toContainText('Modo Ilimitado')
    await expect(page.getByTestId('mode-multiplayer')).toContainText('Multiplayer')
    await expectNoHorizontalScroll(page)
  })

  test('modo ilimitado: rodadas seguidas sem mexer no diário', async ({ page }) => {
    await page.goto('/ilimitado')
    await page.getByTestId('endless-rock').click()
    await expect(page.getByRole('heading', { name: 'Rodada 1' })).toBeVisible()
    const audio = page.waitForResponse((r) => r.url().includes('/audio?stage=1'))
    await page.getByRole('button', { name: 'Tocar trecho 1' }).click()
    expect((await audio).status()).toBe(200)
    await expectNoHorizontalScroll(page)

    // Desiste da rodada: a resposta aparece e dá para seguir para a próxima.
    for (let i = 0; i < 5; i++) await page.getByRole('button', { name: /^Pular/ }).click()
    await page.getByRole('button', { name: /Desistir/ }).click()
    await expect(page.getByRole('heading', { name: 'A música era…' })).toBeVisible()
    await expect(page.getByTestId('session-wins')).toHaveText('0')
    await page.getByRole('button', { name: 'Próxima música' }).click()
    await expect(page.getByRole('heading', { name: 'Rodada 2' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Trecho 2 bloqueado' })).toBeDisabled()

    // O desafio diário continua intocado.
    await page.goto('/')
    await expect(page.getByTestId('category-rock')).toHaveAttribute('data-status', 'not_started')
  })
})

async function signUp(browser: Browser, name: string, device: object): Promise<Page> {
  const context = await browser.newContext({ ...device, locale: 'pt-BR' })
  const page = await context.newPage()
  await page.goto('/multiplayer')
  await page.getByRole('tab', { name: 'Criar conta' }).click()
  await page.getByLabel('Usuário').fill(name)
  await page.getByLabel('Apelido nas salas').fill(name)
  await page.getByLabel('Senha').fill('senha-do-teste-123')
  await page.getByRole('button', { name: 'Criar conta e entrar' }).click()
  await expect(page.getByText(`Jogando como ${name}`)).toBeVisible()
  return page
}

test('multiplayer: dois jogadores na mesma sala, sincronizados', async ({ browser }, testInfo) => {
  test.setTimeout(90_000)
  const device = testInfo.project.use
  const suffix = `${testInfo.project.name}${Date.now() % 100000}`
  const alice = await signUp(browser, `alice_${suffix}`.slice(0, 20), device)
  const bob = await signUp(browser, `bob_${suffix}`.slice(0, 20), device)

  await alice.getByRole('button', { name: 'Criar sala' }).click()
  const code = (await alice.getByTestId('room-code').textContent())?.trim() ?? ''
  expect(code).toMatch(/^[A-Z2-9]{6}$/)

  await bob.getByLabel('Código do convite').fill(code.toLowerCase())
  await bob.getByRole('button', { name: 'Entrar na sala' }).click()
  await expect(bob.getByTestId('room-code')).toHaveText(code)
  // A Alice vê o Bob chegar sem recarregar a página (WebSocket).
  await expect(alice.getByRole('list', { name: 'Jogadores na sala' }).getByRole('listitem')).toHaveCount(2)
  await expect(alice.getByRole('button', { name: 'Iniciar partida' })).toBeDisabled()

  await bob.getByRole('button', { name: 'Estou pronto' }).click()
  await expect(alice.getByRole('button', { name: 'Iniciar partida' })).toBeEnabled()
  // O trecho liberado é pré-carregado assim que a rodada aparece: escuta desde já.
  const clip = alice.waitForResponse((r) => r.url().includes('/rounds/1/audio?stage=1'))
  await alice.getByRole('button', { name: 'Iniciar partida' }).click()

  for (const page of [alice, bob]) {
    await expect(page.getByTestId('round-title')).toHaveText('Rodada 1 de 18')
    await expectNoHorizontalScroll(page)
  }

  // Áudio servido por partes, igual aos outros modos.
  const response = await clip
  await alice.getByRole('button', { name: 'Tocar trecho 1' }).click()
  await expect(alice.getByRole('button', { name: 'Trecho 2 bloqueado' })).toBeDisabled()
  expect(response.status()).toBe(200)
  expect(response.headers()['x-clip-duration']).toBe('0.500')

  const answer = revealRoom(code)
  await submitGuess(alice, answer.title)
  // O Bob vê que a Alice acertou, mas não vê a resposta.
  await expect(bob.getByText(/acertou \+\d+/)).toBeVisible()
  await expect(bob.getByText(answer.title, { exact: true })).toHaveCount(0)

  // Reconexão: o Bob recarrega a página e volta para a mesma rodada.
  await bob.reload()
  await expect(bob.getByTestId('round-title')).toHaveText('Rodada 1 de 18')
  await submitGuess(bob, 'Música Que Não Existe')
  await expect(bob.getByText('5 restantes')).toBeVisible()
  await submitGuess(bob, answer.title)

  // Todos terminaram: revelação para os dois ao mesmo tempo.
  for (const page of [alice, bob]) {
    await expect(page.getByText(answer.title, { exact: true }).first()).toBeVisible()
    await expect(page.getByText('para a próxima rodada')).toBeVisible()
  }
  await expect(alice.getByTestId('round-title')).toHaveText('Rodada 2 de 18', { timeout: 15_000 })
  await expect(bob.getByTestId('round-title')).toHaveText('Rodada 2 de 18', { timeout: 15_000 })
})
