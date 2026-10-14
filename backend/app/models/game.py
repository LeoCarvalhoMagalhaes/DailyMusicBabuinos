from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.challenge import DailyChallenge


class GameSession(Base):
    """Uma partida de um jogador em um desafio. Única por (jogador, desafio):
    impede reiniciar partidas concluídas e registros duplicados."""

    __tablename__ = "game_sessions"
    __table_args__ = (
        UniqueConstraint("player_id", "challenge_id", name="uq_game_player_challenge"),
        Index("ix_game_player_status", "player_id", "status"),
    )

    # Identificador público opaco (UUID4 em texto).
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("daily_challenges.id"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    attempts_used: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    # in_progress | won | lost
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    challenge: Mapped[DailyChallenge] = relationship()
    guesses: Mapped[list[GameGuess]] = relationship(
        back_populates="game", order_by="GameGuess.attempt_number", cascade="all, delete-orphan"
    )

    @property
    def finished(self) -> bool:
        return self.status != "in_progress"


class GameGuess(Base):
    __tablename__ = "game_guesses"
    __table_args__ = (UniqueConstraint("game_id", "attempt_number", name="uq_guess_attempt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.id", ondelete="CASCADE"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    # Texto digitado pelo próprio jogador (vazio quando pulou).
    guess_text: Mapped[str] = mapped_column(String(200), default="")
    normalized: Mapped[str] = mapped_column(String(200), default="")
    is_skip: Mapped[bool] = mapped_column(Boolean, default=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    game: Mapped[GameSession] = relationship(back_populates="guesses")
