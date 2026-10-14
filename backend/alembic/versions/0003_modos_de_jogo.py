"""modos de jogo: ilimitado e multiplayer

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14 20:00:00

- game_sessions passa a servir os três modos: `mode`, `category` e `track_id` em toda
  partida; `challenge_id` só no diário; `run_id` no ilimitado; `match_round_id`,
  `speed_bonus` e `response_ms` no multiplayer. As partidas diárias existentes são
  preenchidas a partir do desafio de cada uma.
- Tabelas novas do multiplayer: contas, sessões de login, salas, membros, partidas e
  rodadas.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=24), nullable=False),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column("player_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_username", "accounts", ["username"], unique=True)

    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_auth_sessions_account_id", "auth_sessions", ["account_id"])

    op.create_table(
        "rooms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("host_account_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("category_order", sa.JSON(), nullable=False),
        sa.Column("current_match_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["host_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rooms_code", "rooms", ["code"], unique=True)

    op.create_table(
        "room_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("ready", sa.Boolean(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id", "account_id", name="uq_member_room_account"),
    )
    op.create_index("ix_room_members_room_id", "room_members", ["room_id"])

    op.create_table(
        "matches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("current_round", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(length=10), nullable=False),
        sa.Column("phase_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("phase_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("participant_ids", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_matches_room_id", "matches", ["room_id"])

    op.create_table(
        "match_rounds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["music_tracks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "number", name="uq_round_number"),
    )
    op.create_index("ix_match_rounds_match_id", "match_rounds", ["match_id"])

    with op.batch_alter_table("game_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mode", sa.String(length=10), nullable=False,
                                      server_default="daily"))
        batch_op.add_column(sa.Column("category", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("track_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("run_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("match_round_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("speed_bonus", sa.Integer(), nullable=False,
                                      server_default="0"))
        batch_op.add_column(sa.Column("response_ms", sa.Integer(), nullable=True))
        batch_op.alter_column("challenge_id", existing_type=sa.Integer(), nullable=True)

    # Partidas diárias já gravadas: categoria e música vêm do desafio.
    op.execute(
        "UPDATE game_sessions SET "
        "category = (SELECT category FROM daily_challenges d WHERE d.id = game_sessions.challenge_id), "
        "track_id = (SELECT track_id FROM daily_challenges d WHERE d.id = game_sessions.challenge_id)"
    )

    with op.batch_alter_table("game_sessions", schema=None) as batch_op:
        batch_op.alter_column("category", existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column("track_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key("fk_game_sessions_track_id", "music_tracks", ["track_id"],
                                    ["id"])
        batch_op.create_foreign_key("fk_game_sessions_match_round_id", "match_rounds",
                                    ["match_round_id"], ["id"], ondelete="CASCADE")
        batch_op.create_unique_constraint("uq_game_player_round",
                                          ["player_id", "match_round_id"])
        batch_op.create_index("ix_game_sessions_track_id", ["track_id"])
        batch_op.create_index("ix_game_sessions_run_id", ["run_id"])
        batch_op.create_index("ix_game_sessions_match_round_id", ["match_round_id"])
        batch_op.create_index("ix_game_player_mode_category", ["player_id", "mode", "category"])


def downgrade() -> None:
    op.execute("DELETE FROM game_sessions WHERE mode <> 'daily'")
    with op.batch_alter_table("game_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_game_player_mode_category")
        batch_op.drop_index("ix_game_sessions_match_round_id")
        batch_op.drop_index("ix_game_sessions_run_id")
        batch_op.drop_index("ix_game_sessions_track_id")
        batch_op.drop_constraint("uq_game_player_round", type_="unique")
        batch_op.drop_constraint("fk_game_sessions_match_round_id", type_="foreignkey")
        batch_op.drop_constraint("fk_game_sessions_track_id", type_="foreignkey")
        batch_op.alter_column("challenge_id", existing_type=sa.Integer(), nullable=False)
        for column in ("response_ms", "speed_bonus", "match_round_id", "run_id", "track_id",
                       "category", "mode"):
            batch_op.drop_column(column)
    for table in ("match_rounds", "matches", "room_members", "rooms", "auth_sessions",
                  "accounts"):
        op.drop_table(table)
