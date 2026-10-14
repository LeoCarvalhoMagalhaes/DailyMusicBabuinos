"""Rotas do multiplayer: conta, salas, partida e WebSocket.

Toda ação competitiva passa por aqui e é validada no servidor; as respostas trazem o
estado novo da sala para quem agiu, e o WebSocket avisa os demais.
"""

from __future__ import annotations

import asyncio
import contextlib
import json

import anyio
from fastapi import APIRouter, Depends, Query, Request, Response, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.deps import (
    _extract_token,
    client_ip,
    current_account,
    get_clock,
    get_db,
    get_hub,
    get_limiter,
    get_provider,
    get_settings,
)
from app.api.mp_presenter import room_state
from app.audio.base import AudioProvider
from app.core.clock import Clock
from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.models import Account, Room
from app.realtime import RealtimeHub
from app.schemas import (
    AccountOut,
    AuthOut,
    CreateRoomIn,
    JoinRoomIn,
    LoginIn,
    MatchGuessIn,
    MatchGuessResult,
    MatchSkipIn,
    OrderIn,
    ReadyIn,
    RegisterIn,
    RoomStateOut,
)
from app.services import accounts
from app.services import multiplayer as mp

router = APIRouter(prefix="/api")


def _account_out(account: Account) -> AccountOut:
    return AccountOut(id=account.id, username=account.username,
                      display_name=account.display_name)


# ------------------------------------------------------------------- conta

@router.post("/auth/register", response_model=AuthOut, status_code=201, tags=["conta"])
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db),
             settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
             limiter: RateLimiter = Depends(get_limiter)) -> AuthOut:
    limiter.hit(f"auth:{client_ip(request)}", settings.rate_limit_auth_per_hour, 3600)
    account, token = accounts.register(db, body.username, body.password, body.display_name,
                                       clock.now(), settings.auth_session_days)
    return AuthOut(token=token, account=_account_out(account))


@router.post("/auth/login", response_model=AuthOut, tags=["conta"])
def login(body: LoginIn, request: Request, db: Session = Depends(get_db),
          settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
          limiter: RateLimiter = Depends(get_limiter)) -> AuthOut:
    limiter.hit(f"auth:{client_ip(request)}", settings.rate_limit_auth_per_hour, 3600)
    limiter.hit(f"login:{accounts.normalize_username(body.username)}",
                settings.rate_limit_auth_per_hour, 3600)
    account, token = accounts.login(db, body.username, body.password, clock.now(),
                                    settings.auth_session_days)
    return AuthOut(token=token, account=_account_out(account))


@router.post("/auth/logout", status_code=204, tags=["conta"])
def logout(request: Request, db: Session = Depends(get_db),
           account: Account = Depends(current_account)) -> Response:
    token = _extract_token(request.headers.get("authorization"), None)
    if token:
        accounts.logout(db, token)
    return Response(status_code=204)


@router.get("/auth/me", response_model=AccountOut, tags=["conta"])
def me(account: Account = Depends(current_account)) -> AccountOut:
    return _account_out(account)


# -------------------------------------------------------------------- salas

def _state(db: Session, settings: Settings, provider: AudioProvider, clock: Clock,
           hub: RealtimeHub, room: Room, account: Account) -> RoomStateOut:
    db.refresh(room)
    return room_state(db, settings, provider, clock, room, account, hub.connected(room.id))


def _room(db: Session, code: str, account: Account) -> Room:
    room = mp.find_room(db, code)
    mp.require_member(room, account)
    return room


@router.post("/mp/rooms", response_model=RoomStateOut, status_code=201, tags=["multiplayer"])
def create_room(body: CreateRoomIn, db: Session = Depends(get_db),
                settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
                provider: AudioProvider = Depends(get_provider),
                hub: RealtimeHub = Depends(get_hub),
                limiter: RateLimiter = Depends(get_limiter),
                account: Account = Depends(current_account)) -> RoomStateOut:
    limiter.hit(f"rooms:{account.id}", 20, 3600)
    room = mp.create_room(db, account, body.category_order, clock.now())
    return _state(db, settings, provider, clock, hub, room, account)


