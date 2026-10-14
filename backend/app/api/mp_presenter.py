"""Estado da sala multiplayer, montado para um jogador específico.

O que cada um vê:
- Do próprio andamento: tentativas, palpites, trecho liberado e pontos.
- Dos outros: só quantas tentativas usaram e se acertaram (nunca o texto digitado,
  que entregaria a resposta).
- A resposta da rodada só aparece na fase de revelação ou com a partida encerrada,
  mesmo para quem já terminou a rodada antes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.presenters import category_out, game_state, rules_out
from app.audio.base import AudioProvider
from app.core.clock import Clock
from app.core.config import Settings
from app.models import Account, GameSession, Room
from app.schemas import (
    AnswerOut,
    CategoryScoreOut,
    MatchOut,
    PlayerProgressOut,
    RoomMemberOut,
    RoomStateOut,
    RoundOut,
    RoundResultOut,
    ScoreLineOut,
)
from app.services import multiplayer as mp
from app.services.game import reveal_track


def _answer(track, provider: AudioProvider) -> AnswerOut:
    revealed = reveal_track(track, provider)
    return AnswerOut(title=revealed.title, artist=revealed.artist, cover_url=revealed.cover_url,
                     external_url=revealed.external_url, spotify_url=revealed.spotify_url,
                     attribution=revealed.attribution)


def _start_blocker(settings: Settings, room: Room, account: Account) -> str | None:
    if room.status != "waiting":
        return "A partida já está em andamento."
    if account.id != room.host_account_id:
        return "Só o anfitrião pode iniciar a partida."
    players = mp.active_members(room)
    if len(players) < settings.mp_min_players:
        return f"Aguardando jogadores: mínimo de {settings.mp_min_players}."
    if any(not m.ready for m in players if m.account_id != room.host_account_id):
        return "Aguardando todos ficarem prontos."
    return None


def _match_out(db: Session, settings: Settings, provider: AudioProvider, clock: Clock,
               room: Room, account: Account) -> MatchOut | None:
    match = mp.current_match(db, room)
    if match is None:
        return None
    rnd = next(r for r in match.rounds if r.number == match.current_round)
    revealed_now = match.phase == "reveal" or match.status != "playing"
    names = {m.account_id: m.account.display_name for m in room.members}
    accounts = {a.player_id: a for a in db.scalars(
        select(Account).where(Account.id.in_(match.participant_ids)))}

    sessions = list(db.scalars(select(GameSession).where(GameSession.match_round_id == rnd.id)))
    my_game = next((s for s in sessions if s.player_id == account.player_id), None)
    my_state = game_state(my_game, settings, provider, clock) if my_game else None
    if my_state is not None and not revealed_now:
        my_state.answer = None  # a resposta só aparece para todos ao mesmo tempo
    progress = [
        PlayerProgressOut(account_id=accounts[s.player_id].id,
                          display_name=names.get(accounts[s.player_id].id,
                                                 accounts[s.player_id].display_name),
                          attempts_used=s.attempts_used, status=s.status,  # type: ignore[arg-type]
                          score=s.score)
        for s in sessions if s.player_id in accounts
    ]

    # Rodadas já encerradas (com resposta) e o resultado do jogador em cada uma.
    last_closed = match.current_round if revealed_now else match.current_round - 1
    closed = [r for r in match.rounds if r.number <= last_closed]
    mine = {s.match_round_id: s for s in db.scalars(
        select(GameSession).where(GameSession.player_id == account.player_id,
                                  GameSession.match_round_id.in_([r.id for r in closed])))}
    history = [
        RoundResultOut(number=r.number, category=category_out(r.category),
                       answer=_answer(r.track, provider),
                       my_status=mine[r.id].status if r.id in mine else None,  # type: ignore[arg-type]
                       my_score=mine[r.id].score if r.id in mine else 0)
        for r in closed
    ]

    board = mp.scoreboard(db, room, match)
    lines = [
        ScoreLineOut(position=s.position, account_id=s.account_id, display_name=s.display_name,
                     total_score=s.total_score, correct=s.correct,
                     average_response_ms=s.average_response_ms, left=s.left,
                     per_category=[CategoryScoreOut(category=c, score=v["score"],  # type: ignore[arg-type]
                                                    correct=v["correct"])
                                   for c, v in s.per_category.items()])
        for s in board
    ]
    top = board[0].total_score if board else 0
    winners = ([s.account_id for s in board if s.total_score == top]
               if match.status == "finished" and board else [])
    return MatchOut(
        id=match.id, status=match.status, phase=match.phase,  # type: ignore[arg-type]
        current_round=match.current_round, total_rounds=len(match.rounds),
        phase_ends_at=match.phase_ends_at,
        round=RoundOut(number=rnd.number, category=category_out(rnd.category),
                       index_in_category=(rnd.number - 1) % mp.ROUNDS_PER_CATEGORY + 1,
                       songs_per_category=mp.ROUNDS_PER_CATEGORY, started_at=rnd.started_at,
                       ends_at=rnd.ends_at),
        my_game=my_state, progress=progress,
        answer=_answer(rnd.track, provider) if revealed_now else None,
        scoreboard=lines, history=history, winner_ids=winners,
    )


def room_state(db: Session, settings: Settings, provider: AudioProvider, clock: Clock,
               room: Room, account: Account, connected: set[str],
               now: datetime | None = None) -> RoomStateOut:
    return RoomStateOut(
        id=room.id, code=room.code, status=room.status,  # type: ignore[arg-type]
        version=room.version, me=account.id, host_account_id=room.host_account_id,
        category_order=room.category_order,  # type: ignore[arg-type]
        members=[
            RoomMemberOut(account_id=m.account_id, display_name=m.account.display_name,
                          is_host=m.account_id == room.host_account_id, ready=m.ready,
                          connected=m.account_id in connected, left=not m.active)
            for m in room.members
        ],
        min_players=settings.mp_min_players, max_players=settings.mp_max_players,
        can_start=_start_blocker(settings, room, account) is None,
        start_blocker=_start_blocker(settings, room, account),
        round_seconds=settings.mp_round_seconds, reveal_seconds=settings.mp_reveal_seconds,
        speed_bonus_max=settings.mp_speed_bonus_max, rules=rules_out(settings),
        server_time=now or clock.now(),
        match=_match_out(db, settings, provider, clock, room, account),
    )
