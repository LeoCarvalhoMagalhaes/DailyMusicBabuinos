"""Estatísticas do jogador.

`game_sessions` é a fonte da verdade. A tabela `player_statistics` é um agregado
recalculado integralmente sempre que uma partida termina — isso torna a operação
idempotente (impossível contar a mesma partida duas vezes) e fácil de reparar.

Sequência de dias: dias de desafio consecutivos em que o jogador concluiu ao menos
uma partida. Os dias seguem o fuso do desafio (CHALLENGE_TIMEZONE), não o relógio
do aparelho. A sequência atual continua "viva" até o fim do dia seguinte ao último
jogo; depois disso é exibida como zero.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.categories import CATEGORY_SLUGS
from app.core.config import Settings
from app.models import DailyChallenge, GameSession, PlayerStatistics

ALL = "all"


@dataclass
class _Acc:
    games: int = 0
    wins: int = 0
    score: int = 0
    days: set[date] = field(default_factory=set)
    distribution: list[int] = field(default_factory=list)


def compute_streaks(days: set[date]) -> tuple[int, int, date | None]:
    """Retorna (sequência terminando no último dia jogado, melhor sequência, último dia)."""
    if not days:
        return 0, 0, None
    ordered = sorted(days)
    best = run = 1
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        run = run + 1 if cur - prev == timedelta(days=1) else 1
        best = max(best, run)
    return run, best, ordered[-1]


def live_streak(stored: int, last_played: date | None, today: date) -> int:
    if last_played is None or today - last_played > timedelta(days=1):
        return 0
    return stored


def refresh_player_stats(db: Session, settings: Settings, player_id: str, now: datetime) -> None:
    rows = db.execute(
        select(GameSession.status, GameSession.attempts_used, GameSession.score,
               DailyChallenge.category, DailyChallenge.challenge_date)
        .join(DailyChallenge, DailyChallenge.id == GameSession.challenge_id)
        .where(GameSession.player_id == player_id, GameSession.status != "in_progress")
    ).all()
    slots = settings.max_attempts + 1
    accs: dict[str, _Acc] = defaultdict(lambda: _Acc(distribution=[0] * slots))
    for row in rows:
        for key in (ALL, row.category):
            acc = accs[key]
            acc.games += 1
            acc.score += row.score
            acc.days.add(row.challenge_date)
            if row.status == "won":
                acc.wins += 1
                acc.distribution[min(row.attempts_used, settings.max_attempts) - 1] += 1
            else:
                acc.distribution[-1] += 1

    db.execute(delete(PlayerStatistics).where(PlayerStatistics.player_id == player_id))
    for key, acc in accs.items():
        current, best, last = compute_streaks(acc.days)
        db.add(PlayerStatistics(
            player_id=player_id, category=key, games_played=acc.games, wins=acc.wins,
            total_score=acc.score, current_streak=current, best_streak=best,
            last_played_date=last, distribution=acc.distribution, updated_at=now,
        ))
    db.flush()


def empty_stats(category: str, settings: Settings) -> dict:
    return {
        "category": category, "games_played": 0, "wins": 0, "win_rate": 0.0,
        "total_score": 0, "average_score": 0.0, "current_streak": 0, "best_streak": 0,
        "last_played_date": None, "distribution": [0] * (settings.max_attempts + 1),
    }


def read_player_stats(db: Session, settings: Settings, player_id: str, today: date) -> dict:
    rows = {
        r.category: r
        for r in db.scalars(select(PlayerStatistics).where(PlayerStatistics.player_id == player_id))
    }

    def view(category: str) -> dict:
        row = rows.get(category)
        if row is None:
            return empty_stats(category, settings)
        distribution = list(row.distribution or [])
        distribution += [0] * (settings.max_attempts + 1 - len(distribution))
        return {
            "category": category,
            "games_played": row.games_played,
            "wins": row.wins,
            "win_rate": round(row.wins / row.games_played, 4) if row.games_played else 0.0,
            "total_score": row.total_score,
            "average_score": round(row.total_score / row.games_played, 1)
            if row.games_played else 0.0,
            "current_streak": live_streak(row.current_streak, row.last_played_date, today),
            "best_streak": row.best_streak,
            "last_played_date": row.last_played_date,
            "distribution": distribution,
        }

    return {"overall": view(ALL), "categories": [view(c) for c in CATEGORY_SLUGS]}
