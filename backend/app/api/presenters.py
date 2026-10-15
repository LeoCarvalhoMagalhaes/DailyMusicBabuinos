"""Conversão de entidades para os contratos públicos da API."""

from __future__ import annotations

from app.audio.base import AudioProvider
from app.core.categories import CATEGORY_BY_SLUG
from app.core.clock import Clock
from app.core.config import Settings
from app.models import GameSession
from app.schemas import AnswerOut, AudioInfo, CategoryOut, GameState, GuessOut, HistoryItem, Rules
from app.services.daily import challenge_number
from app.services.game import reveal_answer, unlocked_stage


def category_out(slug: str) -> CategoryOut:
    cat = CATEGORY_BY_SLUG[slug]
    return CategoryOut(slug=cat.slug, name=cat.name, description=cat.description)


def rules_out(settings: Settings) -> Rules:
    return Rules(max_attempts=settings.max_attempts, stages_seconds=settings.clip_stages_seconds,
                 score_table=settings.score_table)


def audio_info(provider: AudioProvider) -> AudioInfo:
    return AudioInfo(provider=provider.name, demo_mode=provider.is_demo,
                     attribution=provider.attribution)


def answer_out(game: GameSession, provider: AudioProvider) -> AnswerOut | None:
    if not game.finished:
        return None
    revealed = reveal_answer(game, provider)
    return AnswerOut(title=revealed.title, artist=revealed.artist, cover_url=revealed.cover_url,
                     external_url=revealed.external_url, spotify_url=revealed.spotify_url,
                     attribution=revealed.attribution)


def game_state(game: GameSession, settings: Settings, provider: AudioProvider,
               clock: Clock) -> GameState:
    challenge = game.challenge  # só no modo diário
    return GameState(
        id=game.id,
        mode=game.mode,  # type: ignore[arg-type]
        category=category_out(game.category),
        date=challenge.challenge_date if challenge else None,
        challenge_number=challenge_number(settings, challenge.challenge_date)
        if challenge else None,
        status=game.status,  # type: ignore[arg-type]
        attempts_used=game.attempts_used,
        max_attempts=settings.max_attempts,
        remaining_attempts=max(0, settings.max_attempts - game.attempts_used),
        unlocked_stage=unlocked_stage(game, settings),
        stages_seconds=settings.clip_stages_seconds,
        score=game.score,
        speed_bonus=game.speed_bonus,
        guesses=[
            GuessOut(attempt=g.attempt_number, text=g.guess_text, skipped=g.is_skip,
                     correct=g.is_correct, same_artist=bool(g.same_artist))
            for g in game.guesses
        ],
        answer=answer_out(game, provider),
        next_reset_at=clock.next_reset(),
    )


def history_item(game: GameSession, settings: Settings, provider: AudioProvider) -> HistoryItem:
    challenge = game.challenge
    assert challenge is not None  # o histórico só lista partidas diárias
    return HistoryItem(
        game_id=game.id,
        date=challenge.challenge_date,
        challenge_number=challenge_number(settings, challenge.challenge_date),
        category=category_out(challenge.category),
        status=game.status,  # type: ignore[arg-type]
        attempts_used=game.attempts_used,
        score=game.score,
        answer=answer_out(game, provider),
    )
