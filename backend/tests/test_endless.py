"""Modo ilimitado: rodadas solo sem limite, sem repetir e sem mexer no desafio diário."""

from __future__ import annotations

import json

from app.models import GameSession, MusicTrack
from tests.conftest import Harness


def next_round(h: Harness, headers: dict, category: str = "rock", run_id: str | None = None):
    response = h.client.post("/api/endless/next", json={"category": category, "run_id": run_id},
                             headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def track_of(h: Harness, game_id: str) -> MusicTrack:
    with h.app.state.session_factory() as db:
        game = db.get(GameSession, game_id)
        db.expunge(game.track)
        return game.track


def give_up(h: Harness, headers: dict, game: dict) -> dict:
    for attempt in range(game["attempts_used"] + 1, game["max_attempts"] + 1):
        r = h.client.post(f"/api/games/{game['id']}/skip", json={"attempt": attempt},
                          headers=headers)
        assert r.status_code == 200, r.text
        game = r.json()
    return game


def test_round_hides_answer_and_cannot_be_rerolled(main_harness: Harness) -> None:
    h = main_harness
    headers = h.new_player()
    first = next_round(h, headers)
    game = first["game"]
    assert game["mode"] == "endless" and game["status"] == "in_progress"
    assert game["date"] is None and game["challenge_number"] is None
    assert game["answer"] is None
    track = track_of(h, game["id"])
    assert track.title not in json.dumps(first)
    # Pedir a próxima sem terminar devolve a mesma rodada (não dá para trocar a música).
    again = next_round(h, headers, run_id=first["run"]["run_id"])
    assert again["game"]["id"] == game["id"]


def test_rounds_use_the_daily_mechanics_and_score_the_session(main_harness: Harness) -> None:
    h = main_harness
    headers = h.new_player()
    first = next_round(h, headers)
    run_id = first["run"]["run_id"]
    game = first["game"]
    # Mesmas rotas, regras e pontuação do diário: erro, pulo e acerto na 3ª = 60 pontos.
    audio = h.client.get(f"/api/games/{game['id']}/audio?stage=2", headers=headers)
    assert audio.status_code == 403
    wrong = h.client.post(f"/api/games/{game['id']}/guess",
                          json={"guess": "Música Que Não Existe", "attempt": 1}, headers=headers)
    assert wrong.json()["correct"] is False
    h.client.post(f"/api/games/{game['id']}/skip", json={"attempt": 2}, headers=headers)
    track = track_of(h, game["id"])
    won = h.client.post(f"/api/games/{game['id']}/guess",
                        json={"guess": track.title, "attempt": 3}, headers=headers).json()
    assert won["correct"] is True
    assert won["game"]["score"] == 60 and won["game"]["answer"]["title"] == track.title

    second = next_round(h, headers, run_id=run_id)
    assert second["game"]["id"] != game["id"]
    assert second["run"] == {"run_id": run_id, "rounds": 1, "wins": 1, "score": 60,
                             "current_streak": 1, "best_streak": 1}
    give_up(h, headers, second["game"])
    summary = h.client.get(f"/api/endless/runs/{run_id}", headers=headers).json()
    assert (summary["rounds"], summary["wins"], summary["current_streak"],
            summary["best_streak"]) == (2, 1, 0, 1)


def test_no_repeats_and_never_todays_daily_song(main_harness: Harness) -> None:
    h = main_harness
    headers = h.new_player()
    seen: list[int] = []
    run_id = None
    for _ in range(25):
        data = next_round(h, headers, "pop", run_id)
        run_id = data["run"]["run_id"]
        seen.append(track_of(h, data["game"]["id"]).id)
        give_up(h, headers, data["game"])
    assert len(set(seen)) == len(seen)
    # Os desafios do dia já existem (o modo ilimitado os publica antes de sortear) e
    # nenhuma de suas músicas apareceu.
    daily_ids = {h.secret(category).id for category in
                 ("rock", "pop", "rap", "country", "eletronica", "geral")}
    assert not daily_ids & set(seen)


def test_endless_does_not_touch_daily_games_or_stats(main_harness: Harness) -> None:
    h = main_harness
    headers = h.new_player()
    data = next_round(h, headers, "rock")
    give_up(h, headers, data["game"])
    daily = h.client.get("/api/daily", headers=headers).json()
    assert all(c["status"] == "not_started" for c in daily["categories"])
    stats = h.client.get("/api/statistics", headers=headers).json()
    assert stats["overall"]["games_played"] == 0
    assert h.client.get("/api/history", headers=headers).json()["total"] == 0
    # E o desafio diário continua jogável normalmente, com a música do dia.
    game = h.start(headers, "rock")
    assert game["mode"] == "daily" and game["attempts_used"] == 0


def test_endless_stats_per_category(main_harness: Harness) -> None:
    h = main_harness
    headers = h.new_player()
    run_id = None
    for category, win in (("rock", True), ("rock", True), ("rap", False)):
        data = next_round(h, headers, category, run_id)
        run_id = data["run"]["run_id"]
        if win:
            title = track_of(h, data["game"]["id"]).title
            h.client.post(f"/api/games/{data['game']['id']}/guess",
                          json={"guess": title, "attempt": 1}, headers=headers)
        else:
            give_up(h, headers, data["game"])
    stats = h.client.get("/api/endless/stats", headers=headers).json()
    assert stats["overall"]["rounds"] == 3 and stats["overall"]["wins"] == 2
    rock = next(c for c in stats["categories"] if c["category"] == "rock")
    assert (rock["rounds"], rock["wins"], rock["total_score"], rock["current_streak"],
            rock["best_streak"]) == (2, 2, 200, 2, 2)
    assert rock["distribution"][0] == 2
    rap = next(c for c in stats["categories"] if c["category"] == "rap")
    assert rap["distribution"][-1] == 1 and rap["win_rate"] == 0.0


def test_other_players_cannot_touch_my_rounds_or_runs(main_harness: Harness) -> None:
    h = main_harness
    mine, other = h.new_player(), h.new_player()
    data = next_round(h, mine)
    game_id, run_id = data["game"]["id"], data["run"]["run_id"]
    assert h.client.get(f"/api/games/{game_id}", headers=other).status_code == 404
    assert h.client.post(f"/api/games/{game_id}/skip", json={"attempt": 1},
                         headers=other).status_code == 404
    # O id de sessão de outro jogador não é reaproveitado.
    theirs = next_round(h, other, run_id=run_id)
    assert theirs["run"]["run_id"] != run_id


def test_small_catalog_repeats_oldest_song_when_exhausted(harness: Harness) -> None:
    # Modo demonstração: poucas melodias por categoria; o modo continua sem fim.
    headers = harness.new_player()
    run_id = None
    for _ in range(40):
        data = next_round(harness, headers, "geral", run_id)
        run_id = data["run"]["run_id"]
        give_up(harness, headers, data["game"])
    stats = harness.client.get("/api/endless/stats", headers=headers).json()
    assert stats["overall"]["rounds"] == 40


def test_simultaneous_requests_keep_a_single_open_round(main_harness: Harness) -> None:
    from datetime import timedelta

    from app.models import Player
    from app.services import endless

    h = main_harness
    headers = h.new_player()
    first = next_round(h, headers)
    with h.app.state.session_factory() as db:
        game = db.get(GameSession, first["game"]["id"])
        # Simula a corrida: outra requisição gravou uma segunda rodada aberta.
        twin = GameSession(id="00000000-0000-4000-8000-000000000001", mode="endless",
                           category="rock", track_id=game.track_id + 1, run_id="outra",
                           player_id=game.player_id, attempts_used=0, score=0, speed_bonus=0,
                           status="in_progress", started_at=game.started_at + timedelta(seconds=1))
        db.add(twin)
        db.commit()
        # Ao terminar a primeira, a próxima chamada encontra a gêmea e a usa.
        player = db.get(Player, game.player_id)
        kept = endless.next_round(db, h.settings, h.app.state.audio_provider, player, "rock",
                                  None, h.clock.today(), h.clock.now())
        assert kept.id == game.id  # a mais antiga vence
