// Modo ilimitado: rodadas solo em sequência, com placar da sessão. O servidor sorteia
// as músicas; aqui só pedimos a próxima e reaproveitamos palpite e pulo do diário.

import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '../services/api'
import { STORAGE_KEYS, readJSON, writeJSON } from '../services/storage'
import type { CategorySlug, GameState, RunSummary } from '../types/api'
import { useGameMoves } from './useGame'
import type { GameMoves } from './useGame'

type RunIds = Partial<Record<CategorySlug, string>>

function savedRun(category: CategorySlug): string | null {
  return readJSON<RunIds>(STORAGE_KEYS.endlessRuns)?.[category] ?? null
}

function saveRun(category: CategorySlug, runId: string | null): void {
  const runs = readJSON<RunIds>(STORAGE_KEYS.endlessRuns) ?? {}
  if (runId) runs[category] = runId
  else delete runs[category]
  writeJSON(STORAGE_KEYS.endlessRuns, runs)
}

export interface UseEndless extends GameMoves {
  game: GameState | null
  run: RunSummary | null
  loading: boolean
  error: ApiError | null
  next: () => Promise<void>
  newSession: () => Promise<void>
}

export function useEndless(category: CategorySlug, enabled: boolean): UseEndless {
  const [game, setGame] = useState<GameState | null>(null)
  const [run, setRun] = useState<RunSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const moves = useGameMoves(game, setGame)
  const { resetFeedback } = moves

  const load = useCallback(
    async (runId: string | null) => {
      setLoading(true)
      setError(null)
      resetFeedback()
      try {
        const round = await api.endlessNext(category, runId)
        setGame(round.game)
        setRun(round.run)
        saveRun(category, round.run.run_id)
      } catch (err) {
        setError(err instanceof ApiError ? err : new ApiError(0, 'unknown', String(err)))
      } finally {
        setLoading(false)
      }
    },
    [category, resetFeedback],
  )

  useEffect(() => {
    if (enabled) void load(savedRun(category))
  }, [enabled, category, load])

  // Ao terminar a rodada, atualiza o placar da sessão (acertos, pontos e sequência).
  const finished = !!game && game.status !== 'in_progress'
  const runId = run?.run_id
  useEffect(() => {
    if (!finished || !runId) return
    api
      .endlessRun(runId)
      .then(setRun)
      .catch(() => {
        /* o placar se atualiza na próxima rodada */
      })
  }, [finished, runId])

  return {
    ...moves,
    game,
    run,
    loading,
    error,
    next: () => load(run?.run_id ?? savedRun(category)),
    newSession: async () => {
      saveRun(category, null)
      await load(null)
    },
  }
}
