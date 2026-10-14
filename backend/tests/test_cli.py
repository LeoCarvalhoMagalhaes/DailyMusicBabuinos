"""Ferramentas de operação: verificação de áudio do catálogo (check-audio)."""

from __future__ import annotations

from app.cli import audio_summary, check_audio
from tests.conftest import FakeProvider, Harness


def test_check_audio_marks_tracks_and_summarizes_by_category(main_harness: Harness,
                                                             fake_provider: FakeProvider) -> None:
    edition = main_harness.settings.catalog_edition
    logs: list[str] = []
    sleeps: list[float] = []
    with main_harness.app.state.session_factory() as db:
        before = audio_summary(db, edition)
        assert all(sum(c.values()) == 100 for c in before.values())  # 6 listas de 100
        slug = "queen--bohemian-rhapsody"
        fake_provider.unavailable.add(slug)
        checked = check_audio(db, fake_provider, edition, limit=10_000, delay=0.5,
                              log=logs.append, sleep=sleeps.append)
        summary = audio_summary(db, edition)

    assert checked == len(logs) and checked > 0
    assert sleeps == [0.5] * (checked - 1)  # intervalo entre faixas, sem esperar à toa
    assert all(counts["unknown"] == 0 for counts in summary.values())
    assert summary["rock"]["unavailable"] == 1 and summary["rock"]["available"] == 99
    assert any(line.startswith("N/D Queen") for line in logs)


def test_check_audio_stops_on_repeated_failure_without_condemning_tracks(
        main_harness: Harness, fake_provider: FakeProvider) -> None:
    fake_provider.fail_checks = True
    logs: list[str] = []
    sleeps: list[float] = []
    edition = main_harness.settings.catalog_edition
    with main_harness.app.state.session_factory() as db:
        assert check_audio(db, fake_provider, edition, limit=50, log=logs.append,
                           sleep=sleeps.append) == 0
        summary = audio_summary(db, edition)
    assert sleeps == [5]  # tentou de novo uma vez antes de parar
    assert len(logs) == 1 and logs[0].startswith("ERRO")
    assert all(counts["unavailable"] == 0 for counts in summary.values())


def test_check_audio_recheck_revisits_unavailable_tracks(main_harness: Harness,
                                                         fake_provider: FakeProvider) -> None:
    edition = main_harness.settings.catalog_edition
    fake_provider.unavailable.add("queen--bohemian-rhapsody")
    with main_harness.app.state.session_factory() as db:
        check_audio(db, fake_provider, edition, 10_000, log=lambda _: None, sleep=lambda _: None)
        fake_provider.unavailable.clear()  # ex.: a busca melhorou
        assert check_audio(db, fake_provider, edition, 10_000, log=lambda _: None,
                           sleep=lambda _: None) == 0
        assert check_audio(db, fake_provider, edition, 10_000, log=lambda _: None,
                           sleep=lambda _: None, recheck=True) > 0
        assert audio_summary(db, edition)["rock"]["available"] == 100
