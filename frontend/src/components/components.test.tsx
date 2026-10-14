import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { AudioPlayer as Player } from '../hooks/useAudioPlayer'
import { WON_GAME, makeGame } from '../test/fixtures'
import { Attempts } from './Attempts/Attempts'
import { AudioPlayer } from './AudioPlayer/AudioPlayer'
import { CategoryCard } from './CategoryCard/CategoryCard'
import { GuessInput } from './GuessInput/GuessInput'
import { Mascot } from './Mascot/Mascot'
import { ResultPanel } from './Result/ResultPanel'

const SUGGESTIONS = [
  { id: 'a', title: 'Bohemian Rhapsody', artist: 'Queen' },
  { id: 'b', title: 'Born to Run', artist: 'Bruce Springsteen' },
]

function renderInput(overrides: Partial<Parameters<typeof GuessInput>[0]> = {}) {
  const props = {
    disabled: false,
    submitting: false,
    canSkip: true,
    onGuess: vi.fn().mockResolvedValue(true),
    onSkip: vi.fn(),
    search: vi.fn().mockResolvedValue(SUGGESTIONS),
    ...overrides,
  }
  render(<GuessInput {...props} />)
  return props
}

describe('GuessInput', () => {
  it('mostra sugestões e permite escolher pelo teclado', async () => {
    const user = userEvent.setup()
    const props = renderInput()
    const input = screen.getByRole('combobox', { name: 'Título da música' })
    await user.type(input, 'bo')
    expect(await screen.findByRole('option', { name: /Bohemian Rhapsody/ })).toBeInTheDocument()
    expect(props.search).toHaveBeenCalledWith('bo', expect.any(AbortSignal))
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(input).toHaveValue('Born to Run')
    await user.keyboard('{Enter}')
    expect(props.onGuess).toHaveBeenCalledWith('Born to Run')
    await waitFor(() => expect(input).toHaveValue(''))
  })

  it('aceita texto livre e mantém o campo se o palpite falhar', async () => {
    const user = userEvent.setup()
    const props = renderInput({ onGuess: vi.fn().mockResolvedValue(false), search: vi.fn().mockResolvedValue([]) })
    const input = screen.getByRole('combobox')
    await user.type(input, 'musica inventada')
    expect(await screen.findByText(/Nenhuma música encontrada/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Confirmar/ }))
    expect(props.onGuess).toHaveBeenCalledWith('musica inventada')
    expect(input).toHaveValue('musica inventada')
  })

  it('bloqueia envio vazio, durante envio e permite pular', async () => {
    const user = userEvent.setup()
    const props = renderInput()
    expect(screen.getByRole('button', { name: /Confirmar/ })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: /Pular/ }))
    expect(props.onSkip).toHaveBeenCalledTimes(1)
  })

  it('desabilita tudo enquanto envia', () => {
    renderInput({ submitting: true })
    expect(screen.getByRole('button', { name: /Pular/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Confirmar/ })).toBeDisabled()
  })

  it('troca o pulo por desistir na última tentativa', () => {
    renderInput({ lastAttempt: true })
    expect(screen.getByRole('button', { name: /Desistir/ })).toBeInTheDocument()
  })
})

describe('Attempts', () => {
  it('mostra erros, pulos, acerto e vagas restantes', () => {
    const game = makeGame({
      guesses: [
        { attempt: 1, text: 'Hey Jude', skipped: false, correct: false },
        { attempt: 2, text: '', skipped: true, correct: false },
      ],
      remaining_attempts: 4,
    })
    render(<Attempts guesses={game.guesses} maxAttempts={6} inProgress />)
    expect(screen.getAllByRole('listitem')).toHaveLength(6)
    expect(screen.getByText('Hey Jude')).toBeInTheDocument()
    expect(screen.getByText('Pulou')).toBeInTheDocument()
    expect(screen.getByText('Sua vez — ouça e responda')).toBeInTheDocument()
    expect(screen.getByText(/restantes/).closest('p')).toHaveTextContent('4 restantes')
  })
})

