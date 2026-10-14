"""Multiplayer: salas de 2 a 8 jogadores e partidas de 18 músicas (6 categorias x 3).

Regras (detalhes e fórmula de pontuação em docs/06-modos-de-jogo.md):
- O servidor é a autoridade: escolhe as músicas, controla o tempo de cada rodada,
  valida palpites e calcula pontos. O cliente só envia "palpite" e "pular".
- Cada rodada é uma `GameSession` (mode = "match") por jogador, com a mesma mecânica
  dos outros modos: seis tentativas e trechos progressivos individuais.
- Fases: `playing` (até `mp_round_seconds` ou até todos terminarem) e `reveal`
  (resposta à mostra por `mp_reveal_seconds`); depois vem a próxima rodada.
- Transições usam compare-and-swap (UPDATE ... WHERE rodada = N AND fase = X): duas
  requisições ou dois laços simultâneos nunca avançam a mesma rodada duas vezes.
- Pontos = tabela base por tentativa (100/80/60/40/20/10) + bônus de velocidade
  floor(mp_speed_bonus_max x tempo restante / tempo da rodada), só em acertos.
- Reconexão: o membro da sala é único por conta; voltar só retoma o estado. Sair
  durante a partida não a interrompe; quem saiu continua no placar.
"""

from __future__ import annotations

import math
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audio.base import AudioProvider
from app.core.categories import CATEGORY_SLUGS
from app.core.clock import as_utc
from app.core.config import Settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import (
    MODE_MATCH,
    Account,
    GameSession,
    Match,
    MatchRound,
    MusicTrack,
    Room,
    RoomMember,
)
from app.services.endless import pick_track, todays_daily_track_ids
from app.services.game import apply_guess, apply_skip, check_audio_access, new_session

ROUNDS_PER_CATEGORY = 3
# Sem letras/números parecidos (0/O, 1/I/L): 31^6 ≈ 887 milhões de códigos.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
TOUCH_INTERVAL = timedelta(seconds=20)


def new_room_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def validate_order(order: list[str] | None) -> list[str]:
    if not order:
        return list(CATEGORY_SLUGS)
    if sorted(order) != sorted(CATEGORY_SLUGS):
        raise ConflictError("A ordem precisa ter as seis categorias, uma vez cada.",
                            code="invalid_order")
    return list(order)


# ------------------------------------------------------------------- salas

def find_room(db: Session, code: str) -> Room:
    room = db.scalar(select(Room).where(Room.code == code.strip().upper()[:12]))
    if room is None or room.status == "closed":
        raise NotFoundError("Sala não encontrada. Confira o código.", code="room_not_found")
    return room


def member_of(room: Room, account: Account) -> RoomMember | None:
    return next((m for m in room.members if m.account_id == account.id), None)


def require_member(room: Room, account: Account) -> RoomMember:
    member = member_of(room, account)
    if member is None:
        # Não revelamos nada sobre salas de que a pessoa não participa.
        raise NotFoundError("Sala não encontrada. Confira o código.", code="room_not_found")
    return member


def active_members(room: Room) -> list[RoomMember]:
    return [m for m in room.members if m.active]


def bump(room: Room, now: datetime) -> None:
    room.version = (room.version or 0) + 1
    room.updated_at = now


def touch(member: RoomMember, now: datetime) -> None:
    """Marca o jogador como presente (no máximo uma escrita a cada 20 s)."""
    if now - as_utc(member.last_seen_at) >= TOUCH_INTERVAL:
        member.last_seen_at = now


def create_room(db: Session, account: Account, order: list[str] | None, now: datetime) -> Room:
    order = validate_order(order)
    for _ in range(10):
        room = Room(id=str(uuid.uuid4()), code=new_room_code(), host_account_id=account.id,
                    status="waiting", category_order=order, version=1, created_at=now,
                    updated_at=now)
        room.members.append(RoomMember(account_id=account.id, ready=True, joined_at=now,
                                       last_seen_at=now))
        db.add(room)
        try:
            db.commit()
            return room
        except IntegrityError:  # código repetido (raríssimo): sorteia outro
            db.rollback()
    raise ConflictError("Não foi possível criar a sala. Tente de novo.",
                        code="room_code_exhausted")  # pragma: no cover


