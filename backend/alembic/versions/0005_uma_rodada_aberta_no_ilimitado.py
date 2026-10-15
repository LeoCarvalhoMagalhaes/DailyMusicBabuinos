"""uma rodada aberta por categoria no modo ilimitado

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-15 00:30:00

Índice único parcial: no máximo uma rodada em andamento do modo ilimitado por jogador e
categoria. Antes, duas requisições simultâneas podiam abrir duas. Rodadas abertas
duplicadas que já existam (sem nenhuma tentativa) são removidas, ficando a mais antiga.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPEN = "mode = 'endless' AND status = 'in_progress'"


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        f"SELECT id, player_id, category, attempts_used FROM game_sessions WHERE {OPEN} "
        "ORDER BY player_id, category, started_at, id")).all()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.player_id, row.category)
        if key in seen:
            # Duplicada: sem tentativas, é apagada; com tentativas, é encerrada.
            if row.attempts_used == 0:
                bind.execute(sa.text("DELETE FROM game_sessions WHERE id = :id"), {"id": row.id})
            else:
                bind.execute(sa.text("UPDATE game_sessions SET status = 'lost' WHERE id = :id"),
                             {"id": row.id})
        seen.add(key)
    op.create_index("uq_endless_open_round", "game_sessions", ["player_id", "category"],
                    unique=True, sqlite_where=sa.text(OPEN), postgresql_where=sa.text(OPEN))


def downgrade() -> None:
    op.drop_index("uq_endless_open_round", table_name="game_sessions")