function fakePlayer(overrides: Partial<Player> = {}): Player {
  return {
    status: 'idle',
    stage: null,
    position: 0,
    duration: 0,
    error: null,
    volume: 0.8,
    volumeSupported: true,
    play: vi.fn().mockResolvedValue(undefined),
    toggle: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn(),
    setVolume: vi.fn(),
    prefetch: vi.fn(),
    ...overrides,
  }
}

describe('AudioPlayer', () => {
  it('libera só os trechos desbloqueados', async () => {
    const user = userEvent.setup()
    const player = fakePlayer()
    render(<AudioPlayer player={player} stages={[1, 2, 3, 5, 8, 12]} unlocked={2} accent="#f43f5e" finished={false} />)
    expect(screen.getByText('Pista 2 de 6')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ouvir trecho 1 (1s)' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Trecho 3 bloqueado' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Tocar trecho 2' }))
    expect(player.toggle).toHaveBeenCalledWith(2)
    await user.click(screen.getByRole('button', { name: 'Ouvir trecho 1 (1s)' }))
    expect(player.play).toHaveBeenCalledWith(1)
  })

  it('mostra erro de áudio com opção de tentar de novo', async () => {
    const user = userEvent.setup()
    const player = fakePlayer({ status: 'error', stage: 1, error: 'Falhou. Sua tentativa não foi consumida.' })
    render(<AudioPlayer player={player} stages={[1, 2]} unlocked={1} accent="#000" finished={false} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Sua tentativa não foi consumida')
    await user.click(screen.getByRole('button', { name: /Tentar de novo/ }))
    expect(player.play).toHaveBeenCalledWith(1)
  })

  it('esconde o volume quando o aparelho não permite controlá-lo', () => {
    render(
      <AudioPlayer player={fakePlayer({ volumeSupported: false })} stages={[1]} unlocked={1} accent="#000" finished />,
    )
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
    expect(screen.getByText('Ouça de novo')).toBeInTheDocument()
  })
})

describe('ResultPanel', () => {
  it('revela a resposta e copia o resultado', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    render(<ResultPanel game={WON_GAME} />)
    expect(screen.getByText('Bohemian Rhapsody')).toBeInTheDocument()
    expect(screen.getByText('Queen')).toBeInTheDocument()
    expect(screen.getByText('80')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Ouvir a música completa/ })).toHaveAttribute(
      'href',
      'https://www.deezer.com/track/1',
    )
    await user.click(screen.getByRole('button', { name: /Compartilhar resultado/ }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Copiado/ })).toBeInTheDocument())
    expect(writeText.mock.calls[0][0]).toContain('Tentativa: 2/6')
    expect(writeText.mock.calls[0][0]).not.toContain('Bohemian')
  })

  it('mostra a contagem para o próximo desafio', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-15T01:00:00Z'))
    render(<ResultPanel game={WON_GAME} />)
    expect(screen.getByText('02:00:00')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(1000))
    expect(screen.getByText('01:59:59')).toBeInTheDocument()
    vi.useRealTimers()
  })
})

describe('CategoryCard e Mascot', () => {
  it('indica o status do desafio', () => {
    render(
      <MemoryRouter>
        <CategoryCard
          item={{ slug: 'pop', name: 'Pop', description: '', status: 'won', attempts_used: 2, score: 80, game_id: 'x' }}
          maxAttempts={6}
        />
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: 'Pop: Ver resultado' })
    expect(link).toHaveAttribute('href', '/desafio/pop')
    expect(link).toHaveTextContent('80 pts')
  })

  it('descreve cada humor do mascote', () => {
    const { rerender } = render(<Mascot mood="nervous" />)
    expect(screen.getByRole('img', { name: /suando frio/ })).toHaveAttribute('data-mood', 'nervous')
    rerender(<Mascot mood="champion" />)
    expect(screen.getByRole('img', { name: /sinal do rock/ })).toBeInTheDocument()
  })
})
