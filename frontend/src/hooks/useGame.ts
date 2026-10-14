// Estado da partida. Toda regra (tentativas, acerto, pontos) é decidida pelo backend;
// aqui só refletimos a resposta e evitamos envios duplicados.

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../services/api'
import type { CategorySlug, GameState } from '../types/api'

export type Feedback =
  | { kind: 'wrong'; text: string }
  | { kind: 'skip' }
  | { kind: 'correct' }
  | { kind: 'info'; text: string }
  | { kind: 'error'; text: string }

export interface UseGame {
  game: GameState | null
  loading: boolean
  error: ApiError | null
  submitting: boolean
  feedback: Feedback | null
  reload: () => void
  guess: (text: string) => Promise<boolean>
  skip: () => Promise<void>
  clearFeedback: () => void
}

export interface GameMoves {
  submitting: boolean
  feedback: Feedback | null
  guess: (text: string) => Promise<boolean>
  skip: () => Promise<void>
  clearFeedback: () => void
  resetFeedback: () => void
}

/**
 * Palpite e pulo de uma partida solo (diário ou ilimitado): mesma regra nos dois modos.
 * Envia o número da tentativa esperada e trata reenvios e partidas já encerradas.
 */
export function useGameMoves(
  game: GameState | null,
  setGame: (game: GameState) => void,
): GameMoves {
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const inFlight = useRef(false)

  const refresh = useCallback(
    async (id: string) => {
      try {
        setGame(await api.game(id))
      } catch {
        /* mantém o estado atual */
      }
    },
    [setGame],
  )

  const handleError = useCallback(
    async (err: unknown, id: string) => {
      if (!(err instanceof ApiError)) {
        setFeedback({ kind: 'error', text: 'Algo deu errado. Tente de novo.' })
        return
      }
      if (err.code === 'attempt_mismatch' || err.code === 'game_finished') {
        // Outra aba ou um reenvio já registrou esta jogada: sincroniza com o servidor.
        await refresh(id)
        setFeedback({ kind: 'info', text: err.message })
        return
      }
      setFeedback({
        kind: err.code === 'duplicate_guess' || err.code === 'empty_guess' ? 'info' : 'error',
        text: err.message,
      })
    },
    [refresh],
  )

  const guess = useCallback(
    async (text: string): Promise<boolean> => {
      if (!game || game.status !== 'in_progress' || inFlight.current) return false
      const trimmed = text.trim()
      if (!trimmed) {
        setFeedback({ kind: 'info', text: 'Digite o nome de uma música.' })
        return false
      }
      inFlight.current = true
      setSubmitting(true)
      try {
        const result = await api.guess(game.id, trimmed, game.attempts_used + 1)
        setGame(result.game)
        setFeedback(result.correct ? { kind: 'correct' } : { kind: 'wrong', text: trimmed })
        return true
      } catch (err) {
        await handleError(err, game.id)
        return false
      } finally {
        inFlight.current = false
        setSubmitting(false)
      }
    },
    [game, handleError, setGame],
  )

  const skip = useCallback(async () => {
    if (!game || game.status !== 'in_progress' || inFlight.current) return
    inFlight.current = true
    setSubmitting(true)
    try {
      setGame(await api.skip(game.id, game.attempts_used + 1))
      setFeedback({ kind: 'skip' })
    } catch (err) {
      await handleError(err, game.id)
    } finally {
      inFlight.current = false
      setSubmitting(false)
    }
  }, [game, handleError, setGame])

  const clearFeedback = useCallback(() => setFeedback(null), [])
  return { submitting, feedback, guess, skip, clearFeedback, resetFeedback: clearFeedback }
}

export function useGame(category: CategorySlug, enabled: boolean): UseGame {
  const [game, setGame] = useState<GameState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const moves = useGameMoves(game, setGame)
  const { resetFeedback } = moves

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    setLoading(true)
    setError(null)
    resetFeedback()
    api
      .startGame(category)
      .then((state) => !cancelled && setGame(state))
      .catch((err: ApiError) => !cancelled && setError(err))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [category, enabled, reloadKey, resetFeedback])

  return {
    game,
    loading,
    error,
    submitting: moves.submitting,
    feedback: moves.feedback,
    reload: () => setReloadKey((n) => n + 1),
    guess: moves.guess,
    skip: moves.skip,
    clearFeedback: moves.clearFeedback,
  }
}
