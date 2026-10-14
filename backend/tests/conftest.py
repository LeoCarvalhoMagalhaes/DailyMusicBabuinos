from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text

from app.audio.base import AudioClip, AudioProvider
from app.audio.wav import encode_wav
from app.core.clock import FrozenClock
from app.core.config import Settings
from app.core.errors import AudioUnavailableError
from app.main import create_app
from app.models import DailyChallenge, MusicTrack

TEST_SECRET = "segredo-de-teste-com-mais-de-32-caracteres!!"
# 15/10/2026 12:00 em São Paulo (UTC-3)
NOON_SP = datetime(2026, 10, 15, 15, 0, tzinfo=UTC)


class FakeProvider(AudioProvider):
    """Provedor controlável para testar o catálogo principal sem rede."""

    name = "fake"
    max_seconds = 30.0
    attribution = "Fake"

    def __init__(self) -> None:
        self.unavailable: set[str] = set()
        self.fail_checks = False
        self.fail_clips = False
        self.clip_requests: list[float] = []

    def check_availability(self, track: MusicTrack) -> bool:
        if self.fail_checks:
            raise AudioUnavailableError("fora do ar")
        ok = track.slug not in self.unavailable
        track.availability = "available" if ok else "unavailable"
        return ok

    def get_clip(self, track: MusicTrack, seconds: float, category: str | None = None
                 ) -> AudioClip:
        if self.fail_clips:
            raise AudioUnavailableError("O serviço de áudio não respondeu.")
        self.clip_requests.append(seconds)
        samples = np.zeros(int(8000 * seconds), dtype=np.int16)
        return AudioClip(encode_wav(samples, 8000), "audio/wav", seconds)


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "app_env": "test",
        "database_url": f"sqlite:///{tmp_path / 'test.db'}",
        "challenge_secret": TEST_SECRET,
        "audio_provider": "demo",
        "rate_limit_enabled": False,
        "cors_origins": ["http://localhost:5173"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class Harness:
    def __init__(self, client: TestClient, clock: FrozenClock, settings: Settings) -> None:
        self.client = client
        self.clock = clock
        self.settings = settings

    @property
    def app(self):
        return self.client.app

    def new_player(self) -> dict[str, str]:
        response = self.client.post("/api/players")
        assert response.status_code == 201, response.text
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def start(self, headers: dict[str, str], category: str = "rock") -> dict:
        response = self.client.post("/api/games/start", json={"category": category},
                                    headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    def guess(self, headers: dict[str, str], game: dict, text: str, attempt: int | None = None):
        attempt = attempt if attempt is not None else game["attempts_used"] + 1
        return self.client.post(f"/api/games/{game['id']}/guess",
                                json={"guess": text, "attempt": attempt}, headers=headers)

    def secret(self, category: str = "rock") -> MusicTrack:
        with self.app.state.session_factory() as db:
            ch = db.query(DailyChallenge).filter_by(
                challenge_date=self.clock.today(), category=category,
                edition=self.settings.catalog_edition,
            ).one()
            return db.get(MusicTrack, ch.track_id)

    def wrong_titles(self, category: str = "rock", count: int = 6) -> list[str]:
        secret = self.secret(category)
        with self.app.state.session_factory() as db:
            titles = [t.title for t in db.query(MusicTrack).filter_by(
                edition=self.settings.catalog_edition).order_by(MusicTrack.slug)]
        result = [t for t in titles if t.casefold() != secret.title.casefold()]
        return result[:count]


HarnessFactory = Callable[..., Harness]

# Defina TEST_DATABASE_URL=postgresql://... para rodar a suíte contra PostgreSQL.
PG_TEST_URL = os.environ.get("TEST_DATABASE_URL")


def database_url(tmp_path: Path, db_name: str) -> str:
    if not PG_TEST_URL:
        return f"sqlite:///{tmp_path / db_name}"
    base = make_url(Settings(_env_file=None, database_url=PG_TEST_URL).database_url)
    stem = Path(db_name).stem
    name = base.database if stem == "test" else f"{base.database}_{stem}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name})
        if exists.scalar() is None:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    url = base.set(database=name)
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    return url.render_as_string(hide_password=False)


@pytest.fixture
def harness_factory(tmp_path: Path) -> Iterator[HarnessFactory]:
    clients: list[TestClient] = []

    def factory(*, provider: AudioProvider | None = None, now: datetime = NOON_SP,
                db_name: str = "test.db", **overrides) -> Harness:
        overrides.setdefault("database_url", database_url(tmp_path, db_name))
        settings = make_settings(tmp_path, **overrides)
        clock = FrozenClock(settings.tz, now)
        app = create_app(settings, clock=clock)
        if provider is not None:
            app.state.audio_provider = provider
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return Harness(client, clock, settings)

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def harness(harness_factory: HarnessFactory) -> Harness:
    return harness_factory()


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def main_harness(harness_factory: HarnessFactory, fake_provider: FakeProvider) -> Harness:
    """Catálogo principal (edição 'main') com provedor falso controlável."""
    return harness_factory(provider=fake_provider, audio_provider="deezer")
