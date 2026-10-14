// Cliente HTTP da API. O token anônimo do jogador vai no cabeçalho Authorization.

import type {
  CategorySlug,
  DailyOverview,
  GameState,
  GuessResult,
  HistoryPage,
  PlayerCreated,
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

export function setApiToken(value: string | null): void {
  token = value
}

interface RequestOptions {
  method?: 'GET' | 'POST'
  body?: unknown
  signal?: AbortSignal
  auth?: boolean
}

async function send(path: string, { method = 'GET', body, signal, auth = true }: RequestOptions) {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && token) headers.Authorization = `Bearer ${token}`
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
  return (await response.json()) as T
}

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
  async audio(id: string, stage: number, signal?: AbortSignal): Promise<AudioPayload> {
    const response = await send(`/api/games/${id}/audio?stage=${stage}`, { signal })
    if (!response.ok) throw await toError(response)
    const duration = Number(response.headers.get('X-Clip-Duration') ?? '0')
    return { blob: await response.blob(), duration }
  },
}
