import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../services/api'
import { makeGame } from '../test/fixtures'
import { useGame } from './useGame'

const mocks = vi.hoisted(() => ({
  startGame: vi.fn(),
  guess: vi.fn(),
  skip: vi.fn(),
  game: vi.fn(),
}))

vi.mock('../services/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../services/api')>()
  return { ...original, api: { ...original.api, ...mocks } }
})

describe('useGame', () => {
  it('avisa quando o palpite errado é do mesmo artista', async () => {
    mocks.startGame.mockResolvedValue(makeGame())
    mocks.guess.mockResolvedValue({
      correct: false,
      game: makeGame({
        attempts_used: 1,
        remaining_attempts: 5,
        unlocked_stage: 2,
        guesses: [{ attempt: 1, text: 'We Will Rock You', skipped: false, correct: false, same_artist: true }],
      }),
    })
    const { result } = renderHook(() => useGame('rock', true))
    await waitFor(() => expect(result.current.game).not.toBeNull())
    await act(async () => {
      await result.current.guess('We Will Rock You')
    })
    expect(result.current.feedback).toEqual({ kind: 'wrong', text: 'We Will Rock You', sameArtist: true })
  })

  beforeEach(() => vi.clearAllMocks())

  it('envia a tentativa esperada e atualiza com a resposta do servidor', async () => {
    mocks.startGame.mockResolvedValue(makeGame())
    const after = makeGame({
      attempts_used: 1,
      remaining_attempts: 5,
      unlocked_stage: 2,
      guesses: [{ attempt: 1, text: 'Hey Jude', skipped: false, correct: false }],
    })
    mocks.guess.mockResolvedValue({ correct: false, game: after })
    const { result } = renderHook(() => useGame('rock', true))
    await waitFor(() => expect(result.current.game).not.toBeNull())
    await act(async () => {
      await result.current.guess('  Hey Jude ')
    })
    expect(mocks.guess).toHaveBeenCalledWith(after.id, 'Hey Jude', 1)
    expect(result.current.game?.unlocked_stage).toBe(2)
    expect(result.current.feedback).toEqual({ kind: 'wrong', text: 'Hey Jude', sameArtist: false })
  })

  it('ignora cliques duplos enquanto um palpite está em andamento', async () => {
    mocks.startGame.mockResolvedValue(makeGame())
    let resolve!: (v: unknown) => void
    mocks.guess.mockReturnValue(new Promise((r) => (resolve = r)))
    const { result } = renderHook(() => useGame('rock', true))
    await waitFor(() => expect(result.current.game).not.toBeNull())
    let first!: Promise<boolean>
    act(() => {
      first = result.current.guess('A')
      void result.current.guess('B')
    })
    expect(mocks.guess).toHaveBeenCalledTimes(1)
    await act(async () => {
      resolve({ correct: true, game: makeGame({ status: 'won', score: 100 }) })
      await first
    })
    expect(result.current.feedback).toEqual({ kind: 'correct' })
  })

  it('sincroniza com o servidor quando a tentativa já foi registrada', async () => {
    mocks.startGame.mockResolvedValue(makeGame())
    mocks.guess.mockRejectedValue(new ApiError(409, 'attempt_mismatch', 'Já registrada.'))
    const synced = makeGame({ attempts_used: 1, remaining_attempts: 5 })
    mocks.game.mockResolvedValue(synced)
    const { result } = renderHook(() => useGame('rock', true))
    await waitFor(() => expect(result.current.game).not.toBeNull())
    await act(async () => {
      await result.current.guess('X')
    })
    expect(mocks.game).toHaveBeenCalled()
    expect(result.current.game?.attempts_used).toBe(1)
    expect(result.current.feedback?.kind).toBe('info')
  })

  it('mostra aviso de palpite repetido sem alterar a partida', async () => {
    const state = makeGame()
    mocks.startGame.mockResolvedValue(state)
    mocks.guess.mockRejectedValue(new ApiError(409, 'duplicate_guess', 'Você já tentou essa!'))
    const { result } = renderHook(() => useGame('rock', true))
    await waitFor(() => expect(result.current.game).not.toBeNull())
    await act(async () => {
      expect(await result.current.guess('X')).toBe(false)
    })
    expect(result.current.feedback).toEqual({ kind: 'info', text: 'Você já tentou essa!' })
    expect(result.current.game).toEqual(state)
  })

  it('expõe erro de carregamento', async () => {
    mocks.startGame.mockRejectedValue(new ApiError(0, 'network_error', 'Sem conexão'))
    const { result } = renderHook(() => useGame('rock', true))
    await waitFor(() => expect(result.current.error?.code).toBe('network_error'))
  })
})
