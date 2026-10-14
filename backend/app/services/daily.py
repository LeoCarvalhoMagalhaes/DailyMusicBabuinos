"""Seleção do desafio diário.

Estratégia híbrida (determinística + persistida):
1. As músicas candidatas de (categoria, data) são ordenadas por
   HMAC-SHA256(CHALLENGE_SECRET, "edição|categoria|data|slug"). Sem o segredo não dá
   para prever a ordem, e com ele qualquer servidor chega ao mesmo resultado.
2. Filtros contra repetição: a faixa não pode ter sido desafio (em qualquer
   categoria) nos últimos REPEAT_WINDOW_DAYS dias, nem ser desafio de outra categoria
   no mesmo dia; o artista não pode repetir na mesma categoria dentro de
   ARTIST_COOLDOWN_DAYS. Se o catálogo for pequeno demais, os filtros são relaxados
   escolhendo a faixa usada há mais tempo.
3. O resultado é gravado em `daily_challenges`, com restrição única por
   (data, categoria, edição). A partir daí o banco é a fonte da verdade: mudanças no
   catálogo não alteram desafios já publicados, e corridas entre servidores são
   resolvidas pela restrição única.
4. Desafios só são criados para a data corrente do servidor; o cliente nunca envia
   a data, o que impede manipulação de calendário.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audio.base import AudioProvider
from app.core.config import Settings
from app.core.errors import AppError, AudioUnavailableError, NotFoundError
from app.core.security import hmac_hex
from app.models import CatalogEntry, DailyChallenge, MusicTrack

logger = logging.getLogger("babuinos.daily")

MAX_AVAILABILITY_CHECKS = 12


def challenge_number(settings: Settings, day: date) -> int:
    return (day - settings.launch_date).days + 1


def candidates(db: Session, category: str, edition: str) -> list[MusicTrack]:
    """Faixas ativas da categoria que não foram marcadas como sem áudio."""
    return list(
        db.scalars(
            select(MusicTrack)
            .join(CatalogEntry, CatalogEntry.track_id == MusicTrack.id)
            .where(
                CatalogEntry.category == category,
                CatalogEntry.active.is_(True),
                MusicTrack.edition == edition,
                MusicTrack.availability != "unavailable",
            )
        )
    )


def _history(db: Session, edition: str, day: date, days: int) -> list[DailyChallenge]:
    return list(
        db.scalars(
            select(DailyChallenge)
            .where(
                DailyChallenge.edition == edition,
                DailyChallenge.challenge_date >= day - timedelta(days=days),
                DailyChallenge.challenge_date <= day,
            )
            .order_by(DailyChallenge.challenge_date)
        )
    )


def rank_candidates(settings: Settings, edition: str, category: str, day: date,
                    tracks: list[MusicTrack]) -> list[MusicTrack]:
    def key(track: MusicTrack) -> str:
        return hmac_hex(settings.challenge_secret, f"{edition}|{category}|{day}|{track.slug}")

    return sorted(tracks, key=key)


def select_track(db: Session, settings: Settings, provider: AudioProvider, category: str,
                 day: date) -> MusicTrack:
    edition = settings.catalog_edition
    tracks = candidates(db, category, edition)
    if not tracks:
        raise NotFoundError("Não há músicas disponíveis para esta categoria.",
                            code="empty_catalog")
    window = max(settings.repeat_window_days, settings.artist_cooldown_days)
    history = _history(db, edition, day, window)
    last_used: dict[int, date] = {}
    same_day: set[int] = set()
    recent_artists: set[str] = set()
    for ch in history:
        if ch.challenge_date == day:
            same_day.add(ch.track_id)
            continue
        last_used[ch.track_id] = max(last_used.get(ch.track_id, date.min), ch.challenge_date)
        artist_window = day - timedelta(days=settings.artist_cooldown_days)
        if ch.category == category and ch.challenge_date >= artist_window:
            recent_artists.add(ch.track.artist.casefold())

    repeat_limit = day - timedelta(days=settings.repeat_window_days)
    ranked = rank_candidates(settings, edition, category, day, tracks)
    strict = [
        t for t in ranked
        if t.id not in same_day
        and last_used.get(t.id, date.min) < repeat_limit
        and t.artist.casefold() not in recent_artists
    ]
    if strict:
        ordered = strict
    else:
        # Catálogo pequeno (ex.: modo demo): usa a faixa que está há mais tempo sem sair.
        pool = [t for t in ranked if t.id not in same_day] or ranked
        position = {t.id: i for i, t in enumerate(ranked)}
        ordered = sorted(pool, key=lambda t: (last_used.get(t.id, date.min), position[t.id]))

    track = first_playable(db, provider, ordered)
    if track is None:
        raise AppError("Nenhuma música com áudio disponível para hoje.",
                       code="no_playable_track", status_code=503)
    return track


def first_playable(db: Session, provider: AudioProvider, ordered: list[MusicTrack]
                   ) -> MusicTrack | None:
    """Primeira faixa da lista com áudio confirmado no provedor. Usado pelos três
    modos de jogo, para que todos só sorteiem músicas que tocam."""
    # Limita quantas faixas ainda não verificadas consultamos no provedor por sorteio.
    unchecked = [t.id for t in ordered if t.availability != "available"]
    checkable = set(unchecked[:MAX_AVAILABILITY_CHECKS])
    for track in ordered:
        if track.availability == "available":
            return track
        if track.id not in checkable:
            break
        try:
            if provider.check_availability(track):
                db.flush()
                return track
        except AudioUnavailableError:
            # Provedor fora do ar: não dá para validar, usa a melhor candidata e o
            # jogador pode tentar ouvir de novo mais tarde (tentativas não são consumidas).
            logger.warning("Provedor indisponível ao validar %s; seguindo sem validação",
                           track.slug)
            return track
        db.flush()
    return None


def get_challenge(db: Session, category: str, day: date, edition: str) -> DailyChallenge | None:
    return db.scalar(
        select(DailyChallenge).where(
            DailyChallenge.challenge_date == day,
            DailyChallenge.category == category,
            DailyChallenge.edition == edition,
        )
    )


def get_or_create_challenge(db: Session, settings: Settings, provider: AudioProvider,
                            category: str, day: date, now: datetime) -> DailyChallenge:
    edition = settings.catalog_edition
    existing = get_challenge(db, category, day, edition)
    if existing:
        return existing
    track = select_track(db, settings, provider, category, day)
    challenge = DailyChallenge(challenge_date=day, category=category, edition=edition,
                               track_id=track.id, status="published", created_at=now)
    db.add(challenge)
    try:
        db.commit()
    except IntegrityError:
        # Outro processo publicou o desafio ao mesmo tempo: vale o que está no banco.
        db.rollback()
        existing = get_challenge(db, category, day, edition)
        if existing is None:  # pragma: no cover - estado impossível
            raise
        return existing
    return challenge
