// Cliente HTTP da API. O token anônimo do jogador vai no cabeçalho Authorization; nas
// rotas do multiplayer vai o token da conta (login), guardado à parte.

import type {
  Account,
  AuthResult,
  CategorySlug,
  DailyOverview,
  EndlessRound,
  EndlessStats,
  GameState,
  GuessResult,
  HistoryPage,
  PlayerCreated,
  RoomState,
  RunSummary,
  SongSuggestion,
  Statistics,
} from '../types/api'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }

  get isNetwork(): boolean {
    return this.status === 0
  }
}

let token: string | null = null
let accountToken: string | null = null

export function setApiToken(value: string | null): void {
  token = value
}

export function setAccountToken(value: string | null): void {
  accountToken = value
}

export function getAccountToken(): string | null {
  return accountToken
}

interface RequestOptions {
  method?: 'GET' | 'POST'
  body?: unknown
  signal?: AbortSignal
  auth?: boolean
  // Rotas do multiplayer: usam o token da conta em vez do jogador anônimo.
  account?: boolean
}

async function send(
  path: string,
  { method = 'GET', body, signal, auth = true, account = false }: RequestOptions,
) {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const bearer = account ? accountToken : token
  if (auth && bearer) headers.Authorization = `Bearer ${bearer}`
  try {
    return await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'Sem conexão com o palco. Verifique sua internet.')
  }
}

async function toError(response: Response): Promise<ApiError> {
  try {
    const payload = await response.json()
    if (payload?.error?.code) {
      return new ApiError(response.status, payload.error.code, payload.error.message)
    }
  } catch {
    /* corpo não-JSON */
  }
  return new ApiError(response.status, 'http_error', 'O servidor tropeçou no cabo. Tente de novo.')
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options)
  if (!response.ok) throw await toError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function clip(path: string, options: RequestOptions): Promise<AudioPayload> {
  const response = await send(path, options)
  if (!response.ok) throw await toError(response)
  const duration = Number(response.headers.get('X-Clip-Duration') ?? '0')
  return { blob: await response.blob(), duration }
}

/** Endereço do WebSocket do multiplayer (mesmo host da API; em dev, via proxy do Vite). */
export function realtimeUrl(): string {
  const base = BASE || window.location.origin
  return `${base.replace(/^http/, 'ws')}/api/mp/ws`
}

const mp = { account: true } as const

export interface AudioPayload {
  blob: Blob
  duration: number
}

export const api = {
  createPlayer: () => request<PlayerCreated>('/api/players', { method: 'POST', auth: false }),
  me: () => request<{ player_id: string; created_at: string }>('/api/players/me'),
  daily: (signal?: AbortSignal) => request<DailyOverview>('/api/daily', { signal }),
  startGame: (category: CategorySlug) =>
    request<GameState>('/api/games/start', { method: 'POST', body: { category } }),
  game: (id: string) => request<GameState>(`/api/games/${id}`),
  guess: (id: string, guess: string, attempt: number) =>
    request<GuessResult>(`/api/games/${id}/guess`, { method: 'POST', body: { guess, attempt } }),
  skip: (id: string, attempt: number) =>
    request<GameState>(`/api/games/${id}/skip`, { method: 'POST', body: { attempt } }),
  search: (q: string, signal?: AbortSignal) =>
    request<SongSuggestion[]>(`/api/songs/search?q=${encodeURIComponent(q)}`, { signal }),
  statistics: () => request<Statistics>('/api/statistics'),
  history: (limit = 30, offset = 0) =>
    request<HistoryPage>(`/api/history?limit=${limit}&offset=${offset}`),
  audio: (id: string, stage: number, signal?: AbortSignal) =>
    clip(`/api/games/${id}/audio?stage=${stage}`, { signal }),

  // Modo ilimitado (palpite, pulo e áudio usam as rotas de partida acima).
  endlessNext: (category: CategorySlug, runId: string | null) =>
    request<EndlessRound>('/api/endless/next', { method: 'POST', body: { category, run_id: runId } }),
  endlessRun: (runId: string) => request<RunSummary>(`/api/endless/runs/${runId}`),
  endlessStats: () => request<EndlessStats>('/api/endless/stats'),

  // Multiplayer.
  register: (username: string, password: string, displayName: string) =>
    request<AuthResult>('/api/auth/register', {
      method: 'POST',
      auth: false,
      body: { username, password, display_name: displayName },
    }),
  login: (username: string, password: string) =>
    request<AuthResult>('/api/auth/login', { method: 'POST', auth: false, body: { username, password } }),
  logout: () => request<void>('/api/auth/logout', { method: 'POST', ...mp }),
  account: () => request<Account>('/api/auth/me', mp),
  createRoom: (order: CategorySlug[] | null) =>
    request<RoomState>('/api/mp/rooms', { method: 'POST', body: { category_order: order }, ...mp }),
  joinRoom: (code: string) =>
    request<RoomState>('/api/mp/rooms/join', { method: 'POST', body: { code }, ...mp }),
  room: (code: string, signal?: AbortSignal) =>
    request<RoomState>(`/api/mp/rooms/${code}`, { signal, ...mp }),
  setReady: (code: string, ready: boolean) =>
    request<RoomState>(`/api/mp/rooms/${code}/ready`, { method: 'POST', body: { ready }, ...mp }),
  setOrder: (code: string, order: CategorySlug[]) =>
    request<RoomState>(`/api/mp/rooms/${code}/order`, {
      method: 'POST',
      body: { category_order: order },
      ...mp,
    }),
  startMatch: (code: string) => request<RoomState>(`/api/mp/rooms/${code}/start`, { method: 'POST', ...mp }),
  leaveRoom: (code: string) => request<void>(`/api/mp/rooms/${code}/leave`, { method: 'POST', ...mp }),
  matchGuess: (code: string, round: number, attempt: number, guess: string) =>
    request<{ correct: boolean; state: RoomState }>(`/api/mp/rooms/${code}/guess`, {
      method: 'POST',
      body: { round, attempt, guess },
      ...mp,
    }),
  matchSkip: (code: string, round: number, attempt: number) =>
    request<RoomState>(`/api/mp/rooms/${code}/skip`, { method: 'POST', body: { round, attempt }, ...mp }),
  matchAudio: (code: string, round: number, stage: number, signal?: AbortSignal) =>
    clip(`/api/mp/rooms/${code}/rounds/${round}/audio?stage=${stage}`, { signal, ...mp }),
}
