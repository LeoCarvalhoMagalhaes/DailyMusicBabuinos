"""Ponto de entrada da API Músicas Babuínas."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api.routes import endless, games, public
from app.audio import build_provider
from app.core.clock import Clock
from app.core.config import DEV_SECRET, Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.rate_limit import RateLimiter
from app.database.migrate import upgrade_to_head
from app.database.session import build_engine, build_session_factory
from app.services.catalog import sync_catalog

logger = logging.getLogger("babuinos")


def create_app(settings: Settings | None = None, *, clock: Clock | None = None,
               run_migrations: bool = True) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if run_migrations:
            upgrade_to_head(settings.database_url)
        if settings.auto_sync_catalog:
            with app.state.session_factory() as db:
                summary = sync_catalog(db)
                logger.info("Catálogo sincronizado: %s", summary)
        if settings.challenge_secret == DEV_SECRET:
            logger.warning("CHALLENGE_SECRET padrão de desenvolvimento em uso.")
        logger.info("Provedor de áudio: %s | edição do catálogo: %s",
                    app.state.audio_provider.name, settings.catalog_edition)
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="Músicas Babuínas API",
        version=public.VERSION,
        description="API do jogo diário de adivinhação musical Músicas Babuínas.",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.app_env != "production" else None,
    )
    engine = build_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.clock = clock or Clock(settings.tz)
    app.state.audio_provider = build_provider(settings)
    app.state.rate_limiter = RateLimiter(settings.rate_limit_enabled)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Player-Token"],
        expose_headers=["X-Clip-Duration", "Retry-After"],
        max_age=600,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/") and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response

    install_error_handlers(app)
    app.include_router(public.router)
    app.include_router(games.router)
    app.include_router(endless.router)
    return app


app = create_app()
