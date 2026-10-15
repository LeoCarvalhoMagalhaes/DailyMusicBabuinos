// Identidade anônima do jogador: um token aleatório guardado no aparelho.
// Sem nome, e-mail ou senha. Apagar os dados do site cria um novo jogador.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, api, setApiToken, setPlayerRejectedHandler } from '../services/api'
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
    // Usa o token salvo direto: sem a viagem extra de conferência a cada página.
    setApiToken(saved)
    return
  }
  await createIdentity()
}

async function createIdentity(): Promise<void> {
  const created = await api.createPlayer()
  writeString(STORAGE_KEYS.token, created.token)
  setApiToken(created.token)
}

// Token recusado pelo servidor (ex.: banco recriado): cria um jogador novo uma única
// vez, mesmo que várias chamadas tenham sido recusadas ao mesmo tempo.
let pendingRenewal: Promise<boolean> | null = null

setPlayerRejectedHandler(() => {
  pendingRenewal ??= (async () => {
    removeKey(STORAGE_KEYS.token)
    setApiToken(null)
    try {
      await createIdentity()
      return true
    } catch {
      return false
    } finally {
      window.setTimeout(() => (pendingRenewal = null), 0)
    }
  })()
  return pendingRenewal
})

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
