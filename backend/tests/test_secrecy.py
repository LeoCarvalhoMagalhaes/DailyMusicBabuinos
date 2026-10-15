"""A música secreta não pode vazar antes do fim da partida."""

from __future__ import annotations

from app.audio.wav import decode_wav
from tests.conftest import Harness


def _assert_hidden(text: str, title: str, artist: str) -> None:
    lowered = text.casefold()
    assert title.casefold() not in lowered
    assert artist.casefold() not in lowered


def test_no_endpoint_leaks_the_answer_during_the_game(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers, "country")
    secret = harness.secret("country")
    wrong = harness.wrong_titles("country")
    responses = [
        harness.client.get("/api/daily", headers=headers),
        harness.client.get("/api/daily/country", headers=headers),
        harness.client.post("/api/games/start", json={"category": "country"}, headers=headers),
        harness.client.get(f"/api/games/{game['id']}", headers=headers),
        harness.guess(headers, game, wrong[0]),
        harness.client.get("/api/history", headers=headers),
        harness.client.get("/api/statistics", headers=headers),
    ]
    for response in responses:
        assert response.status_code == 200, response.text
        _assert_hidden(response.text, secret.title, secret.artist)
        for value in response.headers.values():
            _assert_hidden(value, secret.title, secret.artist)


def test_result_endpoint_requires_finished_game(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    response = harness.client.get(f"/api/games/{game['id']}/result", headers=headers)
    assert response.status_code == 409
    harness.guess(headers, game, harness.secret().title)
    result = harness.client.get(f"/api/games/{game['id']}/result", headers=headers).json()
    assert result["answer"]["title"] == harness.secret().title


def test_audio_respects_unlocked_stage(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    url = f"/api/games/{game['id']}/audio"
    ok = harness.client.get(f"{url}?stage=1", headers=headers)
    assert ok.status_code == 200
    assert float(ok.headers["X-Clip-Duration"]) == 0.5
    assert ok.headers["Cache-Control"] == "no-store"
    for stage in (2, 6):
        locked = harness.client.get(f"{url}?stage={stage}", headers=headers)
        assert locked.status_code == 403
        assert locked.json()["error"]["code"] == "stage_locked"
    assert harness.client.get(f"{url}?stage=7", headers=headers).status_code == 404
    harness.client.post(f"/api/games/{game['id']}/skip", json={"attempt": 1}, headers=headers)
    stage2 = harness.client.get(f"{url}?stage=2", headers=headers)
    assert stage2.status_code == 200
    assert float(stage2.headers["X-Clip-Duration"]) == 1.0


def test_audio_payload_has_no_metadata(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    secret = harness.secret()
    audio = harness.client.get(f"/api/games/{game['id']}/audio?stage=1", headers=headers)
    assert "content-disposition" not in {k.lower() for k in audio.headers}
    data = audio.content
    assert b"LIST" not in data and b"ID3" not in data
    assert secret.title.encode() not in data
    samples, rate, channels = decode_wav(data)
    assert channels == 1 and len(samples) == rate // 2  # 0,5 s


def test_finished_game_unlocks_every_stage(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    harness.guess(headers, game, harness.secret().title)
    response = harness.client.get(f"/api/games/{game['id']}/audio?stage=6", headers=headers)
    assert response.status_code == 200
    assert float(response.headers["X-Clip-Duration"]) == 16.0


def test_search_does_not_depend_on_the_answer(harness: Harness) -> None:
    headers = harness.new_player()
    before = harness.client.get("/api/songs/search?q=a", headers=headers).json()
    harness.start(headers, "rock")
    harness.start(headers, "pop")
    after = harness.client.get("/api/songs/search?q=a", headers=headers).json()
    assert before == after
    # A busca cobre o catálogo de todas as categorias, não só a do desafio.
    titles = {s["title"] for s in harness.client.get("/api/songs/search?q=jingle").json()}
    assert "Jingle Bells" in titles


def test_secret_tables_are_not_exposed_by_any_route(harness: Harness) -> None:
    paths = set(harness.client.get("/api/openapi.json").json()["paths"])
    assert "/api/games/{game_id}/guess" in paths
    assert not any("track" in p or "challenge" in p or "reveal" in p for p in paths)
