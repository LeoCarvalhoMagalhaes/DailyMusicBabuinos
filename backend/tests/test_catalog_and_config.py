from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import DEV_SECRET, Settings
from app.models import CatalogEntry, MusicTrack
from app.services.catalog import (
    CatalogFormatError,
    catalog_index,
    load_catalog_files,
    sync_catalog,
)
from tests.conftest import Harness


def test_main_catalog_has_100_tracks_per_category() -> None:
    bundle = load_catalog_files()
    counts: dict[str, int] = {}
    for spec in bundle.tracks.values():
        if spec.edition == "main":
            for category in spec.categories:
                counts[category] = counts.get(category, 0) + 1
    assert counts == {c: 100 for c in ("rock", "pop", "rap", "country", "eletronica", "geral")}


def test_editorial_sources_never_claim_rank_positions() -> None:
    bundle = load_catalog_files()
    for spec in bundle.tracks.values():
        for category, rank in spec.categories.items():
            source = bundle.sources[spec.source_by_category[category]]
            if source["kind"] == "editorial":
                assert rank is None
    for source in bundle.sources.values():
        assert source["methodology"] and source["retrieved_on"]


def test_demo_tracks_reference_existing_melodies() -> None:
    from app.audio.synth import load_songs

    songs = load_songs()
    demo = [s for s in load_catalog_files().tracks.values() if s.edition == "demo"]
    assert len(demo) >= 25
    assert all(s.audio_ref in songs for s in demo)
    assert all(s.license_note for s in demo)


def _write(dir_: Path, name: str, payload: dict) -> None:
    (dir_ / name).write_text(json.dumps(payload), encoding="utf-8")


def test_rank_requires_chart_source(tmp_path: Path) -> None:
    _write(tmp_path, "rock.json", {
        "edition": "main", "category": "rock",
        "source": {"id": "x", "kind": "editorial", "name": "x"},
        "tracks": [{"title": "A", "artist": "B", "rank": 1}],
    })
    with pytest.raises(CatalogFormatError):
        load_catalog_files((tmp_path,))


def test_sync_is_idempotent_and_deactivates_removed(harness: Harness, tmp_path: Path) -> None:
    _write(tmp_path, "rock.json", {
        "edition": "main", "category": "rock",
        "source": {"id": "chart-x", "kind": "chart", "name": "Parada X",
                   "url": "https://example.com", "retrieved_on": "2026-10-01"},
        "tracks": [{"title": "Canção A", "artist": "Banda", "rank": 1},
                   {"title": "Canção B", "artist": "Banda", "rank": 2}],
    })
    with harness.app.state.session_factory() as db:
        first = sync_catalog(db, load_catalog_files((tmp_path,)))
        again = sync_catalog(db, load_catalog_files((tmp_path,)))
        assert first["created"] == 2 and again["created"] == 0
        _write(tmp_path, "rock.json", {
            "edition": "main", "category": "rock",
            "source": {"id": "chart-x", "kind": "chart", "name": "Parada X"},
            "tracks": [{"title": "Canção A", "artist": "Banda", "rank": 1}],
        })
        third = sync_catalog(db, load_catalog_files((tmp_path,)))
        assert third["deactivated"] == 1
        removed = db.scalar(select(MusicTrack).where(MusicTrack.slug == "banda--cancao-b"))
        entry = db.scalar(select(CatalogEntry).where(CatalogEntry.track_id == removed.id))
        assert entry.active is False and entry.reference_rank == 2
    catalog_index.invalidate()


def test_search_suggestions(harness: Harness) -> None:
    results = harness.client.get("/api/songs/search?q=ODE A ALEGRIA").json()
    assert results[0]["title"] == "Ode à Alegria"
    assert harness.client.get("/api/songs/search?q=beethoven").json()  # busca por artista
    assert harness.client.get("/api/songs/search?q=zzzzzz").json() == []
    assert harness.client.get("/api/songs/search?q=").status_code == 422
    assert len(harness.client.get("/api/songs/search?q=e").json()) <= 8


def test_settings_validation() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, clip_stages_seconds="1,2", score_table="100")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, clip_stages_seconds="2,1", score_table="100,50")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", challenge_secret=DEV_SECRET)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", challenge_secret="curto")
    s = Settings(_env_file=None, database_url="postgres://u:p@host:5432/db",
                 cors_origins="https://a.com, https://b.com")
    assert s.database_url == "postgresql+psycopg://u:p@host:5432/db"
    assert s.cors_origins == ["https://a.com", "https://b.com"]
    assert s.audio_provider == "deezer" and s.catalog_edition == "main"  # gravações reais
    assert Settings(_env_file=None, audio_provider="demo").catalog_edition == "demo"


def test_health_and_security_headers(harness: Harness) -> None:
    response = harness.client.get("/api/health")
    assert response.json()["status"] == "ok"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"


def test_cors_allows_only_configured_origins(harness: Harness) -> None:
    ok = harness.client.options("/api/daily", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = harness.client.options("/api/daily", headers={
        "Origin": "https://malicioso.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_unknown_route_returns_json_error(harness: Harness) -> None:
    response = harness.client.get("/api/nada")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
