"""Contratos públicos da API (Pydantic).

Nenhum schema de partida em andamento possui campos de título/artista da resposta:
`GameState.answer` só é preenchido por `services.game.reveal_answer`, que exige
partida encerrada.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.categories import CATEGORY_SLUGS

CategorySlug = Literal["rock", "pop", "rap", "country", "eletronica", "geral"]
assert set(CategorySlug.__args__) == set(CATEGORY_SLUGS)  # type: ignore[attr-defined]

GameStatus = Literal["in_progress", "won", "lost"]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class Rules(BaseModel):
    max_attempts: int
    stages_seconds: list[float]
    score_table: list[int]


class CategoryOut(BaseModel):
    slug: CategorySlug
    name: str
    description: str


class CategoryDailyStatus(CategoryOut):
    status: Literal["not_started", "in_progress", "won", "lost"]
    attempts_used: int = 0
    score: int = 0
    game_id: str | None = None


class AudioInfo(BaseModel):
    provider: str
    demo_mode: bool
    attribution: str | None


class DailyOverview(BaseModel):
    date: date
    timezone: str
    challenge_number: int
    server_time: datetime
    next_reset_at: datetime
    audio: AudioInfo
    rules: Rules
    categories: list[CategoryDailyStatus]


class DailyChallengeOut(BaseModel):
    category: CategoryOut
    date: date
    challenge_number: int
    server_time: datetime
    next_reset_at: datetime
    audio: AudioInfo
    rules: Rules


class PlayerCreated(BaseModel):
    player_id: str
    token: str = Field(description="Guarde no dispositivo; enviado como 'Authorization: Bearer'.")


class PlayerOut(BaseModel):
    player_id: str
    created_at: datetime


class StartGameIn(BaseModel):
    category: CategorySlug


class GuessIn(BaseModel):
    guess: str = Field(min_length=1, max_length=200)
    attempt: int = Field(ge=1, le=50)


class SkipIn(BaseModel):
    attempt: int = Field(ge=1, le=50)


class GuessOut(BaseModel):
    attempt: int
    text: str
    skipped: bool
    correct: bool


class AnswerOut(BaseModel):
    title: str
    artist: str
    cover_url: str | None
    external_url: str | None
    spotify_url: str | None = None
    attribution: str | None


class GameState(BaseModel):
    id: str
    category: CategoryOut
    date: date
    challenge_number: int
    status: GameStatus
    attempts_used: int
    max_attempts: int
    remaining_attempts: int
    unlocked_stage: int
    stages_seconds: list[float]
    score: int
    guesses: list[GuessOut]
    answer: AnswerOut | None = None
    next_reset_at: datetime


class GuessResult(BaseModel):
    correct: bool
    game: GameState


class SongSuggestion(BaseModel):
    id: str
    title: str
    artist: str


class StatsBlock(BaseModel):
    category: str
    games_played: int
    wins: int
    win_rate: float
    total_score: int
    average_score: float
    current_streak: int
    best_streak: int
    last_played_date: date | None
    distribution: list[int] = Field(
        description="Vitórias por tentativa (1..N) seguidas do total de derrotas."
    )


class StatisticsOut(BaseModel):
    overall: StatsBlock
    categories: list[StatsBlock]


class HistoryItem(BaseModel):
    game_id: str
    date: date
    challenge_number: int
    category: CategoryOut
    status: GameStatus
    attempts_used: int
    score: int
    answer: AnswerOut | None


class HistoryOut(BaseModel):
    items: list[HistoryItem]
    total: int


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    audio_provider: str
    catalog_edition: str
    version: str
