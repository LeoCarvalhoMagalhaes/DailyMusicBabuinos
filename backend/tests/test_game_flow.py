from __future__ import annotations

from tests.conftest import Harness


def test_start_is_idempotent(harness: Harness) -> None:
    headers = harness.new_player()
    first = harness.start(headers)
    second = harness.start(headers)
    assert first["id"] == second["id"]
    assert first["status"] == "in_progress"
    assert first["attempts_used"] == 0
    assert first["unlocked_stage"] == 1
    assert first["remaining_attempts"] == 6
    assert first["answer"] is None


def test_wrong_guess_consumes_attempt_and_unlocks_next_stage(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    wrong = harness.wrong_titles()[0]
    response = harness.guess(headers, game, wrong)
    body = response.json()
    assert response.status_code == 200
    assert body["correct"] is False
    assert body["game"]["attempts_used"] == 1
    assert body["game"]["remaining_attempts"] == 5
    assert body["game"]["unlocked_stage"] == 2
    assert body["game"]["guesses"] == [
        {"attempt": 1, "text": wrong, "skipped": False, "correct": False,
         "same_artist": False}
    ]


def test_correct_guess_on_third_attempt_ends_with_60_points(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    wrong = harness.wrong_titles()
    game = harness.guess(headers, game, wrong[0]).json()["game"]
    game = harness.guess(headers, game, wrong[1]).json()["game"]
    secret = harness.secret()
    body = harness.guess(headers, game, secret.title.upper()).json()
    assert body["correct"] is True
    assert body["game"]["status"] == "won"
    assert body["game"]["score"] == 60
    assert body["game"]["attempts_used"] == 3
    assert body["game"]["answer"]["title"] == secret.title
    assert body["game"]["answer"]["artist"] == secret.artist
    # Encerrada: todos os estágios ficam liberados para reouvir.
    assert body["game"]["unlocked_stage"] == 6


def test_first_attempt_win_scores_100(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    body = harness.guess(headers, game, harness.secret().title).json()
    assert body["game"]["score"] == 100


def test_six_wrong_guesses_lose_with_zero_points(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    for text in harness.wrong_titles(count=6):
        game = harness.guess(headers, game, text).json()["game"]
    assert game["status"] == "lost"
    assert game["score"] == 0
    assert game["attempts_used"] == 6
    assert game["remaining_attempts"] == 0
    assert game["answer"]["title"] == harness.secret().title


def test_no_extra_attempts_after_game_ends(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    game = harness.guess(headers, game, harness.secret().title).json()["game"]
    response = harness.guess(headers, game, "Qualquer coisa", attempt=2)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "game_finished"
    skip = harness.client.post(f"/api/games/{game['id']}/skip", json={"attempt": 2},
                               headers=headers)
    assert skip.status_code == 409
    # Recomeçar devolve a mesma partida concluída.
    again = harness.start(headers)
    assert again["id"] == game["id"] and again["status"] == "won"


def test_resubmitted_attempt_number_is_rejected_without_consuming(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    wrong = harness.wrong_titles()
    harness.guess(headers, game, wrong[0], attempt=1)
    replay = harness.guess(headers, game, wrong[1], attempt=1)  # duplo clique / retry
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "attempt_mismatch"
    future = harness.guess(headers, game, wrong[1], attempt=5)
    assert future.status_code == 409
    state = harness.client.get(f"/api/games/{game['id']}", headers=headers).json()
    assert state["attempts_used"] == 1


def test_duplicate_guess_does_not_consume_attempt(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    wrong = harness.wrong_titles()[0]
    game = harness.guess(headers, game, wrong).json()["game"]
    duplicate = harness.guess(headers, game, f"  {wrong.upper()} ")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_guess"
    state = harness.client.get(f"/api/games/{game['id']}", headers=headers).json()
    assert state["attempts_used"] == 1


def test_empty_guess_is_rejected(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    response = harness.guess(headers, game, "?!")
    assert response.status_code == 422
    assert harness.client.get(f"/api/games/{game['id']}", headers=headers).json()[
        "attempts_used"] == 0


def test_skip_consumes_attempt_and_six_skips_lose(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    for attempt in range(1, 7):
        response = harness.client.post(f"/api/games/{game['id']}/skip",
                                       json={"attempt": attempt}, headers=headers)
        assert response.status_code == 200
        game = response.json()
    assert game["status"] == "lost"
    assert all(g["skipped"] for g in game["guesses"])


def test_players_cannot_touch_each_others_games(harness: Harness) -> None:
    alice = harness.new_player()
    bob = harness.new_player()
    game = harness.start(alice)
    for method, url, body in [
        ("get", f"/api/games/{game['id']}", None),
        ("post", f"/api/games/{game['id']}/guess", {"guess": "x", "attempt": 1}),
        ("post", f"/api/games/{game['id']}/skip", {"attempt": 1}),
        ("get", f"/api/games/{game['id']}/audio?stage=1", None),
        ("get", f"/api/games/{game['id']}/result", None),
    ]:
        response = harness.client.request(method.upper(), url, json=body, headers=bob)
        assert response.status_code == 404, url
    state = harness.client.get(f"/api/games/{game['id']}", headers=alice).json()
    assert state["attempts_used"] == 0


def test_guess_on_unknown_game_returns_404(harness: Harness) -> None:
    headers = harness.new_player()
    for game_id in ("00000000-0000-4000-8000-000000000000", "nao-e-uuid"):
        response = harness.client.post(f"/api/games/{game_id}/guess",
                                       json={"guess": "x", "attempt": 1}, headers=headers)
        assert response.status_code == 404


def test_authentication_is_required(harness: Harness) -> None:
    assert harness.client.post("/api/games/start", json={"category": "rock"}).status_code == 401
    bad = {"Authorization": "Bearer " + "x" * 43}
    assert harness.client.post("/api/games/start", json={"category": "rock"},
                               headers=bad).status_code == 401
    assert harness.client.get("/api/statistics", headers={"X-Player-Token": "curto"}
                              ).status_code == 401


def test_x_player_token_header_also_works(harness: Harness) -> None:
    token = harness.new_player()["Authorization"].split()[1]
    response = harness.client.get("/api/players/me", headers={"X-Player-Token": token})
    assert response.status_code == 200


def test_unknown_category_is_rejected(harness: Harness) -> None:
    headers = harness.new_player()
    response = harness.client.post("/api/games/start", json={"category": "jazz"},
                                   headers=headers)
    assert response.status_code == 422
    assert harness.client.get("/api/daily/jazz").status_code == 404


def test_all_six_categories_are_playable(harness: Harness) -> None:
    headers = harness.new_player()
    categories = [c["slug"] for c in harness.client.get("/api/categories").json()]
    assert categories == ["rock", "pop", "rap", "country", "eletronica", "geral"]
    for slug in categories:
        game = harness.start(headers, slug)
        assert game["category"]["slug"] == slug
        audio = harness.client.get(f"/api/games/{game['id']}/audio?stage=1", headers=headers)
        assert audio.status_code == 200
    overview = harness.client.get("/api/daily", headers=headers).json()
    assert {c["status"] for c in overview["categories"]} == {"in_progress"}


def test_daily_overview_reflects_results(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers, "pop")
    harness.guess(headers, game, harness.secret("pop").title)
    overview = harness.client.get("/api/daily", headers=headers).json()
    pop = next(c for c in overview["categories"] if c["slug"] == "pop")
    assert pop["status"] == "won" and pop["score"] == 100 and pop["game_id"] == game["id"]
    assert overview["audio"]["demo_mode"] is True
    assert overview["rules"]["stages_seconds"] == [0.5, 1, 2, 4, 8, 16]  # dobra a cada estágio
    assert overview["rules"]["score_table"] == [100, 80, 60, 40, 20, 10]


def test_configurable_rules(harness_factory) -> None:
    h = harness_factory(clip_stages_seconds="1,4,10", score_table="50,20,5")
    headers = h.new_player()
    game = h.start(headers)
    assert game["max_attempts"] == 3
    game = h.guess(headers, game, h.wrong_titles()[0]).json()["game"]
    body = h.guess(headers, game, h.secret().title).json()
    assert body["game"]["score"] == 20


def test_game_started_before_midnight_can_be_finished_after(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    secret = harness.secret().title
    harness.clock.advance(hours=12)  # já é o dia seguinte em São Paulo
    body = harness.guess(headers, game, secret).json()
    assert body["game"]["status"] == "won"
    assert body["game"]["date"] == "2026-10-15"
    # E o desafio de hoje é uma nova partida.
    new_game = harness.start(headers)
    assert new_game["id"] != game["id"] and new_game["date"] == "2026-10-16"


def test_rate_limit_on_guesses(harness_factory) -> None:
    h = harness_factory(rate_limit_enabled=True, rate_limit_guess_per_minute=3)
    headers = h.new_player()
    game = h.start(headers)
    wrong = h.wrong_titles()
    for text in wrong[:3]:
        game = h.guess(headers, game, text).json()["game"]
    limited = h.guess(headers, game, wrong[3])
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
    assert h.client.get(f"/api/games/{game['id']}", headers=headers).json()["attempts_used"] == 3


def test_rate_limit_on_player_creation(harness_factory) -> None:
    h = harness_factory(rate_limit_enabled=True, rate_limit_players_per_hour=2)
    assert h.client.post("/api/players").status_code == 201
    assert h.client.post("/api/players").status_code == 201
    assert h.client.post("/api/players").status_code == 429
