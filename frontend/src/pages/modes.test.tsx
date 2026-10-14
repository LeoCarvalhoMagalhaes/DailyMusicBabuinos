import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CategoryOrder } from '../components/CategoryOrder/CategoryOrder'
import type { CategorySlug, MatchState, ScoreLine } from '../types/api'
import { FinalResults } from './RoomPage'

const ORDER: CategorySlug[] = ['rock', 'pop', 'rap', 'country', 'eletronica', 'geral']

function line(position: number, id: string, name: string, total: number, correct: number): ScoreLine {
  return {
    position,
    account_id: id,
    display_name: name,
    total_score: total,
    correct,
    average_response_ms: correct ? 4200 : null,
    left: false,
    per_category: ORDER.map((category) => ({ category, score: total / 6, correct: correct / 6 })),
  }
}

function finishedMatch(scoreboard: ScoreLine[], winners: string[]): MatchState {
  return {
    id: 'm1',
    status: 'finished',
    phase: 'reveal',
    current_round: 18,
    total_rounds: 18,
    phase_ends_at: new Date().toISOString(),
    round: {
      number: 18,
      category: { slug: 'geral', name: 'Geral', description: '' },
      index_in_category: 3,
      songs_per_category: 3,
      started_at: null,
      ends_at: null,
    },
    my_game: null,
    progress: [],
    answer: null,
    scoreboard,
    history: [],
    winner_ids: winners,
  }
}

describe('FinalResults', () => {
  it('destaca o vencedor e mostra posição, pontos, acertos, categorias e tempo médio', () => {
    const board = [line(1, 'a', 'Alice', 1800, 18), line(2, 'b', 'Bob', 600, 6)]
    render(<FinalResults match={finishedMatch(board, ['a'])} me="b" />)
    expect(screen.getByTestId('winner')).toHaveTextContent('Alice')
    expect(screen.getByRole('img', { name: /sinal do rock/ })).toBeInTheDocument()
    const rows = screen.getAllByRole('row')
    expect(rows).toHaveLength(3) // cabeçalho + 2 jogadores
    const alice = within(rows[1])
    expect(alice.getByText('1º')).toBeInTheDocument()
    expect(alice.getByText('1800')).toBeInTheDocument()
    expect(alice.getByText('18/18')).toBeInTheDocument()
    expect(alice.getByText('5s')).toBeInTheDocument()
    expect(within(rows[2]).getByText(/Bob \(você\)/)).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Eletrônica' })).toBeInTheDocument()
  })

  it('anuncia empate no topo', () => {
    const board = [line(1, 'a', 'Alice', 900, 9), line(2, 'b', 'Bob', 900, 9)]
    render(<FinalResults match={finishedMatch(board, ['a', 'b'])} me="a" />)
    expect(screen.getByText(/Empate no topo/)).toBeInTheDocument()
    expect(screen.getByTestId('winner')).toHaveTextContent('Alice & Bob')
  })
})

describe('CategoryOrder', () => {
  it('o anfitrião reordena as categorias', async () => {
    const onChange = vi.fn()
    render(<CategoryOrder order={ORDER} editable onChange={onChange} />)
    expect(screen.getByRole('button', { name: 'Subir Rock' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Subir Pop' }))
    expect(onChange).toHaveBeenCalledWith(['pop', 'rock', 'rap', 'country', 'eletronica', 'geral'])
  })

  it('os outros jogadores só veem a ordem', () => {
    render(<CategoryOrder order={ORDER} editable={false} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(6)
  })
})
