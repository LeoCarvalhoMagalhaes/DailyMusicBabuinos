// Acesso seguro ao localStorage: pode estar bloqueado (modo privado, políticas do navegador).

export function readJSON<T>(key: string): T | null {
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

export function writeJSON(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* armazenamento indisponível: seguimos sem cache local */
  }
}

export function readString(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeString(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* ignorado */
  }
}

export function removeKey(key: string): void {
  try {
    window.localStorage.removeItem(key)
  } catch {
    /* ignorado */
  }
}

export const STORAGE_KEYS = {
  token: 'mb.player-token',
  stats: 'mb.stats-cache',
  volume: 'mb.volume',
  seenRules: 'mb.seen-rules',
  accountToken: 'mb.account-token',
  endlessRuns: 'mb.endless-runs',
} as const
