import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { silentClipUrl, useAudioPlayer } from './useAudioPlayer'

const mocks = vi.hoisted(() => ({ audio: vi.fn() }))

vi.mock('../services/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../services/api')>()
  return { ...original, api: { ...original.api, ...mocks } }
})

describe('useAudioPlayer', () => {
  let srcAtPlay: string[]

  beforeEach(() => {
    vi.clearAllMocks()
    srcAtPlay = []
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(function (this: HTMLMediaElement) {
      srcAtPlay.push(this.src)
      return Promise.resolve()
    })
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
    URL.createObjectURL = vi.fn(() => 'blob:trecho-1')
    URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    cleanup() // desmonta (e pausa) antes de restaurar os mocks
    vi.restoreAllMocks()
  })

  it('libera o áudio no próprio toque quando o trecho ainda está baixando (iOS)', async () => {
    let finishDownload!: (value: { blob: Blob; duration: number }) => void
    mocks.audio.mockReturnValue(new Promise((resolve) => (finishDownload = resolve)))
    const { result } = renderHook(() => useAudioPlayer('partida-1'))

    let playing!: Promise<void>
    act(() => {
      playing = result.current.play(1)
    })
    // Ainda dentro do toque: já houve um play() (som mudo), antes do download terminar.
    expect(srcAtPlay).toEqual([silentClipUrl()])
    expect(result.current.status).toBe('loading')

    await act(async () => {
      finishDownload({ blob: new Blob(['x'], { type: 'audio/mpeg' }), duration: 1 })
      await playing
    })
    expect(srcAtPlay).toEqual([silentClipUrl(), 'blob:trecho-1'])
    expect(result.current.status).toBe('playing')
  })

  it('com o trecho já em cache, toca direto sem o som mudo', async () => {
    mocks.audio.mockResolvedValue({ blob: new Blob(['x']), duration: 1 })
    const { result } = renderHook(() => useAudioPlayer('partida-2'))
    await act(async () => {
      result.current.prefetch(1)
      await Promise.resolve()
    })
    await act(async () => {
      await result.current.play(1)
    })
    expect(srcAtPlay).toEqual(['blob:trecho-1'])
  })

  it('o som mudo é um WAV válido e curto', () => {
    const url = silentClipUrl()
    expect(url.startsWith('data:audio/wav;base64,')).toBe(true)
    const bytes = atob(url.split(',')[1])
    expect(bytes.slice(0, 4)).toBe('RIFF')
    expect(bytes.slice(8, 12)).toBe('WAVE')
    expect(bytes.length).toBe(44 + 80)
  })
})
