"""palpite do mesmo artista

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14 21:00:00

Marca os palpites errados de uma música do mesmo artista da resposta (exibidos em
amarelo, como "quase"). Palpites antigos ficam como falso.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("game_guesses", schema=None) as batch_op:
        batch_op.add_column(sa.Column("same_artist", sa.Boolean(), nullable=False,
                                      server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("game_guesses", schema=None) as batch_op:
        batch_op.drop_column("same_artist")
