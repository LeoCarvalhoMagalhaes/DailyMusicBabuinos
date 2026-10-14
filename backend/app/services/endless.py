"""Modo ilimitado: rodadas solo sem limite, com a mesma mecânica do desafio diário.

- Cada rodada é uma `GameSession` com `mode = "endless"`. Palpites, pulos, áudio e
  revelação usam exatamente as mesmas funções do modo diário.
- A música é sorteada no servidor (`secrets.SystemRandom`), entre as faixas da
  categoria com áudio, evitando as que o jogador ouviu recentemente nesse modo.
- Nunca sorteia uma música que seja desafio diário hoje (em qualquer categoria): o
  modo ilimitado não pode servir de atalho para descobrir a resposta do dia.
- Uma rodada em andamento precisa terminar (acerto, seis tentativas ou desistência)
  antes da próxima: pedir "próxima" devolve a mesma rodada, o que impede trocar de
  música até cair numa fácil.
- `run_id` agrupa as rodadas de uma sessão de jogo (placar da sessão). Estatísticas do
  modo são calculadas à parte e não mexem nas do desafio diário.
"""

from __future__ import annotations

import secrets
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audio.base import AudioProvider
from app.core.categories import CATEGORY_SLUGS
from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.models import MODE_ENDLESS, DailyChallenge, GameSession, MusicTrack, Player
from app.services.daily import candidates, first_playable, get_or_create_challenge
from app.services.game import new_session

_random = secrets.SystemRandom()


def todays_daily_track_ids(db: Session, settings: Settings, provider: AudioProvider,
                           today: date, now: datetime) -> set[int]:
    """Músicas que são desafio diário hoje. Publica os desafios do dia se ainda não
    existirem, para que nenhum outro modo possa sorteá-los antes."""
    for category in CATEGORY_SLUGS:
        get_or_create_challenge(db, settings, provider, category, today, now)
    return set(db.scalars(
        select(DailyChallenge.track_id).where(
            DailyChallenge.challenge_date == today,
            DailyChallenge.edition == settings.catalog_edition,
        )
    ))


def _recent_track_ids(db: Session, player_id: str, category: str, limit: int) -> list[int]:
    return list(db.scalars(
        select(GameSession.track_id)
        .where(GameSession.player_id == player_id, GameSession.mode == MODE_ENDLESS,
               GameSession.category == category)
        .order_by(GameSession.started_at.desc())
        .limit(limit)
    ))


def pick_track(db: Session, settings: Settings, provider: AudioProvider, category: str,
               avoid: set[int], recent: list[int]) -> MusicTrack:
    """Sorteia uma faixa com áudio da categoria. `avoid` nunca entra; `recent` (mais
    recente primeiro) só volta quando não sobra outra opção, a mais antiga antes."""
    pool = [t for t in candidates(db, category, settings.catalog_edition) if t.id not in avoid]
    if not pool:
        raise NotFoundError("Não há músicas disponíveis para esta categoria.",
                            code="empty_catalog")
    recent_set = set(recent)
    fresh = [t for t in pool if t.id not in recent_set]
    _random.shuffle(fresh)
    # Repetidas por último, da ouvida há mais tempo para a mais recente.
    position = {track_id: i for i, track_id in enumerate(recent)}
    repeats = sorted((t for t in pool if t.id in recent_set),
                     key=lambda t: position[t.id], reverse=True)
    track = first_playable(db, provider, fresh + repeats)
    if track is None:
        raise AppError("Nenhuma música com áudio disponível agora.", code="no_playable_track",
                       status_code=503)
    return track


def _valid_run(db: Session, player_id: str, run_id: str | None) -> str:
    """Reaproveita a sessão do jogador; um id inválido ou de outro jogador vira novo."""
    if run_id:
        try:
            uuid.UUID(run_id)
        except ValueError:
            return str(uuid.uuid4())
        owner = db.scalar(select(GameSession.player_id).where(GameSession.run_id == run_id)
                          .limit(1))
        if owner in (None, player_id):
            return run_id
    return str(uuid.uuid4())


