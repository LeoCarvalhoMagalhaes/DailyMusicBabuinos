import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '../services/api'
import type { DailyOverview } from '../types/api'

export function useDaily(enabled: boolean) {
  const [data, setData] = useState<DailyOverview | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [key, setKey] = useState(0)

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    setLoading(true)
    api
      .daily(controller.signal)
      .then((overview) => {
        setData(overview)
        setError(null)
      })
      .catch((err) => {
        if ((err as Error).name !== 'AbortError') setError(err as ApiError)
      })
      .finally(() => !controller.signal.aborted && setLoading(false))
    return () => controller.abort()
  }, [enabled, key])

  // Atualiza ao voltar para a aba (pode ter virado o dia ou jogado em outra aba).
  useEffect(() => {
    const onVisible = () => document.visibilityState === 'visible' && setKey((n) => n + 1)
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [])

  const reload = useCallback(() => setKey((n) => n + 1), [])
  return { data, error, loading, reload }
}
