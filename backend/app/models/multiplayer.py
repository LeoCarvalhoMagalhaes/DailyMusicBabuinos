"""Contas, salas e partidas do modo multiplayer.

O estado da sala e da partida vive no banco (fonte da verdade). O servidor em tempo
real (WebSocket) só avisa os clientes quando esse estado muda; perder a conexão não
perde nada, e um jogador que volta recebe o estado completo de novo.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.catalog import MusicTrack


class Account(Base):
    """Conta de jogador do multiplayer. Cada conta tem um `Player` próprio, dono das
    rodadas multiplayer (assim a mecânica de partida é a mesma dos outros modos)."""

    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Nome de login, sempre em minúsculas.
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(24))
    # scrypt$n$r$p$sal$hash (ver core.security).
    password_hash: Mapped[str] = mapped_column(String(200))
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    """Sessão de login. Guardamos só o SHA-256 do token, como no jogador anônimo."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"),
                                            index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    account: Mapped[Account] = relationship()


class Room(Base):
    """Sala multiplayer. Estados: waiting (sala de espera, inclusive entre partidas),
    playing (partida em andamento) e closed (vazia ou inativa)."""

    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Código de convite aleatório (ver services.rooms.new_room_code).
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    host_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    status: Mapped[str] = mapped_column(String(10), default="waiting")
    category_order: Mapped[list[str]] = mapped_column(JSON)
    current_match_id: Mapped[str | None] = mapped_column(String(36))
    # Incrementado a cada mudança de estado: o servidor em tempo real compara versões
    # para saber quando avisar os clientes.
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    members: Mapped[list[RoomMember]] = relationship(
        back_populates="room", order_by="RoomMember.joined_at", cascade="all, delete-orphan"
    )


class RoomMember(Base):
    """Participante de uma sala. Único por (sala, conta): reconectar nunca duplica."""

    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "account_id", name="uq_member_room_account"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    ready: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Preenchido quando o jogador sai durante uma partida (continua no placar).
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    room: Mapped[Room] = relationship(back_populates="members")
    account: Mapped[Account] = relationship()

    @property
    def active(self) -> bool:
        return self.left_at is None


class Match(Base):
    """Partida: 6 categorias x 3 músicas = 18 rodadas. `phase` alterna entre playing
    (rodada aberta para palpites até `phase_ends_at`) e reveal (resposta à mostra)."""

    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    # playing | finished | abandoned
    status: Mapped[str] = mapped_column(String(12), default="playing")
    current_round: Mapped[int] = mapped_column(Integer, default=1)
    phase: Mapped[str] = mapped_column(String(10), default="playing")
    phase_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    phase_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Contas que disputaram a partida (para o placar, mesmo depois de saírem).
    participant_ids: Mapped[list[str]] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rounds: Mapped[list[MatchRound]] = relationship(
        back_populates="match", order_by="MatchRound.number", cascade="all, delete-orphan"
    )


class MatchRound(Base):
    __tablename__ = "match_rounds"
    __table_args__ = (UniqueConstraint("match_id", "number", name="uq_round_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"),
                                          index=True)
    number: Mapped[int] = mapped_column(Integer)  # 1..18
    category: Mapped[str] = mapped_column(String(20))
    track_id: Mapped[int] = mapped_column(ForeignKey("music_tracks.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    match: Mapped[Match] = relationship(back_populates="rounds")
    track: Mapped[MusicTrack] = relationship()
