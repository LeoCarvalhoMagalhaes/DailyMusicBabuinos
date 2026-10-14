"""Consultas de partidas usadas pelo histórico e pela visão diária."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import DailyChallenge, GameSession


def games_for_day(db: Session, player_id: str, day: date, edition: str) -> list[GameSession]:
    return list(
        db.scalars(
            select(GameSession)
            .join(DailyChallenge, DailyChallenge.id == GameSession.challenge_id)
            .where(
                GameSession.player_id == player_id,
                DailyChallenge.challenge_date == day,
                DailyChallenge.edition == edition,
            )
            .options(joinedload(GameSession.challenge))
        )
    )


def history(db: Session, player_id: str, limit: int, offset: int) -> tuple[list[GameSession], int]:
    base = (
        select(GameSession)
        .join(DailyChallenge, DailyChallenge.id == GameSession.challenge_id)
        .where(GameSession.player_id == player_id)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = db.scalars(
        base.options(
            joinedload(GameSession.challenge).joinedload(DailyChallenge.track)
        )
        .order_by(DailyChallenge.challenge_date.desc(), DailyChallenge.category)
        .limit(limit)
        .offset(offset)
    ).unique().all()
    return list(items), total
