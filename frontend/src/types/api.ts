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

export type GameMode = 'daily' | 'endless' | 'match'

export interface GameState {
  id: string
  mode?: GameMode
  category: CategoryInfo
  // Só no desafio diário.
  date: string | null
  challenge_number: number | null
  status: GameStatus
  attempts_used: number
  max_attempts: number
  remaining_attempts: number
  unlocked_stage: number
  stages_seconds: number[]
  score: number
  speed_bonus?: number
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

// ------------------------------------------------------------ modo ilimitado

export interface RunSummary {
  run_id: string
  rounds: number
  wins: number
  score: number
  current_streak: number
  best_streak: number
}

export interface EndlessRound {
  game: GameState
  run: RunSummary
}

export interface EndlessStatsBlock {
  category: string
  rounds: number
  wins: number
  win_rate: number
  total_score: number
  average_score: number
  current_streak: number
  best_streak: number
  distribution: number[]
}

export interface EndlessStats {
  overall: EndlessStatsBlock
  categories: EndlessStatsBlock[]
}

// ---------------------------------------------------------------- multiplayer

export interface Account {
  id: string
  username: string
  display_name: string
}

export interface AuthResult {
  token: string
  account: Account
}

export interface RoomMember {
  account_id: string
  display_name: string
  is_host: boolean
  ready: boolean
  connected: boolean
  left: boolean
}

export interface PlayerProgress {
  account_id: string
  display_name: string
  attempts_used: number
  status: GameStatus
  score: number
}

export interface MatchRound {
  number: number
  category: CategoryInfo
  index_in_category: number
  songs_per_category: number
  started_at: string | null
  ends_at: string | null
}

export interface CategoryScore {
  category: CategorySlug
  score: number
  correct: number
}

export interface ScoreLine {
  position: number
  account_id: string
  display_name: string
  total_score: number
  correct: number
  average_response_ms: number | null
  per_category: CategoryScore[]
  left: boolean
}

export interface RoundResult {
  number: number
  category: CategoryInfo
  answer: Answer
  my_status: GameStatus | null
  my_score: number
}

export interface MatchState {
  id: string
  status: 'playing' | 'finished' | 'abandoned'
  phase: 'playing' | 'reveal'
  current_round: number
  total_rounds: number
  phase_ends_at: string
  round: MatchRound
  my_game: GameState | null
  progress: PlayerProgress[]
  answer: Answer | null
  scoreboard: ScoreLine[]
  history: RoundResult[]
  winner_ids: string[]
}

export interface RoomState {
  id: string
  code: string
  status: 'waiting' | 'playing' | 'closed'
  version: number
  me: string
  host_account_id: string
  category_order: CategorySlug[]
  members: RoomMember[]
  min_players: number
  max_players: number
  can_start: boolean
  start_blocker: string | null
  round_seconds: number
  reveal_seconds: number
  speed_bonus_max: number
  rules: Rules
  server_time: string
  match: MatchState | null
}
