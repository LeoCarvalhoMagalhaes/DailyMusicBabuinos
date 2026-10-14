"""Acesso a dados de jogadores anônimos."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_token, looks_like_token, new_player_token
from app.models import Player


def create_player(db: Session, now: datetime) -> tuple[Player, str]:
    token = new_player_token()
    player = Player(id=str(uuid.uuid4()), token_hash=hash_token(token), created_at=now,
                    last_seen_at=now)
    db.add(player)
    db.commit()
    return player, token


def find_by_token(db: Session, token: str) -> Player | None:
    if not looks_like_token(token):
        return None
    return db.scalar(select(Player).where(Player.token_hash == hash_token(token)))