def join_room(db: Session, settings: Settings, account: Account, code: str,
              now: datetime) -> Room:
    room = find_room(db, code)
    member = member_of(room, account)
    if room.status == "playing":
        match = db.get(Match, room.current_match_id) if room.current_match_id else None
        if member is None or match is None or account.id not in match.participant_ids:
            raise ConflictError("A partida desta sala já começou. Espere a próxima.",
                                code="match_in_progress")
        # Reconexão de quem já está na partida: nunca cria outro jogador.
        member.left_at = None
        member.last_seen_at = now
        bump(room, now)
        db.commit()
        return room
    if member is not None:
        member.last_seen_at = now
        db.commit()
        return room
    if len(active_members(room)) >= settings.mp_max_players:
        raise ConflictError(f"Sala cheia: o limite é de {settings.mp_max_players} jogadores.",
                            code="room_full")
    room.members.append(RoomMember(account_id=account.id, ready=False, joined_at=now,
                                   last_seen_at=now))
    bump(room, now)
    try:
        db.commit()
    except IntegrityError:  # duas abas entrando ao mesmo tempo
        db.rollback()
    return room


def _transfer_host(room: Room) -> None:
    if any(m.account_id == room.host_account_id and m.active for m in room.members):
        return
    remaining = active_members(room)
    if remaining:
        room.host_account_id = remaining[0].account_id
        remaining[0].ready = True


def leave_room(db: Session, settings: Settings, account: Account, room: Room,
               now: datetime) -> None:
    member = require_member(room, account)
    if room.status == "playing":
        member.left_at = now
        member.ready = False
        match = db.get(Match, room.current_match_id) if room.current_match_id else None
        if match is not None and match.phase == "playing":
            # A rodada em andamento conta como erro; a partida dos outros continua.
            rnd = _round(match, match.current_round)
            game = _session(db, rnd, account)
            if game is not None and not game.finished:
                _close_session(game, now)
    else:
        room.members.remove(member)
        db.delete(member)
        if not room.members:
            room.status = "closed"
    _transfer_host(room)
    bump(room, now)
    db.commit()
    advance(db, settings, room, now)


def set_ready(db: Session, account: Account, room: Room, ready: bool, now: datetime) -> None:
    member = require_member(room, account)
    if room.status != "waiting":
        raise ConflictError("A partida já começou.", code="match_in_progress")
    member.ready = ready or account.id == room.host_account_id
    touch(member, now)
    bump(room, now)
    db.commit()


def set_order(db: Session, account: Account, room: Room, order: list[str], now: datetime) -> None:
    require_member(room, account)
    if account.id != room.host_account_id:
        raise ForbiddenError("Só o anfitrião pode mudar a ordem das categorias.",
                             code="not_host")
    if room.status != "waiting":
        raise ConflictError("A partida já começou.", code="match_in_progress")
    room.category_order = validate_order(order)
    bump(room, now)
    db.commit()


# ----------------------------------------------------------------- partida

def _round(match: Match, number: int) -> MatchRound:
    return next(r for r in match.rounds if r.number == number)


def _session(db: Session, rnd: MatchRound, account: Account) -> GameSession | None:
    return db.scalar(select(GameSession).where(GameSession.match_round_id == rnd.id,
                                               GameSession.player_id == account.player_id))


def _close_session(game: GameSession, now: datetime) -> None:
    """Rodada encerrada sem acerto (tempo esgotado ou saída): conta como erro."""
    game.status = "lost"
    game.score = 0
    game.finished_at = now


