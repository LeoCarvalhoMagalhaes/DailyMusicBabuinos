// Escolhe a expressão do Babuíno do Rock de acordo com o andamento da partida.

import type { GameState } from '../types/api'

export type MascotMood =
  | 'idle' // confiante, pronto para o desafio
  | 'listening' // curtindo o som
  | 'doubt' // acabou de errar
  | 'nervous' // poucas tentativas restantes
  | 'win' // acertou!
  | 'lose' // derrota engraçada
  | 'champion' // desafio concluído com vitória: pose de campeão

export const MOOD_LABELS: Record<MascotMood, string> = {
  idle: 'Babuíno do Rock confiante, pronto para o desafio',
  listening: 'Babuíno do Rock curtindo o som de olhos fechados',
  doubt: 'Babuíno do Rock com cara de dúvida',
  nervous: 'Babuíno do Rock suando frio',
  win: 'Babuíno do Rock comemorando com a guitarra',
  lose: 'Babuíno do Rock tonto, com uma corda da guitarra arrebentada',
  champion: 'Babuíno do Rock de óculos escuros fazendo o sinal do rock',
}

export function moodForGame(
  game: Pick<GameState, 'status' | 'guesses' | 'remaining_attempts'> | null,
  playing: boolean,
): MascotMood {
  if (!game) return 'idle'
  if (game.status === 'won') return 'win'
  if (game.status === 'lost') return 'lose'
  if (playing) return 'listening'
  if (game.guesses.length > 0 && game.remaining_attempts <= 2) return 'nervous'
  const last = game.guesses[game.guesses.length - 1]
  if (last && !last.correct) return 'doubt'
  return 'idle'
}
