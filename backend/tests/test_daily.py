from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.models import DailyChallenge, MusicTrack
from app.services.daily import get_or_create_challenge
from tests.conftest import NOON_SP, FakeProvider, Harness


def _challenge_slug(h: Harness, category: str = "rock") -> str:
    headers = h.new_player()
    h.start(headers, category)
    return h.secret(category).slug


def test_same_song_for_every_player_on_same_day(main_harness: Harness) -> None:
    players = [main_harness.new_player() for _ in range(3)]
    games = [main_harness.start(p, "rock") for p in players]
    with main_harness.app.state.session_factory() as db:
        rows = db.query(DailyChallenge).filter_by(category="rock").all()
    assert len(rows) == 1
    assert len({g["date"] for g in games}) == 1
    assert len({g["id"] for g in games}) == 3  # partidas diferentes, mesma música


def test_independent_servers_pick_the_same_song(harness_factory, fake_provider) -> None:
    # Dois "servidores" com bancos separados e o mesmo segredo chegam à mesma música.
    a = harness_factory(provider=fake_provider, audio_provider="deezer", db_name="a.db")
    b = harness_factory(provider=FakeProvider(), audio_provider="deezer", db_name="b.db")
    for category in ("rock", "pop", "rap", "country", "eletronica", "geral"):
        assert _challenge_slug(a, category) == _challenge_slug(b, category)


def test_different_secret_gives_different_schedule(harness_factory) -> None:
    a = harness_factory(provider=FakeProvider(), audio_provider="deezer", db_name="a.db")
    b = harness_factory(provider=FakeProvider(), audio_provider="deezer", db_name="b.db",
                        challenge_secret="outro-segredo-totalmente-diferente-1234567")
    picks_a = [_challenge_slug(a, c) for c in ("rock", "pop", "rap", "country", "geral")]
    picks_b = [_challenge_slug(b, c) for c in ("rock", "pop", "rap", "country", "geral")]
    assert picks_a != picks_b


def test_reload_keeps_the_same_challenge(main_harness: Harness) -> None:
    headers = main_harness.new_player()
    first = main_harness.start(headers)
    slug = main_harness.secret().slug
    for _ in range(3):
        assert main_harness.start(headers)["id"] == first["id"]
    assert main_harness.secret().slug == slug


def test_challenge_changes_exactly_at_midnight_in_sao_paulo(main_harness: Harness) -> None:
    clock = main_harness.clock
    clock.set(datetime(2026, 10, 16, 2, 59, tzinfo=UTC))  # 23:59 em São Paulo (dia 15)
    headers = main_harness.new_player()
    late = main_harness.start(headers)
    assert late["date"] == "2026-10-15"
    first_slug = main_harness.secret().slug
    clock.set(datetime(2026, 10, 16, 3, 0, tzinfo=UTC))  # 00:00 em São Paulo (dia 16)
    early = main_harness.start(headers)
    assert early["date"] == "2026-10-16"
    assert early["id"] != late["id"]
    assert main_harness.secret().slug != first_slug
    overview = main_harness.client.get("/api/daily").json()
    assert overview["date"] == "2026-10-16"
    assert overview["next_reset_at"].startswith("2026-10-17T03:00:00")
    assert overview["timezone"] == "America/Sao_Paulo"


def test_client_cannot_choose_the_date(main_harness: Harness) -> None:
    headers = main_harness.new_player()
    response = main_harness.client.post(
        "/api/games/start", json={"category": "rock", "date": "2030-01-01"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["date"] == "2026-10-15"


def test_no_repeats_within_window_and_artist_cooldown(main_harness: Harness) -> None:
    headers = main_harness.new_player()
    seen_slugs: list[str] = []
    artists_by_day: list[str] = []
    for day in range(40):
        main_harness.clock.set(NOON_SP + timedelta(days=day))
        main_harness.start(headers, "rock")
        main_harness.start(headers, "geral")
        rock = main_harness.secret("rock")
        geral = main_harness.secret("geral")
        assert rock.slug != geral.slug  # nunca a mesma música em duas categorias no dia
        seen_slugs.append(rock.slug)
        seen_slugs.append(geral.slug)
        artists_by_day.append(rock.artist)
    assert len(seen_slugs) == len(set(seen_slugs))  # nenhuma repetição em 40 dias
    for i, artist in enumerate(artists_by_day):
        window = artists_by_day[max(0, i - 7):i]
        assert artist not in window


def test_unavailable_tracks_are_skipped(main_harness: Harness, fake_provider) -> None:
    settings = main_harness.settings
    with main_harness.app.state.session_factory() as db:
        day = main_harness.clock.today()
        # Descobre a primeira escolha e a marca como indisponível em outro banco lógico.
        first = get_or_create_challenge(db, settings, fake_provider, "pop", day,
                                        main_harness.clock.now())
        first_slug = first.track.slug
        db.delete(first)
        db.query(MusicTrack).update({"availability": "unknown"})
        db.commit()
        fake_provider.unavailable.add(first_slug)
        second = get_or_create_challenge(db, settings, fake_provider, "pop", day,
                                         main_harness.clock.now())
        assert second.track.slug != first_slug
        assert db.query(MusicTrack).filter_by(slug=first_slug).one().availability == (
            "unavailable"
        )


def test_challenge_is_published_even_if_provider_is_down(main_harness: Harness,
                                                         fake_provider) -> None:
    fake_provider.fail_checks = True
    headers = main_harness.new_player()
    game = main_harness.start(headers, "rap")
    assert game["status"] == "in_progress"


def test_small_catalog_relaxes_constraints(harness: Harness) -> None:
    # O modo demo tem poucas faixas por categoria; mesmo assim cada dia tem desafio.
    headers = harness.new_player()
    for day in range(15):
        harness.clock.set(NOON_SP + timedelta(days=day))
        assert harness.start(headers, "pop")["status"] == "in_progress"


def test_challenge_number_counts_days_since_launch(harness: Harness) -> None:
    overview = harness.client.get("/api/daily").json()
    expected = (date(2026, 10, 15) - harness.settings.launch_date).days + 1
    assert overview["challenge_number"] == expected
