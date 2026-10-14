// Contratos da API (espelham app/schemas no backend).

export type CategorySlug = 'rock' | 'pop' | 'rap' | 'country' | 'eletronica' | 'geral'
export type GameStatus = 'in_progress' | 'won' | 'lost'
export type DailyStatus = GameStatus | 'not_started'

export interface Rules {
  max_attempts: number
  stages_seconds: number[]
  score_table: number[]
}

export interface CategoryInfo {
  slug: CategorySlug
  name: string
  description: string
}

export interface CategoryDailyStatus extends CategoryInfo {
  status: DailyStatus
  attempts_used: number
  score: number
  game_id: string | null
}

export interface AudioInfo {
  provider: string
  demo_mode: boolean
  attribution: string | null
}

export interface DailyOverview {
  date: string
  timezone: string
  challenge_number: number
  server_time: string
  next_reset_at: string
  audio: AudioInfo
  rules: Rules
  categories: CategoryDailyStatus[]
}

export interface PlayerCreated {
  player_id: string
  token: string
}

export interface GuessEntry {
  attempt: number
  text: string
  skipped: boolean
  correct: boolean
}

export interface Answer {
  title: string
  artist: string
  cover_url: string | null
  external_url: string | null
  spotify_url?: string | null
  attribution: string | null
}

export interface GameState {
  id: string
  category: CategoryInfo
  date: string
  challenge_number: number
  status: GameStatus
  attempts_used: number
  max_attempts: number
  remaining_attempts: number
  unlocked_stage: number
  stages_seconds: number[]
  score: number
  guesses: GuessEntry[]
  answer: Answer | null
  next_reset_at: string
}

export interface GuessResult {
  correct: boolean
  game: GameState
}

export interface SongSuggestion {
  id: string
  title: string
  artist: string
}

export interface StatsBlock {
  category: string
  games_played: number
  wins: number
  win_rate: number
  total_score: number
  average_score: number
  current_streak: number
  best_streak: number
  last_played_date: string | null
  distribution: number[]
}

export interface Statistics {
  overall: StatsBlock
  categories: StatsBlock[]
}

export interface HistoryItem {
  game_id: string
  date: string
  challenge_number: number
  category: CategoryInfo
  status: GameStatus
  attempts_used: number
  score: number
  answer: Answer | null
}

export interface HistoryPage {
  items: HistoryItem[]
  total: number
}

export interface ApiErrorBody {
  error: { code: string; message: string }
}
