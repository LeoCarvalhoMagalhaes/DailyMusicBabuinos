"""Rotas de partida: iniciar, consultar, palpitar, pular, ouvir e resultado."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import (
    current_player,
    get_clock,
    get_db,
    get_limiter,
    get_provider,
    get_settings,
)
from app.api.presenters import game_state, history_item
from app.audio.base import AudioProvider
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ConflictError
from app.core.rate_limit import RateLimiter
from app.models import Player
from app.repositories.games import history
from app.schemas import (
    GameState,
    GuessIn,
    GuessResult,
    HistoryOut,
    SkipIn,
    StartGameIn,
    StatisticsOut,
)
from app.services import game as game_service
from app.services.stats import read_player_stats

router = APIRouter(prefix="/api")


@router.post("/games/start", response_model=GameState, tags=["partida"])
def start(body: StartGameIn, db: Session = Depends(get_db),
          settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
          provider: AudioProvider = Depends(get_provider),
          player: Player = Depends(current_player)) -> GameState:
    """Inicia (ou recupera) a partida do jogador no desafio de hoje. Idempotente."""
    game = game_service.start_game(db, settings, provider, player, body.category,
                                   clock.today(), clock.now())
    return game_state(game, settings, provider, clock)


@router.get("/games/{game_id}", response_model=GameState, tags=["partida"])
def get_game(game_id: str, db: Session = Depends(get_db),
             settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
             provider: AudioProvider = Depends(get_provider),
             player: Player = Depends(current_player)) -> GameState:
    game = game_service.load_game(db, player, game_id)
    return game_state(game, settings, provider, clock)


@router.post("/games/{game_id}/guess", response_model=GuessResult, tags=["partida"])
def guess(game_id: str, body: GuessIn, db: Session = Depends(get_db),
          settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
          provider: AudioProvider = Depends(get_provider),
          limiter: RateLimiter = Depends(get_limiter),
          player: Player = Depends(current_player)) -> GuessResult:
    limiter.hit(f"guess:{player.id}", settings.rate_limit_guess_per_minute, 60)
    game, correct = game_service.submit_guess(db, settings, player, game_id, body.guess,
                                              body.attempt, clock.now())
    return GuessResult(correct=correct, game=game_state(game, settings, provider, clock))


@router.post("/games/{game_id}/skip", response_model=GameState, tags=["partida"])
def skip(game_id: str, body: SkipIn, db: Session = Depends(get_db),
         settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
         provider: AudioProvider = Depends(get_provider),
         limiter: RateLimiter = Depends(get_limiter),
         player: Player = Depends(current_player)) -> GameState:
    """Pula a vez: consome uma tentativa e libera a próxima pista."""
    limiter.hit(f"guess:{player.id}", settings.rate_limit_guess_per_minute, 60)
    game = game_service.skip_turn(db, settings, player, game_id, body.attempt, clock.now())
    return game_state(game, settings, provider, clock)


@router.get("/games/{game_id}/audio", tags=["partida"],
            responses={200: {"content": {"audio/mpeg": {}, "audio/wav": {}}}})
def audio(game_id: str, stage: int = Query(ge=1, le=50), db: Session = Depends(get_db),
          settings: Settings = Depends(get_settings),
          provider: AudioProvider = Depends(get_provider),
          limiter: RateLimiter = Depends(get_limiter),
          player: Player = Depends(current_player)) -> Response:
    """Entrega somente o trecho liberado. A URL não contém nada sobre a música, e o
    arquivo vai sem metadados. Erros do provedor retornam 503 sem afetar a partida."""
    limiter.hit(f"audio:{player.id}", settings.rate_limit_audio_per_minute, 60)
    game = game_service.load_game(db, player, game_id, with_guesses=False)
    seconds = game_service.check_audio_access(game, settings, stage)
    clip = provider.get_clip(game.track, seconds, category=game.category)
    db.commit()  # persiste ids externos eventualmente resolvidos pelo provedor
    return Response(content=clip.data, media_type=clip.media_type, headers={
        "Cache-Control": "no-store",
        "X-Clip-Duration": f"{clip.duration:.3f}",
    })


@router.get("/games/{game_id}/result", response_model=GameState, tags=["partida"])
def result(game_id: str, db: Session = Depends(get_db),
           settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
           provider: AudioProvider = Depends(get_provider),
           player: Player = Depends(current_player)) -> GameState:
    game = game_service.load_game(db, player, game_id)
    if not game.finished:
        raise ConflictError("A partida ainda está em andamento.", code="game_in_progress")
    return game_state(game, settings, provider, clock)


@router.get("/statistics", response_model=StatisticsOut, tags=["estatísticas"])
def statistics(db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
               clock: Clock = Depends(get_clock),
               player: Player = Depends(current_player)) -> StatisticsOut:
    return StatisticsOut(**read_player_stats(db, settings, player.id, clock.today()))


@router.get("/history", response_model=HistoryOut, tags=["estatísticas"])
def game_history(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
                 provider: AudioProvider = Depends(get_provider),
                 player: Player = Depends(current_player)) -> HistoryOut:
    items, total = history(db, player.id, limit, offset)
    return HistoryOut(items=[history_item(g, settings, provider) for g in items], total=total)
