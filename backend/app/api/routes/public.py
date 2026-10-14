"""Rotas públicas: saúde, jogador anônimo, categorias, desafio diário e busca."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import (
    client_ip,
    current_player,
    get_clock,
    get_db,
    get_limiter,
    get_provider,
    get_settings,
    optional_player,
)
from app.api.presenters import audio_info, category_out, rules_out
from app.audio.base import AudioProvider
from app.core.categories import CATEGORIES, CATEGORY_BY_SLUG
from app.core.clock import Clock, as_utc
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.core.rate_limit import RateLimiter
from app.models import Player
from app.repositories.games import games_for_day
from app.repositories.players import create_player
from app.schemas import (
    CategoryDailyStatus,
    CategoryOut,
    DailyChallengeOut,
    DailyOverview,
    HealthOut,
    PlayerCreated,
    PlayerOut,
    SongSuggestion,
)
from app.services.catalog import catalog_index
from app.services.daily import challenge_number

VERSION = "1.0.0"
router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthOut, tags=["infra"])
def health(db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
           provider: AudioProvider = Depends(get_provider)) -> HealthOut:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - health check não pode lançar
        database = "error"
    return HealthOut(status="ok" if database == "ok" else "degraded", database=database,
                     audio_provider=provider.name, catalog_edition=settings.catalog_edition,
                     version=VERSION)


@router.post("/players", response_model=PlayerCreated, status_code=201, tags=["jogador"])
def new_player(request: Request, db: Session = Depends(get_db),
               settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
               limiter: RateLimiter = Depends(get_limiter)) -> PlayerCreated:
    limiter.hit(f"players:{client_ip(request)}", settings.rate_limit_players_per_hour, 3600)
    player, token = create_player(db, clock.now())
    return PlayerCreated(player_id=player.id, token=token)


@router.get("/players/me", response_model=PlayerOut, tags=["jogador"])
def me(player: Player = Depends(current_player)) -> PlayerOut:
    return PlayerOut(player_id=player.id, created_at=as_utc(player.created_at))


@router.get("/categories", response_model=list[CategoryOut], tags=["desafio"])
def categories() -> list[CategoryOut]:
    return [category_out(c.slug) for c in CATEGORIES]


@router.get("/daily", response_model=DailyOverview, tags=["desafio"])
def daily_overview(db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
                   clock: Clock = Depends(get_clock),
                   provider: AudioProvider = Depends(get_provider),
                   player: Player | None = Depends(optional_player)) -> DailyOverview:
    today = clock.today()
    by_category = {}
    if player is not None:
        by_category = {g.challenge.category: g
                       for g in games_for_day(db, player.id, today, settings.catalog_edition)}
        now = clock.now()
        if now - as_utc(player.last_seen_at) > timedelta(hours=12):
            player.last_seen_at = now
            db.commit()
    statuses = []
    for cat in CATEGORIES:
        game = by_category.get(cat.slug)
        statuses.append(CategoryDailyStatus(
            slug=cat.slug, name=cat.name, description=cat.description,
            status=game.status if game else "not_started",  # type: ignore[arg-type]
            attempts_used=game.attempts_used if game else 0,
            score=game.score if game else 0,
            game_id=game.id if game else None,
        ))
    return DailyOverview(date=today, timezone=settings.challenge_timezone,
                         challenge_number=challenge_number(settings, today),
                         server_time=clock.now(), next_reset_at=clock.next_reset(),
                         audio=audio_info(provider), rules=rules_out(settings),
                         categories=statuses)


@router.get("/daily/{category}", response_model=DailyChallengeOut, tags=["desafio"])
def daily_challenge(category: str, settings: Settings = Depends(get_settings),
                    clock: Clock = Depends(get_clock),
                    provider: AudioProvider = Depends(get_provider)) -> DailyChallengeOut:
    if category not in CATEGORY_BY_SLUG:
        raise NotFoundError("Categoria inexistente.", code="unknown_category")
    today = clock.today()
    return DailyChallengeOut(category=category_out(category), date=today,
                             challenge_number=challenge_number(settings, today),
                             server_time=clock.now(), next_reset_at=clock.next_reset(),
                             audio=audio_info(provider), rules=rules_out(settings))


@router.get("/songs/search", response_model=list[SongSuggestion], tags=["desafio"])
def search_songs(request: Request, q: str = Query(min_length=1, max_length=80),
                 db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
                 limiter: RateLimiter = Depends(get_limiter)) -> list[SongSuggestion]:
    """Sugestões de títulos. A busca percorre o catálogo inteiro da edição (todas as
    categorias), para que a lista não denuncie qual música é a do dia."""
    limiter.hit(f"search:{client_ip(request)}", settings.rate_limit_search_per_minute, 60)
    results = catalog_index.search(db, settings.catalog_edition, q, limit=8)
    return [SongSuggestion(id=t.slug, title=t.title, artist=t.artist) for t in results]
