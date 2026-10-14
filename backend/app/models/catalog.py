from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class CatalogSource(Base):
    """Origem documentada de uma lista de referência (ranking ou curadoria)."""

    __tablename__ = "catalog_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # "editorial" = curadoria; "chart" = ranking publicado com posições documentadas.
    kind: Mapped[str] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(String(500))
    retrieved_on: Mapped[date | None] = mapped_column(Date)
    methodology: Mapped[str] = mapped_column(Text, default="")


class MusicTrack(Base):
    """Uma música do catálogo. Dados secretos: nunca serializar antes do fim da partida."""

    __tablename__ = "music_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Chave estável vinda do JSON do catálogo (ex.: "queen--bohemian-rhapsody").
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    # "main" (catálogo real) ou "demo" (domínio público sintetizado).
    edition: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(200))
    artist: Mapped[str] = mapped_column(String(200), index=True)
    primary_category: Mapped[str] = mapped_column(String(20))
    extra_genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Identificador externo (ex.: id da faixa no Deezer), resolvido sob demanda.
    external_provider: Mapped[str | None] = mapped_column(String(20))
    external_id: Mapped[str | None] = mapped_column(String(64))
    external_url: Mapped[str | None] = mapped_column(String(500))
    cover_url: Mapped[str | None] = mapped_column(String(500))
    # Id da faixa no Spotify (catálogo importado do kworb). Usado apenas para o link
    # "Ouvir no Spotify" depois da partida; o áudio do jogo não vem do Spotify.
    spotify_id: Mapped[str | None] = mapped_column(String(32))
    # Referência interna de áudio (melodia do modo demo ou arquivo local).
    audio_ref: Mapped[str | None] = mapped_column(String(200))
    license_note: Mapped[str] = mapped_column(Text, default="")
    # unknown | available | unavailable
    availability: Mapped[str] = mapped_column(String(20), default="unknown")
    availability_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    entries: Mapped[list[CatalogEntry]] = relationship(back_populates="track")


class CatalogEntry(Base):
    """Participação de uma música na lista de referência de uma categoria."""

    __tablename__ = "catalog_entries"
    __table_args__ = (UniqueConstraint("category", "track_id", name="uq_entry_category_track"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("music_tracks.id", ondelete="CASCADE"))
    # Posição no ranking de referência, apenas quando documentada pela fonte.
    reference_rank: Mapped[int | None] = mapped_column(Integer)
    source_id: Mapped[str] = mapped_column(ForeignKey("catalog_sources.id"))
    active: Mapped[bool] = mapped_column(default=True)

    track: Mapped[MusicTrack] = relationship(back_populates="entries")
    source: Mapped[CatalogSource] = relationship()
