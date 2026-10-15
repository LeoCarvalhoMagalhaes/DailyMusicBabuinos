// Texto de compartilhamento: mostra o desempenho sem revelar a música.

import type { GameState } from '../types/api'
import { CATEGORY_THEMES } from './categories'

export const SITE_URL = import.meta.env.VITE_PUBLIC_SITE_URL ?? ''

/** Endereço do jogo para o texto de compartilhamento. No GitHub Pages o site fica numa
 * subpasta (ex.: /DailyMusicBabuinos/), então a origem sozinha não basta. */
export function siteUrl(): string {
  return SITE_URL || new URL(import.meta.env.BASE_URL, window.location.origin).href
}

/** Uma célula por tentativa: 🟥 erro, 🟨 artista certo, ⬜ pulou, 🟩 acerto, ⬛ não usada. */
export function resultGrid(game: Pick<GameState, 'guesses' | 'max_attempts'>): string {
  const cells: string[] = game.guesses.map((g) =>
    g.correct ? '🟩' : g.skipped ? '⬜' : g.same_artist ? '🟨' : '🟥',
  )
  while (cells.length < game.max_attempts) cells.push('⬛')
  return cells.join('')
}

export function shareText(game: GameState, siteUrl: string = SITE_URL): string {
  const theme = CATEGORY_THEMES[game.category.slug]
  const won = game.status === 'won'
  const lines = [
    `${theme.emoji} MÚSICAS BABUÍNAS — DESAFIO DIÁRIO #${game.challenge_number}`,
    `Categoria: ${theme.name.toUpperCase()}`,
    `Resultado: ${won ? 'ACERTEI!' : 'NÃO FOI DESSA VEZ'}`,
    won
      ? `Tentativa: ${game.attempts_used}/${game.max_attempts}`
      : `Tentativas: ${game.attempts_used}/${game.max_attempts}`,
    `Pontuação: ${game.score} ${game.score === 1 ? 'ponto' : 'pontos'}`,
    resultGrid(game),
    '',
    `${won ? theme.winSlogan : theme.loseSlogan} 🐒${theme.emoji}`,
    '#MusicasBabuinas',
  ]
  if (siteUrl) lines.push(siteUrl)
  return lines.join('\n')
}

export type ShareOutcome = 'shared' | 'copied' | 'cancelled' | 'failed'

export async function shareResult(text: string): Promise<ShareOutcome> {
  if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
    try {
      await navigator.share({ text })
      return 'shared'
    } catch (error) {
      if ((error as Error).name === 'AbortError') return 'cancelled'
      // Alguns navegadores recusam o share; caímos para a cópia.
    }
  }
  return (await copyText(text)) ? 'copied' : 'failed'
}

export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* tenta o método antigo abaixo */
  }
  try {
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(area)
    return ok
  } catch {
    return false
  }
}