def _pick_match_tracks(db: Session, settings: Settings, provider: AudioProvider,
                       order: list[str], today: date, now: datetime) -> list[tuple[str, int]]:
    """Três músicas diferentes por categoria, sem repetir na partida e sem usar músicas
    que são desafio diário hoje (num catálogo pequeno demais, essa última regra cede)."""
    daily = todays_daily_track_ids(db, settings, provider, today, now)
    chosen: list[tuple[str, int]] = []
    used: set[int] = set()
    for category in order:
        for _ in range(ROUNDS_PER_CATEGORY):
            try:
                track = pick_track(db, settings, provider, category, used | daily, [])
            except NotFoundError:
                track = pick_track(db, settings, provider, category, used, [])
            used.add(track.id)
            chosen.append((category, track.id))
    return chosen


def _start_round(db: Session, settings: Settings, match: Match, rnd: MatchRound,
                 members: list[RoomMember], now: datetime) -> None:
    rnd.started_at = now
    rnd.ends_at = now + timedelta(seconds=settings.mp_round_seconds)
    for member in members:
        db.add(new_session(member.account.player_id, rnd.track_id, rnd.category, MODE_MATCH,
                           now, match_round_id=rnd.id))
    db.flush()  # a sessão usa autoflush=False: grava já, antes de conferir quem terminou


def start_match(db: Session, settings: Settings, provider: AudioProvider, account: Account,
                room: Room, today: date, now: datetime) -> Match:
    require_member(room, account)
    if account.id != room.host_account_id:
        raise ForbiddenError("Só o anfitrião pode iniciar a partida.", code="not_host")
    if room.status != "waiting":
        raise ConflictError("A partida já começou.", code="match_in_progress")
    players = active_members(room)
    if len(players) < settings.mp_min_players:
        raise ConflictError(f"São necessários pelo menos {settings.mp_min_players} jogadores.",
                            code="not_enough_players")
    if any(not m.ready for m in players if m.account_id != room.host_account_id):
        raise ConflictError("Todos os jogadores precisam estar prontos.",
                            code="players_not_ready")
    tracks = _pick_match_tracks(db, settings, provider, room.category_order, today, now)
    match = Match(id=str(uuid.uuid4()), room_id=room.id, status="playing", current_round=1,
                  phase="playing", phase_started_at=now,
                  phase_ends_at=now + timedelta(seconds=settings.mp_round_seconds),
                  participant_ids=[m.account_id for m in players], started_at=now)
    for number, (category, track_id) in enumerate(tracks, start=1):
        match.rounds.append(MatchRound(number=number, category=category, track_id=track_id))
    db.add(match)
    db.flush()
    _start_round(db, settings, match, match.rounds[0], players, now)
    room.status = "playing"
    room.current_match_id = match.id
    bump(room, now)
    db.commit()
    return match


def _participants(room: Room, match: Match) -> list[RoomMember]:
    return [m for m in active_members(room) if m.account_id in match.participant_ids]


def _cas(db: Session, match: Match, expect: dict, values: dict) -> bool:
    """Atualiza a partida só se ela ainda estiver no estado esperado."""
    stmt = update(Match).where(Match.id == match.id)
    for column, value in expect.items():
        stmt = stmt.where(getattr(Match, column) == value)
    result = db.execute(stmt.values(**values).execution_options(synchronize_session=False))
    db.refresh(match)
    return result.rowcount == 1


