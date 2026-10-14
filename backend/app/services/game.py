"""Regras da partida. O backend é a autoridade sobre tentativas, pontuação e resultado.

Separação de responsabilidades:
- Este módulo cuida de tentativas, validação e pontuação.
- O áudio fica em `app.audio`; aqui só decidimos QUAL estágio o jogador pode ouvir.
  Falhas de áudio nunca passam por aqui, então nunca consomem tentativas.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audio.base import AudioProvider
from app.core.config import Settings
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.models import GameGuess, GameSession, Player
from app.services import answers
from app.services.catalog import catalog_index
from app.services.daily import get_or_create_challenge
from app.services.scoring import score_for
from app.services.stats import refresh_player_stats


@dataclass(frozen=True)
class RevealedAnswer:
    title: str
    artist: str
    cover_url: str | None
    external_url: str | None
    spotify_url: str | None
    attribution: str | None


def unlocked_stage(game: GameSession, settings: Settings) -> int:
    """Estágio de áudio liberado (1-based). Partida encerrada libera tudo."""
    if game.finished:
        return settings.max_attempts
    return min(game.attempts_used + 1, settings.max_attempts)


def start_game(db: Session, settings: Settings, provider: AudioProvider, player: Player,
               category: str, today: date, now: datetime) -> GameSession:
    challenge = get_or_create_challenge(db, settings, provider, category, today, now)
    existing = _find_game(db, player.id, challenge.id)
    if existing:
        return existing
    game = GameSession(id=str(uuid.uuid4()), challenge_id=challenge.id, player_id=player.id,
                       attempts_used=0, score=0, status="in_progress", started_at=now)
    db.add(game)
    try:
        db.commit()
    except IntegrityError:
        # Duplo clique / duas abas: a restrição única garante uma única partida.
        db.rollback()
        existing = _find_game(db, player.id, challenge.id)
        if existing is None:  # pragma: no cover
            raise
        return existing
    return game


def _find_game(db: Session, player_id: str, challenge_id: int) -> GameSession | None:
    return db.scalar(
        select(GameSession).where(
            GameSession.player_id == player_id, GameSession.challenge_id == challenge_id
        )
    )


def load_game(db: Session, player: Player, game_id: str, *, for_update: bool = False
              ) -> GameSession:
    try:
        uuid.UUID(game_id)
    except ValueError as exc:
        raise NotFoundError("Partida não encontrada.") from exc
    stmt = select(GameSession).where(GameSession.id == game_id)
    if for_update:
        stmt = stmt.with_for_update()
    game = db.scalar(stmt)
    # Partidas de outros jogadores respondem 404 (não revelamos que existem).
    if game is None or game.player_id != player.id:
        raise NotFoundError("Partida não encontrada.")
    return game


def _check_turn(game: GameSession, settings: Settings, expected_attempt: int) -> None:
    if game.finished:
        raise ConflictError("Esta partida já terminou.", code="game_finished")
    if game.attempts_used >= settings.max_attempts:  # pragma: no cover - defesa extra
        raise ConflictError("Sem tentativas restantes.", code="no_attempts_left")
    # O cliente informa qual tentativa acha que está enviando. Reenvios (duplo clique,
    # retry de rede) chegam com número antigo e são rejeitados sem consumir nada.
    if expected_attempt != game.attempts_used + 1:
        raise ConflictError("Esta tentativa já foi registrada. Atualizando a partida…",
                            code="attempt_mismatch")


def _register(db: Session, settings: Settings, game: GameSession, guess: GameGuess,
              now: datetime) -> GameSession:
    game.attempts_used += 1
    guess.attempt_number = game.attempts_used
    guess.created_at = now
    game.guesses.append(guess)
    if guess.is_correct:
        game.status = "won"
        game.score = score_for(game.attempts_used, True, settings.score_table)
        game.finished_at = now
    elif game.attempts_used >= settings.max_attempts:
        game.status = "lost"
        game.score = 0
        game.finished_at = now
    try:
        db.flush()
    except IntegrityError as exc:
        # Duas requisições simultâneas para a mesma tentativa: só uma é gravada.
        db.rollback()
        raise ConflictError("Esta tentativa já foi registrada.", code="attempt_mismatch") from exc
    if game.finished:
        refresh_player_stats(db, settings, game.player_id, now)
    db.commit()
    return game


def submit_guess(db: Session, settings: Settings, player: Player, game_id: str, raw_guess: str,
                 expected_attempt: int, now: datetime) -> tuple[GameSession, bool]:
    game = load_game(db, player, game_id, for_update=True)
    _check_turn(game, settings, expected_attempt)
    text = answers.clean_guess(raw_guess)
    normalized = answers.normalize(text)
    if not normalized:
        raise AppError("Digite o nome de uma música.", code="empty_guess", status_code=422)
    if any(g.normalized == normalized and not g.is_skip for g in game.guesses):
        raise ConflictError("Você já tentou essa! Escolha outra música.", code="duplicate_guess")
    track = game.challenge.track
    others = catalog_index.titles(db, settings.catalog_edition)
    correct = answers.is_correct(text, track.title, track.aliases, others)
    guess = GameGuess(guess_text=text, normalized=normalized[:200], is_skip=False,
                      is_correct=correct)
    return _register(db, settings, game, guess, now), correct


def skip_turn(db: Session, settings: Settings, player: Player, game_id: str,
              expected_attempt: int, now: datetime) -> GameSession:
    game = load_game(db, player, game_id, for_update=True)
    _check_turn(game, settings, expected_attempt)
    guess = GameGuess(guess_text="", normalized="", is_skip=True, is_correct=False)
    return _register(db, settings, game, guess, now)


def check_audio_access(game: GameSession, settings: Settings, stage: int) -> float:
    """Valida o estágio pedido e retorna a duração (s) que pode ser entregue."""
    if not 1 <= stage <= settings.max_attempts:
        raise NotFoundError("Estágio inexistente.")
    if stage > unlocked_stage(game, settings):
        raise ForbiddenError("Esse trecho ainda não foi liberado.", code="stage_locked")
    return settings.clip_stages_seconds[stage - 1]


def reveal_answer(game: GameSession, provider: AudioProvider) -> RevealedAnswer:
    """Único ponto que expõe a música secreta — e só para partidas encerradas."""
    if not game.finished:
        raise ForbiddenError("A resposta só aparece no fim da partida.", code="game_in_progress")
    track = game.challenge.track
    meta = provider.metadata(track)
    spotify_url = f"https://open.spotify.com/track/{track.spotify_id}" if track.spotify_id else None
    return RevealedAnswer(track.title, track.artist, meta.cover_url, meta.external_url, spotify_url,
                          meta.attribution)

