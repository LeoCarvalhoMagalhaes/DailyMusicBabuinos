// Efeitos de uma rodada, iguais nos três modos: pré-carrega o trecho liberado, toca a
// próxima pista depois de um erro ou pulo e a música inteira liberada depois do acerto.

import { useEffect } from 'react'
import type { GameState } from '../types/api'
import { playCorrect, playWrong } from '../utils/sfx'
import type { AudioPlayer } from './useAudioPlayer'
import type { Feedback } from './useGame'

export function useRoundEffects(game: GameState | null, feedback: Feedback | null, player: AudioPlayer) {
  // Baixa antecipadamente o trecho liberado: o play responde na hora.
  const { prefetch, play, volume } = player
  useEffect(() => {
    if (game) prefetch(game.unlocked_stage)
  }, [game, prefetch])

  // Reações sonoras e próxima pista tocando automaticamente após erro/pulo.
  useEffect(() => {
    if (!game || !feedback) return
    if (feedback.kind === 'wrong' || feedback.kind === 'skip') {
      if (feedback.kind === 'wrong') playWrong(volume)
      if (game.status === 'in_progress') void play(game.unlocked_stage)
    } else if (feedback.kind === 'correct') {
      playCorrect(volume)
      window.setTimeout(() => void play(game.max_attempts), 700)
    }
    // Só reage a um feedback novo (cada jogada gera um objeto novo).
  }, [feedback])
}
