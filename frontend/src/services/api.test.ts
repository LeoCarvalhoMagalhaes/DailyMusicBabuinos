import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, setApiToken, setPlayerRejectedHandler } from './api'

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('token do jogador', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    setPlayerRejectedHandler(null)
    setApiToken(null)
  })

  it('usa o token salvo direto e, se o servidor recusar, renova e repete a chamada uma vez', async () => {
    setApiToken('token-antigo')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, { error: { code: 'invalid_player', message: 'x' } }))
      .mockResolvedValueOnce(json(200, { categories: [] }))
    vi.stubGlobal('fetch', fetchMock)
    const renew = vi.fn(async () => {
      setApiToken('token-novo')
      return true
    })
    setPlayerRejectedHandler(renew)

    await expect(api.daily()).resolves.toEqual({ categories: [] })
    expect(renew).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const retryHeaders = fetchMock.mock.calls[1][1].headers as Record<string, string>
    expect(retryHeaders.Authorization).toBe('Bearer token-novo')
  })

  it('não tenta renovar nas rotas do multiplayer (token da conta)', async () => {
    setApiToken('token-do-jogador')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(401, { error: { code: 'login_required', message: 'x' } })))
    const renew = vi.fn(async () => true)
    setPlayerRejectedHandler(renew)
    await expect(api.account()).rejects.toMatchObject({ status: 401, code: 'login_required' })
    expect(renew).not.toHaveBeenCalled()
  })
})
