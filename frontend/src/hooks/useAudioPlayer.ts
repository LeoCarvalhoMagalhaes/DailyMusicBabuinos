// Reprodução dos trechos. Totalmente separado da lógica de tentativas: falhas aqui
// nunca mexem na partida (o backend também não consome tentativas por áudio).

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../services/api'
import { STORAGE_KEYS, readJSON, writeJSON } from '../services/storage'

export type AudioStatus = 'idle' | 'loading' | 'playing' | 'paused' | 'error'

interface CachedClip {
  url: string
  duration: number
}

export interface AudioPlayer {
  status: AudioStatus
  stage: number | null
  position: number
  duration: number
  error: string | null
  volume: number
  volumeSupported: boolean
  play: (stage: number) => Promise<void>
  toggle: (stage: number) => Promise<void>
  stop: () => void
  setVolume: (value: number) => void
  prefetch: (stage: number) => void
}

function detectVolumeSupport(audio: HTMLAudioElement): boolean {
  // iOS ignora audio.volume (controle só pelo botão físico).
  try {
    const before = audio.volume
    audio.volume = 0.5
    const supported = Math.abs(audio.volume - 0.5) < 0.01
    audio.volume = before
    return supported
  } catch {
    return false
  }
}

export function useAudioPlayer(gameId: string | null): AudioPlayer {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const cacheRef = useRef(new Map<number, CachedClip>())
  const pendingRef = useRef(new Map<number, Promise<CachedClip>>())
  const rafRef = useRef<number>(0)
  const requestRef = useRef(0)
  const [status, setStatus] = useState<AudioStatus>('idle')
  const [stage, setStage] = useState<number | null>(null)
  const [position, setPosition] = useState(0)
  const [duration, setDuration] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [volume, setVolumeState] = useState(() => readJSON<number>(STORAGE_KEYS.volume) ?? 0.8)
  const [volumeSupported, setVolumeSupported] = useState(true)

  const audio = useCallback((): HTMLAudioElement => {
    if (!audioRef.current) {
      const el = new Audio()
      el.preload = 'auto'
      audioRef.current = el
      setVolumeSupported(detectVolumeSupport(el))
    }
    return audioRef.current
  }, [])

  const stopTicker = () => cancelAnimationFrame(rafRef.current)

  const tick = useCallback(() => {
    const el = audioRef.current
    if (el) setPosition(el.currentTime)
    rafRef.current = requestAnimationFrame(tick)
  }, [])

  // Troca de partida: limpa cache e para o áudio.
  useEffect(() => {
    const cache = cacheRef.current
    const pending = pendingRef.current
    return () => {
      stopTicker()
      audioRef.current?.pause()
      cache.forEach((clip) => URL.revokeObjectURL(clip.url))
      cache.clear()
      pending.clear()
    }
  }, [gameId])

  useEffect(() => {
    const el = audio()
    el.volume = volume
    writeJSON(STORAGE_KEYS.volume, volume)
  }, [audio, volume])

  useEffect(() => {
    const el = audio()
    const onEnded = () => {
      stopTicker()
      setPosition(el.duration || 0)
      setStatus('idle')
    }
    const onError = () => {
      stopTicker()
      setStatus('error')
      setError('Seu navegador não conseguiu tocar este trecho. Tente de novo.')
    }
    el.addEventListener('ended', onEnded)
    el.addEventListener('error', onError)
    return () => {
      el.removeEventListener('ended', onEnded)
      el.removeEventListener('error', onError)
    }
  }, [audio])

  const load = useCallback(
    (target: number): Promise<CachedClip> => {
      const cached = cacheRef.current.get(target)
      if (cached) return Promise.resolve(cached)
      const pending = pendingRef.current.get(target)
      if (pending) return pending
      if (!gameId) return Promise.reject(new ApiError(0, 'no_game', 'Partida não carregada.'))
      const promise = api
        .audio(gameId, target)
        .then(({ blob, duration: clipDuration }) => {
          const clip = { url: URL.createObjectURL(blob), duration: clipDuration }
          cacheRef.current.set(target, clip)
          return clip
        })
        .finally(() => pendingRef.current.delete(target))
      pendingRef.current.set(target, promise)
      return promise
    },
    [gameId],
  )

  const prefetch = useCallback(
    (target: number) => {
      load(target).catch(() => {
        /* o erro aparece quando o jogador apertar play */
      })
    },
    [load],
  )

  const stop = useCallback(() => {
    requestRef.current += 1
    stopTicker()
    const el = audioRef.current
    if (el) {
      el.pause()
      el.currentTime = 0
    }
    setPosition(0)
    setStatus('idle')
  }, [])

  const play = useCallback(
    async (target: number) => {
      const el = audio()
      const request = ++requestRef.current
      stopTicker()
      el.pause()
      setError(null)
      setStage(target)
      setPosition(0)
      const cached = cacheRef.current.get(target)
      if (!cached) setStatus('loading')
      try {
        const clip = cached ?? (await load(target))
        if (request !== requestRef.current) return
        if (el.src !== clip.url) el.src = clip.url
        el.currentTime = 0
        setDuration(clip.duration)
        await el.play()
        if (request !== requestRef.current) return
        setStatus('playing')
        rafRef.current = requestAnimationFrame(tick)
      } catch (err) {
        if (request !== requestRef.current) return
        stopTicker()
        setStatus('error')
        if (err instanceof ApiError) {
          setError(
            err.code === 'audio_unavailable'
              ? `${err.message} Sua tentativa não foi consumida.`
              : err.message,
          )
        } else if ((err as Error).name === 'NotAllowedError') {
          setError('O navegador bloqueou o som. Toque no botão de play novamente.')
        } else {
          setError('Não foi possível tocar o trecho. Tente de novo.')
        }
      }
    },
    [audio, load, tick],
  )

  const toggle = useCallback(
    async (target: number) => {
      const el = audio()
      if (status === 'playing' && stage === target) {
        el.pause()
        stopTicker()
        setStatus('paused')
        return
      }
      if (status === 'paused' && stage === target) {
        try {
          await el.play()
          setStatus('playing')
          rafRef.current = requestAnimationFrame(tick)
        } catch {
          await play(target)
        }
        return
      }
      await play(target)
    },
    [audio, play, stage, status, tick],
  )

  const setVolume = useCallback((value: number) => {
    setVolumeState(Math.min(1, Math.max(0, value)))
  }, [])

  return {
    status,
    stage,
    position,
    duration,
    error,
    volume,
    volumeSupported,
    play,
    toggle,
    stop,
    setVolume,
    prefetch,
  }
}
