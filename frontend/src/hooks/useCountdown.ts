import { useEffect, useRef, useState } from 'react'

/**
 * Contagem regressiva até `targetIso`, corrigida pelo relógio do servidor
 * (`serverTimeIso`) para não depender do horário do aparelho.
 */
export function useCountdown(targetIso: string | null, serverTimeIso?: string | null,
                             onExpire?: () => void): number {
  const offsetRef = useRef(0)
  const expiredRef = useRef(false)
  const onExpireRef = useRef(onExpire)
  onExpireRef.current = onExpire
  const [remaining, setRemaining] = useState(0)

  useEffect(() => {
    offsetRef.current = serverTimeIso ? new Date(serverTimeIso).getTime() - Date.now() : 0
  }, [serverTimeIso])

  useEffect(() => {
    if (!targetIso) return
    expiredRef.current = false
    const target = new Date(targetIso).getTime()
    const update = () => {
      const left = target - (Date.now() + offsetRef.current)
      setRemaining(Math.max(0, left))
      if (left <= 0 && !expiredRef.current) {
        expiredRef.current = true
        onExpireRef.current?.()
      }
    }
    update()
    const id = window.setInterval(update, 1000)
    return () => window.clearInterval(id)
  }, [targetIso])

  return remaining
}
