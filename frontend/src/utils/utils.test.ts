import { afterEach, describe, expect, it, vi } from 'vitest'
import { WON_GAME, makeGame } from '../test/fixtures'
import { formatChallengeDate, formatCountdown, formatSeconds, formatShortDate } from './format'
import { moodForGame } from './mascot'
import { resultGrid, shareResult, shareText, siteUrl } from './share'

describe('compartilhamento', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('monta a grade sem revelar a música', () => {
    expect(resultGrid(WON_GAME)).toBe('🟥🟩⬛⬛⬛⬛')
    const text = shareText(WON_GAME, 'https://musicasbabuinas.example')
    expect(text).toContain('🎸 MÚSICAS BABUÍNAS — DESAFIO DIÁRIO #1')
    expect(text).toContain('Categoria: ROCK')
    expect(text).toContain('Resultado: ACERTEI!')
    expect(text).toContain('Tentativa: 2/6')
    expect(text).toContain('Pontuação: 80 pontos')
    expect(text).toContain('Rock não se adivinha. Se sente! 🐒🎸')
    expect(text).toContain('#MusicasBabuinas')
    expect(text).not.toContain('Bohemian')
    expect(text).not.toContain('Queen')
    expect(text).not.toContain('Hey Jude')
  })

  it('adapta o texto para derrota e categoria', () => {
    const lost = makeGame({
      category: { slug: 'country', name: 'Country', description: '' },
      status: 'lost',
      attempts_used: 6,
      remaining_attempts: 0,
      guesses: Array.from({ length: 6 }, (_, i) => ({
        attempt: i + 1,
        text: i % 2 ? '' : 'Jolene',
        skipped: i % 2 === 1,
        correct: false,
      })),
    })
    const text = shareText(lost, '')
    expect(text).toContain('🤠 MÚSICAS BABUÍNAS')
    expect(text).toContain('Resultado: NÃO FOI DESSA VEZ')
    expect(text).toContain('Pontuação: 0 pontos')
    expect(text).toContain('🟥⬜🟥⬜🟥⬜')
    expect(text).not.toContain('Jolene')
  })

  it('usa a Web Share API quando existe', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { ...navigator, share })
    await expect(shareResult('oi')).resolves.toBe('shared')
    expect(share).toHaveBeenCalledWith({ text: 'oi' })
  })

  it('cai para a área de transferência sem Web Share', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    await expect(shareResult('texto')).resolves.toBe('copied')
    expect(writeText).toHaveBeenCalledWith('texto')
  })

  it('respeita o cancelamento do compartilhamento', async () => {
    const share = vi.fn().mockRejectedValue(Object.assign(new Error('x'), { name: 'AbortError' }))
    vi.stubGlobal('navigator', { share })
    await expect(shareResult('texto')).resolves.toBe('cancelled')
  })
})

describe('formatação', () => {
  it('formata contagem regressiva', () => {
    expect(formatCountdown(0)).toBe('00:00:00')
    expect(formatCountdown(3_723_000)).toBe('01:02:03')
    expect(formatCountdown(-5)).toBe('00:00:00')
  })

  it('formata datas do desafio sem depender do fuso do aparelho', () => {
    expect(formatChallengeDate('2026-10-14')).toBe('Quarta-feira, 14 de outubro')
    expect(formatShortDate('2026-01-02')).toBe('02/01/2026')
  })

  it('formata segundos', () => {
    expect(formatSeconds(1)).toBe('1s')
    expect(formatSeconds(1.5)).toBe('1.5s')
  })
})

describe('humor do mascote', () => {
  it('reage ao andamento da partida', () => {
    expect(moodForGame(null, false)).toBe('idle')
    expect(moodForGame(makeGame(), false)).toBe('idle')
    expect(moodForGame(makeGame(), true)).toBe('listening')
    const wrong = makeGame({
      guesses: [{ attempt: 1, text: 'x', skipped: false, correct: false }],
      remaining_attempts: 5,
    })
    expect(moodForGame(wrong, false)).toBe('doubt')
    expect(moodForGame({ ...wrong, remaining_attempts: 2 }, false)).toBe('nervous')
    expect(moodForGame(WON_GAME, false)).toBe('win')
    expect(moodForGame(makeGame({ status: 'lost' }), false)).toBe('lose')
  })
})

describe('endereço do jogo no compartilhamento', () => {
  it('inclui a subpasta do site (GitHub Pages), não só a origem', () => {
    // Nos testes a base é "/"; no Pages, VITE_BASE_PATH=/DailyMusicBabuinos/.
    expect(siteUrl()).toBe(new URL(import.meta.env.BASE_URL, window.location.origin).href)
    expect(siteUrl().endsWith('/')).toBe(true)
  })
})
