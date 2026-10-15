import type { GameState } from '../types/api'

export function makeGame(overrides: Partial<GameState> = {}): GameState {
  return {
    id: '1dc8a8f7-d32a-4d39-8375-e1b749421433',
    category: { slug: 'rock', name: 'Rock', description: '' },
    date: '2026-10-14',
    challenge_number: 1,
    status: 'in_progress',
    attempts_used: 0,
    max_attempts: 6,
    remaining_attempts: 6,
    unlocked_stage: 1,
    stages_seconds: [0.5, 1, 2, 4, 8, 16],
    score: 0,
    guesses: [],
    answer: null,
    next_reset_at: '2026-10-15T03:00:00Z',
    ...overrides,
  }
}

export const WON_GAME = makeGame({
  status: 'won',
  attempts_used: 2,
  remaining_attempts: 4,
  unlocked_stage: 6,
  score: 80,
  guesses: [
    { attempt: 1, text: 'Hey Jude', skipped: false, correct: false },
    { attempt: 2, text: 'Bohemian Rhapsody', skipped: false, correct: true },
  ],
  answer: {
    title: 'Bohemian Rhapsody',
    artist: 'Queen',
    cover_url: null,
    external_url: 'https://www.deezer.com/track/1',
    spotify_url: 'https://open.spotify.com/track/4u7EnebtmKWzUH433cf5Qv',
    attribution: 'Prévia de áudio fornecida pelo Deezer',
  },
})
