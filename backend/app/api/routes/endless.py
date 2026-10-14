"""Modo ilimitado: próxima rodada, placar da sessão e estatísticas do modo.

Palpites, pulos, áudio e resultado de cada rodada usam as rotas de /api/games, as
mesmas do desafio diário.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import (
    current_player,
    get_clock,
    get_db,
    get_limiter,
    get_provider,
    get_settings,
)
from app.api.presenters import game_state
from app.audio.base import AudioProvider
from app.core.clock import Clock
from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.models import Player
from app.schemas import (
    EndlessNextIn,
    EndlessRound,
    EndlessStatsBlock,
    EndlessStatsOut,
    RunSummaryOut,
)
from app.services import endless

router = APIRouter(prefix="/api/endless", tags=["modo ilimitado"])


def _run_out(summary: endless.RunSummary) -> RunSummaryOut:
    return RunSummaryOut(run_id=summary.run_id, rounds=summary.rounds, wins=summary.wins,
                         score=summary.score, current_streak=summary.current_streak,
                         best_streak=summary.best_streak)


@router.post("/next", response_model=EndlessRound)
def next_round(body: EndlessNextIn, db: Session = Depends(get_db),
               settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
               provider: AudioProvider = Depends(get_provider),
               limiter: RateLimiter = Depends(get_limiter),
               player: Player = Depends(current_player)) -> EndlessRound:
    """Rodada atual da categoria ou, se a anterior terminou, uma música nova."""
    limiter.hit(f"endless:{player.id}", settings.rate_limit_guess_per_minute, 60)
    game = endless.next_round(db, settings, provider, player, body.category, body.run_id,
                              clock.today(), clock.now())
    summary = endless.run_summary(db, player.id, game.run_id or "")
    return EndlessRound(game=game_state(game, settings, provider, clock), run=_run_out(summary))


@router.get("/runs/{run_id}", response_model=RunSummaryOut)
def run(run_id: str, db: Session = Depends(get_db),
        player: Player = Depends(current_player)) -> RunSummaryOut:
    return _run_out(endless.run_summary(db, player.id, run_id[:36]))


@router.get("/stats", response_model=EndlessStatsOut)
def stats(db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
          player: Player = Depends(current_player)) -> EndlessStatsOut:
    blocks = [
        EndlessStatsBlock(category=s.category, rounds=s.rounds, wins=s.wins,
                          win_rate=s.win_rate, total_score=s.total_score,
                          average_score=s.average_score, current_streak=s.current_streak,
                          best_streak=s.best_streak, distribution=s.distribution)
        for s in endless.endless_stats(db, settings, player.id)
    ]
    return EndlessStatsOut(overall=blocks[0], categories=blocks[1:])
