// Conta do multiplayer. O token de login fica no aparelho e é validado no servidor;
// é separado do jogador anônimo do desafio diário e do modo ilimitado.

import { useCallback, useEffect, useState } from 'react'
import { ApiError, api, setAccountToken } from '../services/api'
import { STORAGE_KEYS, readString, removeKey, writeString } from '../services/storage'
import type { Account } from '../types/api'

export interface UseAccount {
  account: Account | null
  checking: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string, displayName: string) => Promise<void>
  logout: () => Promise<void>
}

export function useAccount(): UseAccount {
  const [account, setAccount] = useState<Account | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    const saved = readString(STORAGE_KEYS.accountToken)
    if (!saved) {
      setChecking(false)
      return
    }
    setAccountToken(saved)
    let cancelled = false
    api
      .account()
      .then((me) => !cancelled && setAccount(me))
      .catch((err: unknown) => {
        // Sessão vencida ou encerrada: volta para o login.
        if (err instanceof ApiError && err.status === 401) {
          removeKey(STORAGE_KEYS.accountToken)
          setAccountToken(null)
        }
      })
      .finally(() => !cancelled && setChecking(false))
    return () => {
      cancelled = true
    }
  }, [])

  const keep = useCallback((token: string, me: Account) => {
    writeString(STORAGE_KEYS.accountToken, token)
    setAccountToken(token)
    setAccount(me)
  }, [])

  const login = useCallback(
    async (username: string, password: string) => {
      const result = await api.login(username, password)
      keep(result.token, result.account)
    },
    [keep],
  )

  const register = useCallback(
    async (username: string, password: string, displayName: string) => {
      const result = await api.register(username, password, displayName)
      keep(result.token, result.account)
    },
    [keep],
  )

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      /* sai localmente mesmo sem rede */
    }
    removeKey(STORAGE_KEYS.accountToken)
    setAccountToken(null)
    setAccount(null)
  }, [])

  return { account, checking, login, register, logout }
}
