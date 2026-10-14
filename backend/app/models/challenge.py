from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.catalog import MusicTrack


class DailyChallenge(Base):
    """Desafio de uma categoria em uma data. A restrição única garante que todos os
    servidores e jogadores enxerguem a mesma música para (data, categoria, edição)."""

    __tablename__ = "daily_challenges"
    __table_args__ = (
        UniqueConstraint("challenge_date", "category", "edition", name="uq_challenge_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(20))
    edition: Mapped[str] = mapped_column(String(10))
    track_id: Mapped[int] = mapped_column(ForeignKey("music_tracks.id"), index=True)
    # published | withdrawn (retirado manualmente, ex.: áudio indisponível)
    status: Mapped[str] = mapped_column(String(20), default="published")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    track: Mapped[MusicTrack] = relationship()