@router.post("/mp/rooms/join", response_model=RoomStateOut, tags=["multiplayer"])
def join_room(body: JoinRoomIn, db: Session = Depends(get_db),
              settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
              provider: AudioProvider = Depends(get_provider),
              hub: RealtimeHub = Depends(get_hub), limiter: RateLimiter = Depends(get_limiter),
              account: Account = Depends(current_account)) -> RoomStateOut:
    # Limita tentativas de adivinhar códigos de convite.
    limiter.hit(f"join:{account.id}", 30, 600)
    room = mp.join_room(db, settings, account, body.code, clock.now())
    return _state(db, settings, provider, clock, hub, room, account)


@router.get("/mp/rooms/{code}", response_model=RoomStateOut, tags=["multiplayer"])
def get_room(code: str, db: Session = Depends(get_db),
             settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
             provider: AudioProvider = Depends(get_provider),
             hub: RealtimeHub = Depends(get_hub),
             account: Account = Depends(current_account)) -> RoomStateOut:
    """Estado completo (usado ao abrir a sala, ao reconectar e como reserva do WebSocket)."""
    room = _room(db, code, account)
    now = clock.now()
    mp.advance(db, settings, room, now)
    member = mp.require_member(room, account)
    mp.touch(member, now)
    db.commit()
    return _state(db, settings, provider, clock, hub, room, account)


@router.post("/mp/rooms/{code}/ready", response_model=RoomStateOut, tags=["multiplayer"])
def ready(code: str, body: ReadyIn, db: Session = Depends(get_db),
          settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
          provider: AudioProvider = Depends(get_provider), hub: RealtimeHub = Depends(get_hub),
          account: Account = Depends(current_account)) -> RoomStateOut:
    room = _room(db, code, account)
    mp.set_ready(db, account, room, body.ready, clock.now())
    return _state(db, settings, provider, clock, hub, room, account)


@router.post("/mp/rooms/{code}/order", response_model=RoomStateOut, tags=["multiplayer"])
def order(code: str, body: OrderIn, db: Session = Depends(get_db),
          settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
          provider: AudioProvider = Depends(get_provider), hub: RealtimeHub = Depends(get_hub),
          account: Account = Depends(current_account)) -> RoomStateOut:
    room = _room(db, code, account)
    mp.set_order(db, account, room, list(body.category_order), clock.now())
    return _state(db, settings, provider, clock, hub, room, account)


@router.post("/mp/rooms/{code}/start", response_model=RoomStateOut, tags=["multiplayer"])
def start(code: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
          clock: Clock = Depends(get_clock), provider: AudioProvider = Depends(get_provider),
          hub: RealtimeHub = Depends(get_hub),
          account: Account = Depends(current_account)) -> RoomStateOut:
    room = _room(db, code, account)
    mp.start_match(db, settings, provider, account, room, clock.today(), clock.now())
    return _state(db, settings, provider, clock, hub, room, account)


@router.post("/mp/rooms/{code}/leave", status_code=204, tags=["multiplayer"])
def leave(code: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
          clock: Clock = Depends(get_clock),
          account: Account = Depends(current_account)) -> Response:
    room = _room(db, code, account)
    mp.leave_room(db, settings, account, room, clock.now())
    return Response(status_code=204)


@router.post("/mp/rooms/{code}/guess", response_model=MatchGuessResult, tags=["multiplayer"])
def guess(code: str, body: MatchGuessIn, db: Session = Depends(get_db),
          settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
          provider: AudioProvider = Depends(get_provider), hub: RealtimeHub = Depends(get_hub),
          limiter: RateLimiter = Depends(get_limiter),
          account: Account = Depends(current_account)) -> MatchGuessResult:
    limiter.hit(f"guess:{account.id}", settings.rate_limit_guess_per_minute, 60)
    room = _room(db, code, account)
    _, correct = mp.match_guess(db, settings, account, room, body.round, body.guess,
                                body.attempt, clock.now())
    return MatchGuessResult(correct=correct,
                            state=_state(db, settings, provider, clock, hub, room, account))


