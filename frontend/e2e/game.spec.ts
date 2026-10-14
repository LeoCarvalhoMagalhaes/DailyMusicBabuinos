import { expect, test } from '@playwright/test'
import {
  captureShares,
  expectNoHorizontalScroll,
  openChallenge,
  revealAnswer,
  sharedText,
  submitGuess,
} from './helpers'

test.describe('Músicas Babuínas', () => {
  test('página inicial mostra as seis categorias e o modo demonstração', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /Ouviu\?/ })).toBeVisible()
    for (const slug of ['rock', 'pop', 'rap', 'country', 'eletronica', 'geral']) {
      await expect(page.getByTestId(`category-${slug}`)).toBeVisible()
    }
    await expect(page.getByLabel('Modo demonstração')).toBeVisible()
    await expect(page.getByText(/Desafio #\d+ · /)).toBeVisible()
    await expect(page.getByRole('img', { name: /Babuíno do Rock/ })).toBeVisible()
    await expectNoHorizontalScroll(page)
  })

  test('partida vencida: áudio, erro, persistência, acerto e compartilhamento', async ({ page }) => {
    await captureShares(page)
    // O trecho liberado é pré-carregado ao abrir a partida: escuta a resposta desde já.
    const audioResponse = page.waitForResponse((r) => r.url().includes('/audio?stage=1'))
    await openChallenge(page, 'rock')
    await expectNoHorizontalScroll(page)
    const audio = await audioResponse
    expect(audio.status()).toBe(200)
    expect(audio.headers()['x-clip-duration']).toBe('1.000')

    // Toca a primeira pista (o servidor entrega só o trecho liberado).
    await page.getByRole('button', { name: 'Tocar trecho 1' }).click()
    await expect(page.getByRole('button', { name: 'Ouvir trecho 1 (1s)' })).toBeEnabled()
    await expect(page.getByRole('button', { name: 'Trecho 2 bloqueado' })).toBeDisabled()

    // Autocomplete + palpite errado.
    const answer = revealAnswer('rock')
    const wrong = answer.title === 'Jingle Bells' ? 'Greensleeves' : 'Jingle Bells'
    await page.getByRole('combobox', { name: 'Título da música' }).fill(wrong.slice(0, 5))
    await page.getByRole('option', { name: new RegExp(wrong) }).click()
    await page.getByRole('button', { name: 'Confirmar' }).click()
    await expect(page.getByRole('listitem').filter({ hasText: wrong })).toBeVisible()
    await expect(page.getByText('5 restantes')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Ouvir trecho 2 (2s)' })).toBeEnabled()

    // Recarregar mantém a mesma partida e as tentativas usadas.
    await page.reload()
    await expect(page.getByText('5 restantes')).toBeVisible()
    await expect(page.getByRole('listitem').filter({ hasText: wrong })).toBeVisible()

    // Acerto com caixa e acentos diferentes.
    await submitGuess(page, answer.title.toUpperCase())
    await expect(page.getByRole('heading', { name: 'Acertou na 2ª tentativa!' })).toBeVisible()
    const result = page.locator('#resultado')
    await expect(result.getByText(answer.title, { exact: true })).toBeVisible()
    await expect(result.getByText('80', { exact: true })).toBeVisible()
    await expect(page.getByRole('img', { name: /sinal do rock/ })).toBeVisible()
    await expect(page.getByText(/Próximo desafio em \d\d:\d\d:\d\d/)).toBeVisible()

    // Compartilhar (Web Share API ou cópia) sem revelar a música.
    await page.getByRole('button', { name: /Compartilhar resultado/ }).click()
    await expect(page.getByRole('button', { name: /Copiado|Compartilhado/ })).toBeVisible()
    const clipboard = await sharedText(page)
    expect(clipboard).toContain('Resultado: ACERTEI!')
    expect(clipboard).toContain('Tentativa: 2/6')
    expect(clipboard).toContain('🟥🟩⬛⬛⬛⬛')
    expect(clipboard).not.toContain(answer.title)

    // Partida concluída não reinicia ao voltar.
    await page.goto('/')
    await expect(page.getByTestId('category-rock')).toHaveAttribute('data-status', 'won')
    await openChallenge(page, 'rock')
    await expect(page.getByRole('heading', { name: 'Acertou na 2ª tentativa!' })).toBeVisible()
    await expect(page.getByRole('combobox')).toHaveCount(0)
    await expectNoHorizontalScroll(page)
  })

  test('partida perdida revela a música e entra nas estatísticas', async ({ page }) => {
    await openChallenge(page, 'country')
    const answer = revealAnswer('country')
    for (let i = 0; i < 5; i++) {
      await page.getByRole('button', { name: /^Pular/ }).click()
      await expect(page.getByText(`${5 - i} ${5 - i === 1 ? 'restante' : 'restantes'}`)).toBeVisible()
    }
    await page.getByRole('button', { name: /Desistir/ }).click()
    await expect(page.getByRole('heading', { name: 'A música era…' })).toBeVisible()
    await expect(page.locator('#resultado').getByText(answer.title, { exact: true })).toBeVisible()
    await expect(page.getByRole('img', { name: /corda da guitarra arrebentada/ })).toBeVisible()

    await page.getByRole('link', { name: 'Estatísticas' }).click()
    await expect(page.getByRole('heading', { name: 'Estatísticas' })).toBeVisible()
    await expect(page.getByRole('listitem').filter({ hasText: answer.title })).toBeVisible()
    await expectNoHorizontalScroll(page)
  })

  test('palpite repetido não consome tentativa', async ({ page }) => {
    await openChallenge(page, 'geral')
    const answer = revealAnswer('geral')
    const wrong = answer.title === 'Yankee Doodle' ? 'Greensleeves' : 'Yankee Doodle'
    await submitGuess(page, wrong)
    await expect(page.getByText('5 restantes')).toBeVisible()
    await submitGuess(page, wrong.toLowerCase())
    await expect(page.getByText('Você já tentou essa! Escolha outra música.')).toBeVisible()
    await expect(page.getByText('5 restantes')).toBeVisible()
  })

  test('avisa quando o aparelho fica offline', async ({ page, context }) => {
    await openChallenge(page, 'pop')
    await context.setOffline(true)
    await expect(page.getByRole('status').filter({ hasText: 'Você está offline' })).toBeVisible()
    await expect(page.getByRole('combobox')).toBeDisabled()
    await context.setOffline(false)
    await expect(page.getByRole('combobox')).toBeEnabled()
  })

  test('páginas de regras, sobre e 404', async ({ page }) => {
    await page.goto('/como-jogar')
    await expect(page.getByRole('heading', { name: 'Como jogar' })).toBeVisible()
    await expect(page.getByRole('cell', { name: '100' })).toBeVisible()
    await page.goto('/sobre#privacidade')
    await expect(page.getByRole('heading', { name: 'Privacidade' })).toBeVisible()
    await page.goto('/desafio/jazz')
    await expect(page.getByRole('heading', { name: /404/ })).toBeVisible()
    await expectNoHorizontalScroll(page)
  })
})
