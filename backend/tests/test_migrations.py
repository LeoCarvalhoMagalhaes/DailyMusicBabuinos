"""Migração 0003 (modos de jogo) sobre um banco com partidas diárias já gravadas."""

from __future__ import annotations

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from alembic import command
from app.database.migrate import alembic_config
from app.database.session import Base
from tests.conftest import database_url


def test_upgrade_keeps_existing_daily_games(tmp_path: Path) -> None:
    url = database_url(tmp_path, "migracao.db")
    config = alembic_config(url)
    command.upgrade(config, "0002")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO players (id, token_hash, created_at, last_seen_at) "
            "VALUES ('p1', 'h1', '2026-10-14 12:00:00', '2026-10-14 12:00:00')"))
        conn.execute(text(
            "INSERT INTO music_tracks (id, slug, edition, title, artist, primary_category, "
            "extra_genres, aliases, license_note, availability) VALUES (7, 'queen--x', 'main', "
            "'X', 'Queen', 'rock', '[]', '[]', '', 'available')"))
        conn.execute(text(
            "INSERT INTO daily_challenges (id, challenge_date, category, edition, track_id, "
            "status, created_at) VALUES (3, '2026-10-14', 'rock', 'main', 7, 'published', "
            "'2026-10-14 12:00:00')"))
        conn.execute(text(
            "INSERT INTO game_sessions (id, challenge_id, player_id, attempts_used, score, "
            "status, started_at) VALUES ('g1', 3, 'p1', 2, 80, 'won', '2026-10-14 12:00:00')"))

    command.upgrade(config, "head")

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT mode, category, track_id, challenge_id, speed_bonus, run_id, "
            "match_round_id FROM game_sessions WHERE id = 'g1'")).one()
        assert tuple(row) == ("daily", "rock", 7, 3, 0, None, None)
        # O esquema migrado é exatamente o dos modelos.
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    engine.dispose()

    command.downgrade(config, "0002")
    command.upgrade(config, "head")
