from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Player(Base):
    """Jogador anônimo. Não guardamos nome, e-mail nem IP."""

    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlayerStatistics(Base):
    """Agregado de estatísticas. `category = "all"` guarda o geral.

    É um cache derivado de `game_sessions` (fonte da verdade), recalculado a cada
    partida concluída por `services.stats.refresh_player_stats`.
    """

    __tablename__ = "player_statistics"

    player_id: Mapped[str] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    total_score: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_played_date: Mapped[date | None] = mapped_column(Date)
    # Índice i = vitórias na tentativa i+1; o último elemento conta as derrotas.
    distribution: Mapped[list[int]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
