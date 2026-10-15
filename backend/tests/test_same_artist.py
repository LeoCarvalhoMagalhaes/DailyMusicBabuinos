"""Palpite errado de uma música do mesmo artista: marcado como "quase" (amarelo)."""

from __future__ import annotations

from sqlalchemy import select

from app.models import GameSession, MusicTrack
from app.services.answers import same_artist
from tests.conftest import Harness
from tests.test_multiplayer import guess as mp_guess
from tests.test_multiplayer import round_track, setup_match


def other_song_by(h: Harness, track: MusicTrack) -> str | None:
    """Título de outra música do catálogo com o mesmo artista (se houver)."""
    with h.app.state.session_factory() as db:
        return db.scalar(select(MusicTrack.title).where(
            MusicTrack.edition == track.edition, MusicTrack.artist == track.artist,
            MusicTrack.id != track.id, MusicTrack.title != track.title))


def other_artist_song(h: Harness, track: MusicTrack) -> str:
    with h.app.state.session_factory() as db:
        return db.scalar(select(MusicTrack.title).where(
            MusicTrack.edition == track.edition, MusicTrack.artist != track.artist))


def test_same_artist_rules() -> None:
    assert same_artist("Queen", ["queen"])
    assert same_artist("Kenny Rogers & Dolly Parton", ["dolly parton"])  # parceria
    assert same_artist("Zé Neto & Cristiano", ["ze neto and cristiano"])
    assert not same_artist("Queen", ["queen latifah"])
    assert not same_artist("Queen", [])


def _daily_with_two_songs(h: Harness) -> tuple[dict, dict, MusicTrack, str]:
    """Primeira categoria em que o artista da resposta tem outra música no catálogo."""
    for category in ("rock", "pop", "rap", "country", "eletronica", "geral"):
        headers = h.new_player()
        game = h.start(headers, category)
        secret = h.secret(category)
        sibling = other_song_by(h, secret)
        if sibling:
            return headers, game, secret, sibling
    raise AssertionError("nenhum artista com duas músicas no catálogo")  # pragma: no cover


def test_daily_wrong_guess_by_same_artist_is_marked(main_harness: Harness) -> None:
    h = main_harness
    headers, game, secret, sibling = _daily_with_two_songs(h)
    near = h.guess(headers, game, sibling).json()
    assert near["correct"] is False
    assert near["game"]["guesses"][-1]["same_artist"] is True
    far = h.guess(headers, near["game"], other_artist_song(h, secret)).json()
    assert far["game"]["guesses"][-1]["same_artist"] is False
    won = h.guess(headers, far["game"], secret.title).json()
    assert won["correct"] and won["game"]["guesses"][-1]["same_artist"] is False
    # Não revela a resposta: só diz que o artista do palpite é o mesmo.
    assert secret.title not in str(near)


def test_endless_uses_the_same_rule(main_harness: Harness) -> None:
    h = main_harness
    headers = h.new_player()
    for _ in range(30):
        data = h.client.post("/api/endless/next", json={"category": "rock"},
                             headers=headers).json()
        with h.app.state.session_factory() as db:
            track = db.get(GameSession, data["game"]["id"]).track
            db.expunge(track)
        sibling = other_song_by(h, track)
        game = data["game"]
        if sibling:
            r = h.client.post(f"/api/games/{game['id']}/guess",
                              json={"guess": sibling, "attempt": 1}, headers=headers).json()
            assert r["game"]["guesses"][0]["same_artist"] is True
            return
        h.client.post(f"/api/games/{game['id']}/guess",
                      json={"guess": track.title, "attempt": 1}, headers=headers)
    raise AssertionError("nenhuma rodada com artista repetido no catálogo")  # pragma: no cover


def test_multiplayer_marks_only_for_the_guesser(main_harness: Harness) -> None:
    h = main_harness
    code, (alice, bob) = setup_match(h, 2)
    for number in range(1, 19):
        track = round_track(h, code, number)
        sibling = other_song_by(h, track)
        if sibling:
            r = mp_guess(h, alice, code, number, 1, sibling).json()
            mine = r["state"]["match"]["my_game"]["guesses"][0]
            assert mine["same_artist"] is True and mine["correct"] is False
            # O Bob vê só o andamento da Alice, nunca o palpite nem a marca.
            bob_view = h.client.get(f"/api/mp/rooms/{code}", headers=bob).json()
            assert sibling not in str(bob_view["match"]["progress"])
            return
        # Rodada sem irmã: os dois acertam para passar.
        for headers in (alice, bob):
            mp_guess(h, headers, code, number, 1, track.title)
        h.clock.advance(seconds=9)
        h.client.get(f"/api/mp/rooms/{code}", headers=alice)
    raise AssertionError("nenhuma rodada com artista repetido")  # pragma: no cover