def _step(db: Session, settings: Settings, room: Room, match: Match, now: datetime) -> bool:
    if match.status != "playing":
        return False
    players = _participants(room, match)
    number = match.current_round
    if not players:
        # Todos saíram: a partida é encerrada como abandonada.
        if not _cas(db, match, {"status": "playing", "current_round": number},
                    {"status": "abandoned", "finished_at": now}):
            return False
        room.status = "closed" if not active_members(room) else "waiting"
        return True
    rnd = _round(match, number)
    if match.phase == "playing":
        sessions = list(db.scalars(select(GameSession)
                                   .where(GameSession.match_round_id == rnd.id)))
        active_players = {m.account.player_id for m in players}
        pending = [s for s in sessions if s.player_id in active_players and not s.finished]
        if pending and now < as_utc(match.phase_ends_at):
            return False
        if not _cas(db, match, {"current_round": number, "phase": "playing"},
                    {"phase": "reveal", "phase_started_at": now,
                     "phase_ends_at": now + timedelta(seconds=settings.mp_reveal_seconds)}):
            return False
        for game in sessions:
            if not game.finished:
                _close_session(game, now)
        return True
    # Fase de revelação.
    if now < as_utc(match.phase_ends_at):
        return False
    if number >= len(match.rounds):
        if not _cas(db, match, {"current_round": number, "phase": "reveal",
                                "status": "playing"},
                    {"status": "finished", "finished_at": now}):
            return False
        room.status = "waiting"
        for member in room.members:
            member.ready = member.account_id == room.host_account_id
        return True
    if not _cas(db, match, {"current_round": number, "phase": "reveal"},
                {"current_round": number + 1, "phase": "playing", "phase_started_at": now,
                 "phase_ends_at": now + timedelta(seconds=settings.mp_round_seconds)}):
        return False
    _start_round(db, settings, match, _round(match, number + 1), players, now)
    return True


def advance(db: Session, settings: Settings, room: Room, now: datetime) -> bool:
    """Aplica as transições devidas pelo relógio ou pelo fim da rodada. Idempotente."""
    if room.status != "playing" or not room.current_match_id:
        return False
    match = db.get(Match, room.current_match_id)
    if match is None:  # pragma: no cover - estado impossível
        return False
    changed = False
    for _ in range(4):  # no máximo: fecha a rodada, abre a próxima...
        if not _step(db, settings, room, match, now):
            break
        changed = True
    if changed:
        bump(room, now)
        db.commit()
    return changed


def current_match(db: Session, room: Room) -> Match | None:
    return db.get(Match, room.current_match_id) if room.current_match_id else None


def _open_round(db: Session, settings: Settings, room: Room, account: Account, number: int,
                now: datetime) -> tuple[Match, MatchRound, GameSession]:
    member = require_member(room, account)
    advance(db, settings, room, now)
    match = current_match(db, room)
    if (room.status != "playing" or match is None or match.phase != "playing"
            or match.current_round != number or now >= as_utc(match.phase_ends_at)):
        raise ConflictError("Essa rodada já terminou.", code="round_closed")
    if not member.active:
        raise ConflictError("Você saiu desta partida.", code="left_match")
    rnd = _round(match, number)
    game = db.scalar(select(GameSession).where(GameSession.match_round_id == rnd.id,
                                               GameSession.player_id == account.player_id)
                     .with_for_update())
    if game is None:
        raise ForbiddenError("Você não está nesta rodada.", code="not_in_round")
    touch(member, now)
    return match, rnd, game


def speed_bonus(settings: Settings, rnd: MatchRound, now: datetime) -> int:
    if rnd.ends_at is None:  # pragma: no cover
        return 0
    remaining = (as_utc(rnd.ends_at) - now).total_seconds()
    ratio = max(0.0, min(1.0, remaining / settings.mp_round_seconds))
    return math.floor(settings.mp_speed_bonus_max * ratio)


def match_guess(db: Session, settings: Settings, account: Account, room: Room, number: int,
                text: str, attempt: int, now: datetime) -> tuple[GameSession, bool]:
    _, rnd, game = _open_round(db, settings, room, account, number, now)
    correct = apply_guess(db, settings, game, text, attempt, now, commit=False)
    if correct:
        bonus = speed_bonus(settings, rnd, now)
        game.speed_bonus = bonus
        game.score += bonus
        if rnd.started_at is not None:
            game.response_ms = int((now - as_utc(rnd.started_at)).total_seconds() * 1000)
    bump(room, now)
    db.commit()
    advance(db, settings, room, now)
    return game, correct


def match_skip(db: Session, settings: Settings, account: Account, room: Room, number: int,
               attempt: int, now: datetime) -> GameSession:
    _, _, game = _open_round(db, settings, room, account, number, now)
    apply_skip(db, settings, game, attempt, now, commit=False)
    bump(room, now)
    db.commit()
    advance(db, settings, room, now)
    return game


