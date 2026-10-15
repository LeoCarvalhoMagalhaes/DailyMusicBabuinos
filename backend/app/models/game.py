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
from sqlalchemy.sql import text

from app.database.session import Base
from app.models.catalog import MusicTrack
from app.models.challenge import DailyChallenge

# Modos de jogo. Todos usam a mesma mecânica (tentativas, trechos, validação e
# pontuação); só muda de onde vem a música e como a partida é agrupada.
MODE_DAILY = "daily"  # desafio diário: uma por (jogador, desafio)
MODE_ENDLESS = "endless"  # modo ilimitado: rodadas solo agrupadas por `run_id`
MODE_MATCH = "match"  # multiplayer: uma por (jogador, rodada da partida)
GAME_MODES = (MODE_DAILY, MODE_ENDLESS, MODE_MATCH)


class GameSession(Base):
    """Uma partida (rodada) de um jogador. As restrições únicas impedem reiniciar um
    desafio diário concluído e duplicar o jogador numa rodada multiplayer (no SQL,
    valores nulos não colidem, então cada restrição só vale para o seu modo)."""

    __tablename__ = "game_sessions"
    __table_args__ = (
        UniqueConstraint("player_id", "challenge_id", name="uq_game_player_challenge"),
        UniqueConstraint("player_id", "match_round_id", name="uq_game_player_round"),
        Index("ix_game_player_status", "player_id", "status"),
        Index("ix_game_player_mode_category", "player_id", "mode", "category"),
        # Modo ilimitado: no máximo uma rodada aberta por jogador e categoria, mesmo com
        # requisições simultâneas (índice único parcial, no SQLite e no PostgreSQL).
        Index("uq_endless_open_round", "player_id", "category", unique=True,
              sqlite_where=text("mode = 'endless' AND status = 'in_progress'"),
              postgresql_where=text("mode = 'endless' AND status = 'in_progress'")),
    )

    # Identificador público opaco (UUID4 em texto).
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mode: Mapped[str] = mapped_column(String(10), default=MODE_DAILY)
    category: Mapped[str] = mapped_column(String(20))
    track_id: Mapped[int] = mapped_column(ForeignKey("music_tracks.id"), index=True)
    # Só no modo diário.
    challenge_id: Mapped[int | None] = mapped_column(ForeignKey("daily_challenges.id"),
                                                     index=True)
    # Só no modo ilimitado: agrupa as rodadas de uma sessão de jogo.
    run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    # Só no multiplayer.
    match_round_id: Mapped[int | None] = mapped_column(
        ForeignKey("match_rounds.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    attempts_used: Mapped[int] = mapped_column(Integer, default=0)
    # Pontuação total da rodada (base + bônus de velocidade no multiplayer).
    score: Mapped[int] = mapped_column(Integer, default=0)
    speed_bonus: Mapped[int] = mapped_column(Integer, default=0)
    # Multiplayer: milissegundos entre o início da rodada e o acerto.
    response_ms: Mapped[int | None] = mapped_column(Integer)
    # in_progress | won | lost
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    track: Mapped[MusicTrack] = relationship()
    challenge: Mapped[DailyChallenge | None] = relationship()
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
    # Palpite errado, mas de uma música do mesmo artista da resposta (fica amarelo).
    same_artist: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    game: Mapped[GameSession] = relationship(back_populates="guesses")