def _open_rounds(db: Session, player_id: str, category: str) -> list[GameSession]:
    return list(db.scalars(
        select(GameSession)
        .where(GameSession.player_id == player_id, GameSession.mode == MODE_ENDLESS,
               GameSession.category == category, GameSession.status == "in_progress")
        .order_by(GameSession.started_at, GameSession.id)
    ))


def next_round(db: Session, settings: Settings, provider: AudioProvider, player: Player,
               category: str, run_id: str | None, today: date, now: datetime
               ) -> GameSession:
    current = _open_rounds(db, player.id, category)
    if current:
        return current[0]
    run = _valid_run(db, player.id, run_id)
    avoid = todays_daily_track_ids(db, settings, provider, today, now)
    pool_size = len(candidates(db, category, settings.catalog_edition))
    window = max(0, min(settings.endless_recent_window, pool_size - len(avoid) - 1))
    recent = _recent_track_ids(db, player.id, category, window)
    track = pick_track(db, settings, provider, category, avoid, recent)
    game = new_session(player.id, track.id, category, MODE_ENDLESS, now, run_id=run)
    db.add(game)
    db.commit()
    # Duas requisições simultâneas (duplo clique, duas abas) podem criar duas rodadas.
    # Fica só a mais antiga; a escolha é determinística, então as duas concordam.
    open_rounds = _open_rounds(db, player.id, category)
    for extra in open_rounds[1:]:
        if extra.attempts_used == 0:
            db.delete(extra)
    db.commit()
    return open_rounds[0]


@dataclass
class RunSummary:
    run_id: str
    rounds: int = 0
    wins: int = 0
    score: int = 0
    current_streak: int = 0
    best_streak: int = 0


@dataclass
class EndlessStats:
    category: str
    rounds: int = 0
    wins: int = 0
    total_score: int = 0
    current_streak: int = 0
    best_streak: int = 0
    distribution: list[int] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return round(self.wins / self.rounds, 4) if self.rounds else 0.0

    @property
    def average_score(self) -> float:
        return round(self.total_score / self.rounds, 1) if self.rounds else 0.0


def _streaks(results: list[bool]) -> tuple[int, int]:
    """(sequência atual de acertos, melhor sequência), com os resultados em ordem."""
    best = run = 0
    for won in results:
        run = run + 1 if won else 0
        best = max(best, run)
    return run, best


def run_summary(db: Session, player_id: str, run_id: str) -> RunSummary:
    rows = db.execute(
        select(GameSession.status, GameSession.score)
        .where(GameSession.player_id == player_id, GameSession.run_id == run_id,
               GameSession.mode == MODE_ENDLESS, GameSession.status != "in_progress")
        .order_by(GameSession.finished_at)
    ).all()
    results = [r.status == "won" for r in rows]
    current, best = _streaks(results)
    return RunSummary(run_id=run_id, rounds=len(rows), wins=sum(results),
                      score=sum(r.score for r in rows), current_streak=current,
                      best_streak=best)


def endless_stats(db: Session, settings: Settings, player_id: str) -> list[EndlessStats]:
    """Estatísticas do modo ilimitado: geral ("all") e por categoria."""
    rows = db.execute(
        select(GameSession.category, GameSession.status, GameSession.score,
               GameSession.attempts_used)
        .where(GameSession.player_id == player_id, GameSession.mode == MODE_ENDLESS,
               GameSession.status != "in_progress")
        .order_by(GameSession.finished_at)
    ).all()
    slots = settings.max_attempts + 1
    stats = {key: EndlessStats(key, distribution=[0] * slots)
             for key in ("all", *CATEGORY_SLUGS)}
    results: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        won = row.status == "won"
        for key in ("all", row.category):
            item = stats[key]
            item.rounds += 1
            item.wins += won
            item.total_score += row.score
            index = min(row.attempts_used, settings.max_attempts) - 1 if won else -1
            item.distribution[index] += 1
            results[key].append(won)
    for key, item in stats.items():
        item.current_streak, item.best_streak = _streaks(results[key])
    return list(stats.values())
