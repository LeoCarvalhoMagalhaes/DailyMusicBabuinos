// Sala multiplayer sincronizada em tempo real.
//
// - Ao abrir: entra na sala (ou reconecta, se já participa) e recebe o estado completo.
// - WebSocket: autentica na primeira mensagem e recebe o estado a cada mudança.
// - Sem WebSocket (rede instável, proxy): consulta o servidor a cada 3 s até reconectar.
// - Ações (pronto, iniciar, palpite, pular) vão por HTTP e devolvem o estado novo.
// O servidor decide tudo; o cliente só mostra o estado mais recente que recebeu.

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api, getAccountToken, realtimeUrl } from '../services/api'
import type { CategorySlug, RoomState } from '../types/api'
import type { Feedback } from './useGame'

export type Connection = 'connecting' | 'live' | 'polling'

export interface UseRoom {
  room: RoomState | null
  error: ApiError | null
  connection: Connection
  feedback: Feedback | null
  submitting: boolean
  setReady: (ready: boolean) => Promise<void>
  setOrder: (order: CategorySlug[]) => Promise<void>
  start: () => Promise<void>
  leave: () => Promise<void>
  guess: (text: string) => Promise<boolean>
  skip: () => Promise<void>
  refresh: () => Promise<void>
  clearFeedback: () => void
}

const POLL_MS = 3000
const PING_MS = 25_000

export function useRoom(code: string, enabled: boolean): UseRoom {
  const [room, setRoom] = useState<RoomState | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [connection, setConnection] = useState<Connection>('connecting')
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const inFlight = useRef(false)
  const roomRef = useRef<RoomState | null>(null)

  // Aceita o estado se não for mais antigo do que o que já temos.
  const apply = useCallback((next: RoomState) => {
    const current = roomRef.current
    if (current && current.id === next.id && next.version < current.version) return
    roomRef.current = next
    setRoom(next)
  }, [])

  const refresh = useCallback(async () => {
    try {
      apply(await api.room(code))
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 401)) setError(err)
    }
  }, [apply, code])

  // Entrada na sala (também serve de reconexão).
  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api
      .joinRoom(code)
      .then((state) => !cancelled && apply(state))
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err : new ApiError(0, 'unknown', String(err)))
      })
    return () => {
      cancelled = true
    }
  }, [enabled, code, apply])

  // WebSocket com reconexão e consulta periódica como reserva.
  const joined = !!room
  useEffect(() => {
    if (!enabled || !joined) return
    let socket: WebSocket | null = null
    let closed = false
    let retry = 0
    let reconnectTimer = 0
    let pingTimer = 0
    let pollTimer = 0

    const startPolling = () => {
      setConnection('polling')
      window.clearInterval(pollTimer)
      pollTimer = window.setInterval(() => void refresh(), POLL_MS)
    }

    const connect = () => {
      if (closed) return
      try {
        socket = new WebSocket(realtimeUrl())
      } catch {
        startPolling()
        return
      }
      socket.onopen = () => {
        socket?.send(JSON.stringify({ type: 'auth', token: getAccountToken(), room: code }))
      }
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(String(event.data))
          if (message.type === 'state') {
            retry = 0
            setConnection('live')
            window.clearInterval(pollTimer)
            apply(message.state as RoomState)
          }
        } catch {
          /* mensagem inválida: ignora */
        }
      }
      socket.onclose = () => {
        if (closed) return
        startPolling()
        retry += 1
        const delay = Math.min(10_000, 1000 * 2 ** Math.min(retry - 1, 4))
        reconnectTimer = window.setTimeout(connect, delay)
      }
      socket.onerror = () => socket?.close()
    }

    connect()
    pingTimer = window.setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ping' }))
    }, PING_MS)
    // Voltar para a aba: sincroniza na hora (o celular pode ter suspendido a conexão).
    const onVisible = () => document.visibilityState === 'visible' && void refresh()
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      closed = true
      window.clearTimeout(reconnectTimer)
      window.clearInterval(pingTimer)
      window.clearInterval(pollTimer)
      document.removeEventListener('visibilitychange', onVisible)
      socket?.close()
    }
  }, [enabled, joined, code, apply, refresh])

  const run = useCallback(
    async (action: () => Promise<RoomState | void>) => {
      if (inFlight.current) return
      inFlight.current = true
      setSubmitting(true)
      try {
        const state = await action()
        if (state) apply(state)
      } catch (err) {
        if (err instanceof ApiError) {
          const sync = ['round_closed', 'attempt_mismatch', 'game_finished', 'match_in_progress']
          if (sync.includes(err.code)) await refresh()
          const info = err.code === 'duplicate_guess' || err.code === 'empty_guess'
          setFeedback({ kind: info ? 'info' : 'error', text: err.message })
        } else {
          setFeedback({ kind: 'error', text: 'Algo deu errado. Tente de novo.' })
        }
      } finally {
        inFlight.current = false
        setSubmitting(false)
      }
    },
    [apply, refresh],
  )

  const guess = useCallback(
    async (text: string): Promise<boolean> => {
      const match = roomRef.current?.match
      const game = match?.my_game
      if (!match || !game || game.status !== 'in_progress') return false
      const trimmed = text.trim()
      if (!trimmed) {
        setFeedback({ kind: 'info', text: 'Digite o nome de uma música.' })
        return false
      }
      let accepted = false
      await run(async () => {
        const result = await api.matchGuess(code, match.current_round, game.attempts_used + 1, trimmed)
        accepted = true
        setFeedback(result.correct ? { kind: 'correct' } : { kind: 'wrong', text: trimmed })
        return result.state
      })
      return accepted
    },
    [code, run],
  )

  const skip = useCallback(async () => {
    const match = roomRef.current?.match
    const game = match?.my_game
    if (!match || !game || game.status !== 'in_progress') return
    await run(async () => {
      const state = await api.matchSkip(code, match.current_round, game.attempts_used + 1)
      setFeedback({ kind: 'skip' })
      return state
    })
  }, [code, run])

  return {
    room,
    error,
    connection,
    feedback,
    submitting,
    setReady: (ready) => run(() => api.setReady(code, ready)),
    setOrder: (order) => run(() => api.setOrder(code, order)),
    start: () => run(() => api.startMatch(code)),
    leave: () => run(() => api.leaveRoom(code)),
    guess,
    skip,
    refresh,
    clearFeedback: () => setFeedback(null),
  }
}
