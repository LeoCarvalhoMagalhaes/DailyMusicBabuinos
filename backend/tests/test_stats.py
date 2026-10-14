from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.stats import compute_streaks, live_streak
from tests.conftest import NOON_SP, Harness


def _win(h: Harness, headers, category: str, wrong_first: int = 0) -> dict:
    game = h.start(headers, category)
    for text in h.wrong_titles(category, wrong_first):
        game = h.guess(headers, game, text).json()["game"]
    return h.guess(headers, game, h.secret(category).title).json()["game"]


def _lose(h: Harness, headers, category: str) -> dict:
    game = h.start(headers, category)
    for text in h.wrong_titles(category, 6):
        game = h.guess(headers, game, text).json()["game"]
    return game


def test_statistics_aggregate_results(harness: Harness) -> None:
    headers = harness.new_player()
    _win(harness, headers, "rock", wrong_first=0)  # 100
    _win(harness, headers, "pop", wrong_first=1)   # 80
    _lose(harness, headers, "rap")                 # 0
    stats = harness.client.get("/api/statistics", headers=headers).json()
    overall = stats["overall"]
    assert overall["games_played"] == 3
    assert overall["wins"] == 2
    assert overall["win_rate"] == round(2 / 3, 4)
    assert overall["total_score"] == 180
    assert overall["average_score"] == 60.0
    assert overall["distribution"] == [1, 1, 0, 0, 0, 0, 1]
    assert overall["current_streak"] == 1 and overall["best_streak"] == 1
    by_cat = {c["category"]: c for c in stats["categories"]}
    assert by_cat["rock"]["wins"] == 1 and by_cat["rock"]["total_score"] == 100
    assert by_cat["rap"]["wins"] == 0 and by_cat["rap"]["distribution"][-1] == 1
    assert by_cat["geral"]["games_played"] == 0


def test_in_progress_games_do_not_count(harness: Harness) -> None:
    headers = harness.new_player()
    game = harness.start(headers)
    harness.guess(headers, game, harness.wrong_titles()[0])
    stats = harness.client.get("/api/statistics", headers=headers).json()
    assert stats["overall"]["games_played"] == 0


def test_day_streaks(harness: Harness) -> None:
    headers = harness.new_player()
    for day in (0, 1, 2, 4, 5):  # 3 dias seguidos, pula um, mais 2
        harness.clock.set(NOON_SP + timedelta(days=day))
        _win(harness, headers, "rock")
        _win(harness, headers, "pop")  # duas partidas no mesmo dia contam um dia só
    stats = harness.client.get("/api/statistics", headers=headers).json()["overall"]
    assert stats["best_streak"] == 3
    assert stats["current_streak"] == 2
    harness.clock.set(NOON_SP + timedelta(days=6))
    assert harness.client.get("/api/statistics", headers=headers).json()["overall"][
        "current_streak"] == 2  # ainda pode jogar hoje
    harness.clock.set(NOON_SP + timedelta(days=7))
    assert harness.client.get("/api/statistics", headers=headers).json()["overall"][
        "current_streak"] == 0  # perdeu a sequência


def test_statistics_survive_restart(harness_factory) -> None:
    h = harness_factory()
    headers = h.new_player()
    _win(h, headers, "geral", wrong_first=2)
    first = h.client.get("/api/statistics", headers=headers).json()
    # Nova instância da aplicação apontando para o mesmo banco.
    app = create_app(h.settings, clock=h.clock)
    with TestClient(app) as client:
        again = client.get("/api/statistics", headers=headers).json()
    assert again == first
    assert again["overall"]["total_score"] == 60


def test_history_lists_results_with_answers(harness: Harness) -> None:
    headers = harness.new_player()
    won = _win(harness, headers, "rock")
    harness.clock.set(NOON_SP + timedelta(days=1))
    pending = harness.start(headers, "rock")
    history = harness.client.get("/api/history", headers=headers).json()
    assert history["total"] == 2
    newest, oldest = history["items"]
    assert newest["game_id"] == pending["id"] and newest["answer"] is None
    assert newest["status"] == "in_progress"
    assert oldest["game_id"] == won["id"] and oldest["answer"]["title"] == won["answer"]["title"]
    assert oldest["date"] == "2026-10-15" and oldest["score"] == 100


def test_other_players_have_isolated_stats(harness: Harness) -> None:
    alice, bob = harness.new_player(), harness.new_player()
    _win(harness, alice, "rock")
    assert harness.client.get("/api/statistics", headers=bob).json()["overall"][
        "games_played"] == 0
    assert harness.client.get("/api/history", headers=bob).json()["total"] == 0


def test_streak_helpers() -> None:
    d = date(2026, 1, 1)
    assert compute_streaks(set()) == (0, 0, None)
    assert compute_streaks({d, d + timedelta(1), d + timedelta(3)}) == (1, 2, d + timedelta(3))
    assert live_streak(5, d, d + timedelta(1)) == 5
    assert live_streak(5, d, d + timedelta(2)) == 0
