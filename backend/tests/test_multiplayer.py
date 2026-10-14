"""Multiplayer: contas, salas de 2 a 8, partidas de 18 músicas e tempo real."""

from __future__ import annotations

import json
from collections import Counter
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import Account, GameSession, Match, MatchRound, MusicTrack, Room
from app.services import multiplayer as mp
from tests.conftest import Harness, HarnessFactory

CATEGORIES = ["rock", "pop", "rap", "country", "eletronica", "geral"]
_counter = iter(range(10_000))


def register(h: Harness, name: str | None = None) -> dict[str, str]:
    name = name or f"jogador{next(_counter)}"
    r = h.client.post("/api/auth/register",
                      json={"username": name, "password": "senha-segura-123",
                            "display_name": name.title()})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def create_room(h: Harness, headers: dict, order: list[str] | None = None) -> dict:
    r = h.client.post("/api/mp/rooms", json={"category_order": order}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def join(h: Harness, headers: dict, code: str) -> dict:
    r = h.client.post("/api/mp/rooms/join", json={"code": code}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def state(h: Harness, headers: dict, code: str) -> dict:
    r = h.client.get(f"/api/mp/rooms/{code}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def ready(h: Harness, headers: dict, code: str, value: bool = True) -> dict:
    return h.client.post(f"/api/mp/rooms/{code}/ready", json={"ready": value},
                         headers=headers).json()


def setup_match(h: Harness, players: int = 2, order: list[str] | None = None
                ) -> tuple[str, list[dict]]:
    heads = [register(h) for _ in range(players)]
    code = create_room(h, heads[0], order)["code"]
    for headers in heads[1:]:
        join(h, headers, code)
        ready(h, headers, code)
    r = h.client.post(f"/api/mp/rooms/{code}/start", headers=heads[0])
    assert r.status_code == 200, r.text
    return code, heads


def round_track(h: Harness, code: str, number: int | None = None) -> MusicTrack:
    with h.app.state.session_factory() as db:
        room = db.scalar(select(Room).where(Room.code == code))
        match = db.get(Match, room.current_match_id)
        rnd = next(r for r in match.rounds if r.number == (number or match.current_round))
        track = rnd.track
        db.expunge(track)
        return track


def guess(h: Harness, headers: dict, code: str, number: int, attempt: int, text: str):
    return h.client.post(f"/api/mp/rooms/{code}/guess",
                         json={"round": number, "attempt": attempt, "guess": text},
                         headers=headers)


def skip(h: Harness, headers: dict, code: str, number: int, attempt: int):
    return h.client.post(f"/api/mp/rooms/{code}/skip",
                         json={"round": number, "attempt": attempt}, headers=headers)


# ------------------------------------------------------------------- contas

def test_register_login_logout(main_harness: Harness) -> None:
    h = main_harness
    r = h.client.post("/api/auth/register", json={"username": "Babuino_1", "password":
                                                  "rock-and-roll", "display_name": "  Babu  "})
    assert r.status_code == 201
    body = r.json()
    assert body["account"] == {"id": body["account"]["id"], "username": "babuino_1",
                               "display_name": "Babu"}
    with h.app.state.session_factory() as db:
        stored = db.scalar(select(Account).where(Account.username == "babuino_1"))
        assert stored.password_hash.startswith("scrypt$")
        assert "rock-and-roll" not in stored.password_hash

    dup = h.client.post("/api/auth/register", json={"username": "BABUINO_1", "password":
                                                    "outra-senha-1", "display_name": "Outro"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "username_taken"
    weak = h.client.post("/api/auth/register", json={"username": "novo_user", "password":
                                                     "curta", "display_name": "Novo"})
    assert weak.status_code == 422

    wrong = h.client.post("/api/auth/login", json={"username": "babuino_1", "password": "errada!!"})
    unknown = h.client.post("/api/auth/login", json={"username": "ninguem", "password": "errada!!"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # não revela se o usuário existe

    login = h.client.post("/api/auth/login", json={"username": "babuino_1",
                                                   "password": "rock-and-roll"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    assert h.client.get("/api/auth/me", headers=headers).json()["username"] == "babuino_1"
    assert h.client.post("/api/auth/logout", headers=headers).status_code == 204
    assert h.client.get("/api/auth/me", headers=headers).status_code == 401
    # O token anônimo do jogador não vale como login (e vice-versa).
    player = h.new_player()
    assert h.client.get("/api/auth/me", headers=player).status_code == 401
    assert h.client.post("/api/mp/rooms", json={}, headers=player).status_code == 401


# -------------------------------------------------------------------- salas

def test_room_lobby_rules(main_harness: Harness) -> None:
    h = main_harness
    host = register(h)
    room = create_room(h, host)
    code = room["code"]
    assert len(code) == 6 and room["status"] == "waiting"
    assert room["members"][0]["is_host"] and room["members"][0]["ready"]
    assert not room["can_start"] and "mínimo de 2" in room["start_blocker"]

    guest = register(h)
    joined = join(h, guest, code.lower())  # código não diferencia maiúsculas
    assert len(joined["members"]) == 2
    assert h.client.post(f"/api/mp/rooms/{code}/start", headers=guest).status_code == 403
    blocked = h.client.post(f"/api/mp/rooms/{code}/start", headers=host)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "players_not_ready"
    assert ready(h, guest, code)["members"][1]["ready"] is True
    assert state(h, host, code)["can_start"] is True

    # Entrar de novo (outra aba / reconexão) não duplica o jogador.
    join(h, guest, code)
    assert len(state(h, host, code)["members"]) == 2

    # Ordem das categorias definida pelo anfitrião.
    order = ["geral", "rock", "pop", "rap", "country", "eletronica"]
    assert h.client.post(f"/api/mp/rooms/{code}/order", json={"category_order": order},
                         headers=guest).status_code == 403
    r = h.client.post(f"/api/mp/rooms/{code}/order", json={"category_order": order},
                      headers=host)
    assert r.json()["category_order"] == order
    bad = h.client.post(f"/api/mp/rooms/{code}/order",
                        json={"category_order": ["rock"] * 6}, headers=host)
    assert bad.status_code == 409

    # Quem não é da sala não vê nada dela.
    stranger = register(h)
    assert h.client.get(f"/api/mp/rooms/{code}", headers=stranger).status_code == 404
    assert h.client.post("/api/mp/rooms/join", json={"code": "ZZZZZZ"},
                         headers=stranger).status_code == 404


def test_room_accepts_at_most_eight_players(main_harness: Harness) -> None:
    h = main_harness
    host = register(h)
    code = create_room(h, host)["code"]
    for _ in range(7):
        join(h, register(h), code)
    assert len(state(h, host, code)["members"]) == 8
    ninth = h.client.post("/api/mp/rooms/join", json={"code": code}, headers=register(h))
    assert ninth.status_code == 409 and ninth.json()["error"]["code"] == "room_full"


def test_host_leaving_lobby_passes_the_room_on(main_harness: Harness) -> None:
    h = main_harness
    host, guest = register(h), register(h)
    code = create_room(h, host)["code"]
    join(h, guest, code)
    assert h.client.post(f"/api/mp/rooms/{code}/leave", headers=host).status_code == 204
    after = state(h, guest, code)
    assert len(after["members"]) == 1 and after["members"][0]["is_host"]
    h.client.post(f"/api/mp/rooms/{code}/leave", headers=guest)
    assert h.client.get(f"/api/mp/rooms/{code}", headers=guest).status_code == 404  # fechada


# ------------------------------------------------------------------ partida

def test_match_has_18_songs_three_per_category(main_harness: Harness) -> None:
    h = main_harness
    order = ["pop", "geral", "rock", "eletronica", "rap", "country"]
    code, heads = setup_match(h, 3, order)
    with h.app.state.session_factory() as db:
        room = db.scalar(select(Room).where(Room.code == code))
        match = db.get(Match, room.current_match_id)
        rounds = sorted(match.rounds, key=lambda r: r.number)
        assert len(rounds) == 18
        assert [r.category for r in rounds] == [c for c in order for _ in range(3)]
        assert Counter(r.category for r in rounds) == dict.fromkeys(CATEGORIES, 3)
        assert len({r.track_id for r in rounds}) == 18  # sem repetir na partida
        daily_ids = {h.secret(c).id for c in CATEGORIES}
        assert not daily_ids & {r.track_id for r in rounds}  # nada do diário de hoje
        # Todos os jogadores recebem a mesma música na rodada.
        sessions = db.scalars(select(GameSession).where(GameSession.match_round_id ==
                                                        rounds[0].id)).all()
        assert len(sessions) == 3 and len({s.track_id for s in sessions}) == 1
        assert {s.mode for s in sessions} == {"match"}
    current = state(h, heads[1], code)
    assert current["status"] == "playing"
    # Datas sempre com fuso: o navegador calcula o cronômetro a partir delas.
    for value in (current["match"]["phase_ends_at"], current["match"]["round"]["ends_at"],
                  current["server_time"]):
        assert value.endswith(("Z", "+00:00")), value
    match_state = current["match"]
    assert (match_state["current_round"], match_state["total_rounds"]) == (1, 18)
    assert match_state["round"]["category"]["slug"] == "pop"
    assert match_state["round"]["index_in_category"] == 1
    # Partida em andamento: ninguém novo entra.
    late = h.client.post("/api/mp/rooms/join", json={"code": code}, headers=register(h))
    assert late.status_code == 409 and late.json()["error"]["code"] == "match_in_progress"


def test_scoring_is_server_side_with_speed_bonus(main_harness: Harness) -> None:
    h = main_harness
    code, (alice, bob) = setup_match(h, 2)
    track = round_track(h, code)
    h.clock.advance(seconds=15)  # 45 s de 60 restantes -> bônus floor(50 * 0,75) = 37
    r = guess(h, alice, code, 1, 1, track.title)
    assert r.status_code == 200 and r.json()["correct"] is True
    mine = r.json()["state"]["match"]["my_game"]
    assert mine["score"] == 100 + 37 and mine["speed_bonus"] == 37
    # Reenvio da mesma jogada (duplo clique / retry) não pontua de novo.
    again = guess(h, alice, code, 1, 1, track.title)
    assert again.status_code == 409
    assert state(h, alice, code)["match"]["my_game"]["score"] == 137

    # Bob ainda está jogando: a resposta não aparece para ninguém, nem para a Alice.
    bob_view = state(h, bob, code)
    assert bob_view["match"]["phase"] == "playing" and bob_view["match"]["answer"] is None
    assert track.title not in json.dumps(bob_view)
    alice_view = state(h, alice, code)
    assert alice_view["match"]["answer"] is None
    assert alice_view["match"]["my_game"]["answer"] is None
    alice_progress = next(p for p in bob_view["match"]["progress"]
                          if p["account_id"] == alice_view["me"])
    assert alice_progress["status"] == "won" and alice_progress["attempts_used"] == 1

    # Bob erra e pula: o trecho liberado aumenta só para ele.
    wrong = guess(h, bob, code, 1, 1, "Música Que Não Existe")
    assert wrong.json()["correct"] is False
    assert skip(h, bob, code, 1, 2).json()["match"]["my_game"]["unlocked_stage"] == 3
    h.clock.advance(seconds=5)
    won = guess(h, bob, code, 1, 3, track.title).json()
    # 60 pontos base + floor(50 * 40/60) = 33.
    assert won["state"]["match"]["my_game"]["score"] == 60 + 33
    # Todos terminaram: a rodada vai para a revelação, igual para os dois.
    revealed = won["state"]["match"]
    assert revealed["phase"] == "reveal" and revealed["answer"]["title"] == track.title
    board = {s["display_name"]: s for s in revealed["scoreboard"]}
    assert [s["position"] for s in revealed["scoreboard"]] == [1, 2]
    assert revealed["scoreboard"][0]["total_score"] == 137
    assert sum(s["correct"] for s in board.values()) == 2


def test_round_times_out_and_next_round_starts(main_harness: Harness) -> None:
    h = main_harness
    code, (alice, bob) = setup_match(h, 2)
    guess(h, alice, code, 1, 1, round_track(h, code).title)
    h.clock.advance(seconds=61)
    view = state(h, bob, code)["match"]
    assert view["phase"] == "reveal" and view["my_game"]["status"] == "lost"
    assert skip(h, bob, code, 1, 1).json()["error"]["code"] == "round_closed"
    h.clock.advance(seconds=9)
    view = state(h, bob, code)["match"]
    assert view["phase"] == "playing" and view["current_round"] == 2
    assert view["my_game"]["attempts_used"] == 0 and view["answer"] is None
    assert [r["number"] for r in view["history"]] == [1]


def test_audio_only_for_current_round_and_unlocked_stage(main_harness: Harness) -> None:
    h = main_harness
    code, (alice, _bob) = setup_match(h, 2)
    ok = h.client.get(f"/api/mp/rooms/{code}/rounds/1/audio?stage=1", headers=alice)
    assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store"
    assert h.client.get(f"/api/mp/rooms/{code}/rounds/1/audio?stage=2",
                        headers=alice).status_code == 403
    assert h.client.get(f"/api/mp/rooms/{code}/rounds/2/audio?stage=1",
                        headers=alice).status_code == 409  # rodada futura
    stranger = register(h)
    assert h.client.get(f"/api/mp/rooms/{code}/rounds/1/audio?stage=1",
                        headers=stranger).status_code == 404


def play_full_match(h: Harness, code: str, alice: dict, bob: dict) -> dict:
    """Alice acerta na 1ª tentativa; Bob acerta só nas rodadas pares, na 2ª."""
    for number in range(1, 19):
        title = round_track(h, code, number).title
        assert guess(h, alice, code, number, 1, title).json()["correct"]
        if number % 2 == 0:
            skip(h, bob, code, number, 1)
            guess(h, bob, code, number, 2, title)
        else:
            for attempt in range(1, 7):
                skip(h, bob, code, number, attempt)
        h.clock.advance(seconds=9)
        final = state(h, alice, code)
    return final


def test_full_match_final_ranking(main_harness: Harness) -> None:
    h = main_harness
    code, (alice, bob) = setup_match(h, 2)
    final = play_full_match(h, code, alice, bob)
    assert final["status"] == "waiting"  # sala volta para a espera
    match = final["match"]
    assert match["status"] == "finished" and len(match["history"]) == 18
    first, second = match["scoreboard"]
    assert first["account_id"] == final["me"] and match["winner_ids"] == [final["me"]]
    # Sem mexer no relógio dentro das rodadas, o bônus é sempre o máximo (50).
    assert (first["correct"], first["total_score"]) == (18, 18 * 150)
    assert (second["correct"], second["total_score"]) == (9, 9 * (80 + 50))
    assert all(c["correct"] == 3 for c in first["per_category"])
    assert first["average_response_ms"] == 0
    # Os outros jogadores ficam prontos de novo só quando quiserem.
    assert [m["ready"] for m in final["members"]] == [True, False]
    # Estatísticas do diário não são afetadas pelo multiplayer.
    with h.app.state.session_factory() as db:
        assert db.scalar(select(GameSession).where(GameSession.mode == "daily")) is None


def test_reconnect_does_not_duplicate_or_give_points(main_harness: Harness) -> None:
    h = main_harness
    code, (alice, bob) = setup_match(h, 2)
    # "Desconectar" e voltar: entrar de novo e consultar o estado.
    join(h, bob, code)
    view = state(h, bob, code)
    assert len(view["members"]) == 2
    with h.app.state.session_factory() as db:
        rnd = db.scalar(select(MatchRound).where(MatchRound.number == 1))
        sessions = db.scalars(select(GameSession).where(GameSession.match_round_id ==
                                                        rnd.id)).all()
        assert len(sessions) == 2
    assert view["match"]["my_game"]["score"] == 0


def test_leaving_does_not_stop_the_others(main_harness: Harness) -> None:
    h = main_harness
    code, (alice, bob, carol) = setup_match(h, 3)
    assert h.client.post(f"/api/mp/rooms/{code}/leave", headers=bob).status_code == 204
    view = state(h, alice, code)
    assert view["status"] == "playing"
    assert next(m for m in view["members"] if not m["is_host"] and m["left"])
    title = round_track(h, code).title
    guess(h, alice, code, 1, 1, title)
    guess(h, carol, code, 1, 1, title)
    # Quem saiu não segura a rodada: com os dois ativos terminados, ela fecha.
    assert state(h, alice, code)["match"]["phase"] == "reveal"
    left_line = next(s for s in state(h, alice, code)["match"]["scoreboard"] if s["left"])
    assert left_line["total_score"] == 0
    # Bob pode voltar à mesma partida (reconexão), sem duplicar.
    join(h, bob, code)
    assert not any(m["left"] for m in state(h, alice, code)["members"])

    # Todos saem: partida abandonada e sala fechada.
    for headers in (alice, bob, carol):
        h.client.post(f"/api/mp/rooms/{code}/leave", headers=headers)
    with h.app.state.session_factory() as db:
        room = db.scalar(select(Room).where(Room.code == code))
        assert room.status == "closed"
        assert db.get(Match, room.current_match_id).status == "abandoned"


def test_inactive_match_is_abandoned(main_harness: Harness) -> None:
    h = main_harness
    code, _ = setup_match(h, 2)
    h.clock.advance(minutes=11)
    with h.app.state.session_factory() as db:
        mp.tick(db, h.settings, h.clock.now())
        room = db.scalar(select(Room).where(Room.code == code))
        assert room.status == "closed"
        assert db.get(Match, room.current_match_id).status == "abandoned"


def test_concurrent_advance_moves_one_round_only(main_harness: Harness) -> None:
    h = main_harness
    code, _ = setup_match(h, 2)
    h.clock.advance(seconds=61)
    factory = h.app.state.session_factory
    with factory() as db1, factory() as db2:
        room1 = db1.scalar(select(Room).where(Room.code == code))
        room2 = db2.scalar(select(Room).where(Room.code == code))
        db2.get(Match, room2.current_match_id)  # as duas sessões leem "playing"
        assert mp.advance(db1, h.settings, room1, h.clock.now()) is True
        mp.advance(db2, h.settings, room2, h.clock.now())
        match = db2.get(Match, room2.current_match_id)
        db2.refresh(match)
        assert (match.current_round, match.phase) == (1, "reveal")


# ---------------------------------------------------------------- WebSocket

@pytest.fixture
def realtime_harness(harness_factory: HarnessFactory, fake_provider) -> Harness:
    return harness_factory(provider=fake_provider, audio_provider="deezer",
                           realtime_enabled=True, realtime_interval_seconds=0.05)


def test_websocket_pushes_state_changes(realtime_harness: Harness) -> None:
    h = realtime_harness
    host = register(h)
    code = create_room(h, host)["code"]
    token = host["Authorization"].split()[1]
    with h.client.websocket_connect("/api/mp/ws") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": token, "room": code}))
        first = json.loads(ws.receive_text())
        assert first["type"] == "state" and first["state"]["code"] == code
        assert first["state"]["members"][0]["connected"] is True
        join(h, register(h), code)
        for _ in range(20):
            message = json.loads(ws.receive_text())
            if message["type"] == "state" and len(message["state"]["members"]) == 2:
                break
        else:  # pragma: no cover
            pytest.fail("o WebSocket não avisou a entrada do segundo jogador")
        ws.send_text(json.dumps({"type": "ping"}))


def test_websocket_rejects_invalid_session(realtime_harness: Harness) -> None:
    h = realtime_harness
    host = register(h)
    code = create_room(h, host)["code"]
    outsider = register(h)["Authorization"].split()[1]
    for token in ("token-invalido-" + "x" * 40, outsider):
        with h.client.websocket_connect("/api/mp/ws") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": token, "room": code}))
            with pytest.raises(Exception):  # noqa: B017 - conexão fechada pelo servidor
                ws.receive_text()


def test_room_codes_are_random_and_unambiguous() -> None:
    codes = {mp.new_room_code() for _ in range(2000)}
    assert len(codes) == 2000
    assert all(set(c) <= set(mp.CODE_ALPHABET) and len(c) == 6 for c in codes)
    assert not set("01IOL") & set(mp.CODE_ALPHABET)


def test_speed_bonus_formula(main_harness: Harness) -> None:
    rnd = MatchRound(started_at=main_harness.clock.now(),
                     ends_at=main_harness.clock.now() + timedelta(seconds=60))
    settings = main_harness.settings
    now = main_harness.clock.now()
    assert mp.speed_bonus(settings, rnd, now) == 50
    assert mp.speed_bonus(settings, rnd, now + timedelta(seconds=30)) == 25
    assert mp.speed_bonus(settings, rnd, now + timedelta(seconds=59.9)) == 0
    assert mp.speed_bonus(settings, rnd, now + timedelta(seconds=90)) == 0
