// Falas do Babuíno do Rock durante uma rodada (comuns aos três modos).

import type { Feedback } from '../hooks/useGame'
import type { GameState } from '../types/api'

export function speech(
  game: GameState | null,
  feedback: Feedback | null,
  playing: boolean,
  lostLine = 'Ihhh, arrebentou a corda! Amanhã tem revanche.',
): string {
  if (!game) return 'Afinando a guitarra…'
  if (game.status === 'won') {
    return game.attempts_used === 1 ? 'DE PRIMEIRA?! Você é lenda! 🤘' : 'É ISSO! Que ouvido, hein? 🤘'
  }
  if (game.status === 'lost') return lostLine
  if (feedback?.kind === 'info' || feedback?.kind === 'error') return feedback.text
  if (feedback?.kind === 'wrong' && feedback.sameArtist) {
    return `Quase! “${feedback.text}” é do mesmo artista, mas não é essa. Escuta mais um pedaço!`
  }
  if (feedback?.kind === 'wrong' && game.remaining_attempts > 2) {
    return `Hmm… não é “${feedback.text}”. Escuta mais um pedaço!`
  }
  if (playing && !feedback) return 'Escuta só esse som…'
  if (game.remaining_attempts === 1) return 'Última chance! Tô roendo as unhas aqui…'
  if (game.guesses.length > 0 && game.remaining_attempts <= 2) {
    return `Só restam ${game.remaining_attempts} tentativas! Tô suando frio…`
  }
  if (feedback?.kind === 'skip') return 'Pulou? Beleza, lá vai mais um pedaço!'
  if (game.attempts_used === 0) return 'Aperte o play e me diga: que música é essa?'
  return 'Ouve de novo com calma e manda o palpite!'
}
