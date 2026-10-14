"""Dependências compartilhadas pelas rotas (banco, configuração, jogador, limites)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.audio.base import AudioProvider
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.core.rate_limit import RateLimiter
from app.models import Account, Player
from app.realtime import RealtimeHub
from app.repositories.players import find_by_token
from app.services.accounts import account_for_token


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_provider(request: Request) -> AudioProvider:
    return request.app.state.audio_provider


def get_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _extract_token(authorization: str | None, x_player_token: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return x_player_token.strip() if x_player_token else None


def optional_player(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_player_token: str | None = Header(default=None),
) -> Player | None:
    token = _extract_token(authorization, x_player_token)
    return find_by_token(db, token) if token else None


def current_player(player: Player | None = Depends(optional_player)) -> Player:
    if player is None:
        raise UnauthorizedError("Identificação do jogador ausente ou inválida.",
                                code="invalid_player")
    return player


def current_account(
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
    authorization: str | None = Header(default=None),
) -> Account:
    """Conta do multiplayer (token de login, diferente do token anônimo do jogador)."""
    account = account_for_token(db, _extract_token(authorization, None), clock.now())
    if account is None:
        raise UnauthorizedError("Entre na sua conta para jogar o multiplayer.",
                                code="login_required")
    return account


def get_hub(request: Request) -> RealtimeHub:
    return request.app.state.realtime
