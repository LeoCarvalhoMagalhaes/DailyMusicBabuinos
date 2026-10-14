const DATE_FMT = new Intl.DateTimeFormat('pt-BR', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  timeZone: 'UTC',
})

const SHORT_DATE_FMT = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: 'UTC',
})

/** Datas de desafio chegam como "AAAA-MM-DD" (dia no fuso do jogo). */
export function formatChallengeDate(isoDate: string): string {
  const text = DATE_FMT.format(new Date(`${isoDate}T12:00:00Z`))
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function formatShortDate(isoDate: string): string {
  return SHORT_DATE_FMT.format(new Date(`${isoDate}T12:00:00Z`))
}

export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return [h, m, s].map((n) => String(n).padStart(2, '0')).join(':')
}

export function formatSeconds(value: number): string {
  return `${Number.isInteger(value) ? value : value.toFixed(1)}s`
}

export function formatPercent(rate: number): string {
  return `${Math.round(rate * 100)}%`
}

export function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`
}