def match_audio(db: Session, settings: Settings, account: Account, room: Room, number: int,
                stage: int, now: datetime) -> tuple[MusicTrack, float, str]:
    """Trecho da rodada atual. Rodadas futuras nunca são servidas."""
    member = require_member(room, account)
    advance(db, settings, room, now)
    match = current_match(db, room)
    if match is None or match.current_round != number or match.status != "playing":
        raise ConflictError("Essa rodada não está em jogo.", code="round_closed")
    rnd = _round(match, number)
    game = _session(db, rnd, account)
    if game is None:
        raise ForbiddenError("Você não está nesta rodada.", code="not_in_round")
    seconds = check_audio_access(game, settings, stage)
    touch(member, now)
    return rnd.track, seconds, rnd.category


# ------------------------------------------------------- placar e manutenção

@dataclass
class ScoreLine:
    account_id: str
    display_name: str
    total_score: int = 0
    correct: int = 0
    left: bool = False
    per_category: dict[str, dict[str, int]] = field(default_factory=dict)
    response_times: list[int] = field(default_factory=list)
    position: int = 0

    @property
    def average_response_ms(self) -> int | None:
        times = self.response_times
        return round(sum(times) / len(times)) if times else None


def scoreboard(db: Session, room: Room, match: Match) -> list[ScoreLine]:
    accounts = {a.id: a for a in db.scalars(select(Account)
                                            .where(Account.id.in_(match.participant_ids)))}
    by_player = {a.player_id: a.id for a in accounts.values()}
    members = {m.account_id: m for m in room.members}
    lines = {
        account_id: ScoreLine(account_id, accounts[account_id].display_name,
                              left=not (members.get(account_id) and members[account_id].active),
                              per_category={c: {"score": 0, "correct": 0}
                                            for c in room.category_order})
        for account_id in match.participant_ids if account_id in accounts
    }
    rows = db.execute(
        select(GameSession.player_id, GameSession.status, GameSession.score,
               GameSession.response_ms, MatchRound.category)
        .join(MatchRound, MatchRound.id == GameSession.match_round_id)
        .where(MatchRound.match_id == match.id)
    ).all()
    for row in rows:
        line = lines.get(by_player.get(row.player_id, ""))
        if line is None:
            continue
        line.total_score += row.score
        category = line.per_category.setdefault(row.category, {"score": 0, "correct": 0})
        category["score"] += row.score
        if row.status == "won":
            line.correct += 1
            category["correct"] += 1
            if row.response_ms is not None:
                line.response_times.append(row.response_ms)
    ordered = sorted(lines.values(), key=lambda s: (
        -s.total_score, -s.correct,
        s.average_response_ms if s.average_response_ms is not None else math.inf,
        s.display_name.casefold()))
    for position, line in enumerate(ordered, start=1):
        line.position = position
    return ordered


def tick(db: Session, settings: Settings, now: datetime) -> None:
    """Laço do servidor: avança rodadas vencidas e encerra salas e partidas inativas."""
    idle = now - timedelta(minutes=settings.mp_idle_minutes)
    room_idle = now - timedelta(minutes=settings.mp_room_idle_minutes)
    rooms = db.scalars(select(Room).where(Room.status.in_(("playing", "waiting")))).all()
    for room in rooms:
        recent = [m for m in active_members(room) if as_utc(m.last_seen_at) >= idle]
        if room.status == "playing":
            match = current_match(db, room)
            if match is not None and not recent:
                # Ninguém por perto há mp_idle_minutes: partida abandonada.
                match.status = "abandoned"
                match.finished_at = now
                room.status = "closed"
                bump(room, now)
                db.commit()
                continue
            advance(db, settings, room, now)
        elif as_utc(room.updated_at) < room_idle and not [
                m for m in active_members(room) if as_utc(m.last_seen_at) >= room_idle]:
            room.status = "closed"
            bump(room, now)
            db.commit()