@router.post("/mp/rooms/{code}/skip", response_model=RoomStateOut, tags=["multiplayer"])
def skip(code: str, body: MatchSkipIn, db: Session = Depends(get_db),
         settings: Settings = Depends(get_settings), clock: Clock = Depends(get_clock),
         provider: AudioProvider = Depends(get_provider), hub: RealtimeHub = Depends(get_hub),
         limiter: RateLimiter = Depends(get_limiter),
         account: Account = Depends(current_account)) -> RoomStateOut:
    limiter.hit(f"guess:{account.id}", settings.rate_limit_guess_per_minute, 60)
    room = _room(db, code, account)
    mp.match_skip(db, settings, account, room, body.round, body.attempt, clock.now())
    return _state(db, settings, provider, clock, hub, room, account)


@router.get("/mp/rooms/{code}/rounds/{number}/audio", tags=["multiplayer"],
            responses={200: {"content": {"audio/mpeg": {}, "audio/wav": {}}}})
def audio(code: str, number: int, stage: int = Query(ge=1, le=50),
          db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
          clock: Clock = Depends(get_clock), provider: AudioProvider = Depends(get_provider),
          limiter: RateLimiter = Depends(get_limiter),
          account: Account = Depends(current_account)) -> Response:
    """Mesmo áudio dos outros modos: só o trecho liberado, sem metadados."""
    limiter.hit(f"audio:{account.id}", settings.rate_limit_audio_per_minute, 60)
    room = _room(db, code, account)
    track, seconds, category = mp.match_audio(db, settings, account, room, number, stage,
                                              clock.now())
    clip = provider.get_clip(track, seconds, category=category)
    db.commit()
    return Response(content=clip.data, media_type=clip.media_type, headers={
        "Cache-Control": "no-store",
        "X-Clip-Duration": f"{clip.duration:.3f}",
    })


# ---------------------------------------------------------------- WebSocket

def _authorize_socket(app, token: str, code: str) -> tuple[str, str, str] | None:
    """Roda numa thread: valida token e sala; devolve (sala, conta, estado inicial)."""
    settings, provider, clock = app.state.settings, app.state.audio_provider, app.state.clock
    hub: RealtimeHub = app.state.realtime
    with app.state.session_factory() as db:
        account = accounts.account_for_token(db, token, clock.now())
        if account is None:
            return None
        try:
            room = mp.find_room(db, code)
        except Exception:  # noqa: BLE001 - sala inexistente
            return None
        member = mp.member_of(room, account)
        if member is None:
            return None
        mp.touch(member, clock.now())
        db.commit()
        connected = hub.connected(room.id) | {account.id}
        state = room_state(db, settings, provider, clock, room, account, connected)
        return room.id, account.id, '{"type":"state","state":' + state.model_dump_json() + "}"


@router.websocket("/mp/ws")
async def websocket(ws: WebSocket) -> None:
    """Protocolo: o cliente envia {"type":"auth","token":...,"room":"CÓDIGO"} (o token
    não vai na URL, que pode parar em logs); o servidor responde com o estado e depois
    envia {"type":"state",...} a cada mudança. {"type":"ping"} recebe {"type":"pong"}."""
    await ws.accept()
    hub: RealtimeHub = ws.app.state.realtime
    try:
        hello = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=10))
        auth = await anyio.to_thread.run_sync(_authorize_socket, ws.app,
                                              str(hello.get("token", "")),
                                              str(hello.get("room", "")))
    except (TimeoutError, ValueError, WebSocketDisconnect, AttributeError):
        auth = None
    if auth is None:
        with contextlib.suppress(Exception):
            await ws.close(code=4401, reason="Sessão ou sala inválida")
        return
    room_id, account_id, initial = auth
    hub.add(room_id, ws, account_id)
    try:
        await ws.send_text(initial)
        while True:
            message = await ws.receive_text()
            if '"ping"' in message:
                await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(room_id, ws)
