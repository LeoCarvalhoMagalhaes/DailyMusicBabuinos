// Identidade anônima do jogador: um token aleatório guardado no aparelho.
// Sem nome, e-mail ou senha. Apagar os dados do site cria um novo jogador.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, api, setApiToken } from '../services/api'
import { STORAGE_KEYS, readString, removeKey, writeString } from '../services/storage'

interface PlayerContextValue {
  ready: boolean
  error: ApiError | null
  retry: () => void
}

const PlayerContext = createContext<PlayerContextValue | null>(null)

// Uma única identificação por carregamento da página, mesmo que o efeito rode duas
// vezes (StrictMode) ou várias telas peçam ao mesmo tempo: evita criar dois jogadores.
let pendingIdentity: Promise<void> | null = null

function ensurePlayer(): Promise<void> {
  pendingIdentity ??= identify().catch((error: unknown) => {
    pendingIdentity = null // permite tentar de novo
    throw error
  })
  return pendingIdentity
}

async function identify(): Promise<void> {
  const saved = readString(STORAGE_KEYS.token)
  if (saved) {
    setApiToken(saved)
    try {
      await api.me()
      return
    } catch (error) {
      // Token desconhecido pelo servidor (ex.: banco recriado): gera um novo.
      if (!(error instanceof ApiError) || error.status !== 401) throw error
      removeKey(STORAGE_KEYS.token)
      setApiToken(null)
    }
  }
  const created = await api.createPlayer()
  writeString(STORAGE_KEYS.token, created.token)
  setApiToken(created.token)
}

export function PlayerProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setError(null)
    ensurePlayer()
      .then(() => !cancelled && setReady(true))
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err : new ApiError(0, 'unknown', String(err)))
      })
    return () => {
      cancelled = true
    }
  }, [attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  const value = useMemo(() => ({ ready, error, retry }), [ready, error, retry])
  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>
}

export function usePlayer(): PlayerContextValue {
  const ctx = useContext(PlayerContext)
  if (!ctx) throw new Error('usePlayer precisa de <PlayerProvider>')
  return ctx
}
