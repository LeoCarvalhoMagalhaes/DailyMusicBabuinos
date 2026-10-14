from __future__ import annotations

import json
import os

import httpx
import numpy as np
import pytest

from app.audio.base import TTLCache
from app.audio.deezer import DeezerProvider
from app.audio.local import LocalFileProvider
from app.audio.mp3 import Mp3FormatError, mp3_duration, parse_header, trim_mp3
from app.audio.synth import load_songs, render_int16
from app.audio.wav import decode_wav, encode_wav, trim_wav
from app.core.errors import AudioUnavailableError
from app.models import MusicTrack
from tests.conftest import FakeProvider, Harness

FRAME_HEADER = bytes([0xFF, 0xFB, 0x90, 0x00])  # MPEG1 Layer III, 128 kbps, 44.1 kHz
FRAME_LEN = 417
FRAME_DURATION = 1152 / 44100


def _frame(fill: int = 0x11) -> bytes:
    return FRAME_HEADER + bytes([fill]) * (FRAME_LEN - 4)


def _xing_frame() -> bytes:
    body = bytearray(FRAME_LEN - 4)
    body[32:36] = b"Xing"
    return FRAME_HEADER + bytes(body)


def _id3(title: str) -> bytes:
    text = b"\x00" + title.encode()
    frame = b"TIT2" + len(text).to_bytes(4, "big") + b"\x00\x00" + text
    size = len(frame)
    syncsafe = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
    return b"ID3\x03\x00\x00" + syncsafe + frame


def fake_mp3(seconds: float, title: str = "Musica Secreta") -> bytes:
    frames = int(seconds / FRAME_DURATION) + 1
    id3v1 = b"TAG" + title.encode().ljust(125, b"\x00")
    return _id3(title) + _xing_frame() + b"".join(_frame() for _ in range(frames)) + id3v1


def test_parse_header() -> None:
    header = parse_header(FRAME_HEADER, 0)
    assert header is not None
    assert header.bitrate_kbps == 128 and header.sample_rate == 44100
    assert header.length == FRAME_LEN
    assert parse_header(b"\x00\x00\x00\x00", 0) is None


def test_trim_mp3_removes_metadata_and_limits_duration() -> None:
    data = fake_mp3(30)
    clip, duration = trim_mp3(data, 3.0)
    assert 3.0 <= duration < 3.0 + FRAME_DURATION
    assert b"ID3" not in clip and b"TAG" not in clip and b"Xing" not in clip
    assert b"Musica Secreta" not in clip
    assert clip.startswith(FRAME_HEADER)
    assert len(clip) % FRAME_LEN == 0
    assert mp3_duration(data) == pytest.approx(30, abs=0.05)


def real_layout_preview(seconds: float = 30.0) -> bytes:
    """MP3 gerado com o mesmo layout de uma prévia real do Deezer (medida em 14/10/2026):
    tag ID3v2.4 vazia de 10 bytes, sem quadro Xing/Info e sem ID3v1, quadros MPEG-1
    Layer III de 128 kbps / 44,1 kHz em joint stereo, com padding alternado (417/418 bytes).
    O conteúdo dos quadros é sintético: nenhum áudio de terceiros fica no repositório."""
    out = bytearray(b"ID3\x04\x00\x00\x00\x00\x00\x00")
    elapsed, index = 0.0, 0
    while elapsed < seconds:
        padding = 1 - index % 2  # o 1º quadro da prévia real tem padding
        header = bytes([0xFF, 0xFB, 0x90 | (padding << 1), 0x64])
        out += header + bytes([0x22]) * (FRAME_LEN - 4 + padding)
        elapsed += FRAME_DURATION
        index += 1
    return bytes(out)


def test_trim_real_deezer_layout() -> None:
    data = real_layout_preview()
    header = parse_header(data, 10)
    assert header is not None and header.channel_mode == 1 and header.length == FRAME_LEN + 1
    assert mp3_duration(data) == pytest.approx(30, abs=0.05)
    for stage in (1, 2, 3, 5, 8, 12):
        clip, duration = trim_mp3(data, stage)
        # Na prévia real: 1,019 / 2,011 / 3,004 / 5,016 / 8,020 / 12,016 s.
        assert stage <= duration < stage + FRAME_DURATION
        assert not clip.startswith(b"ID3") and clip[:2] == b"\xff\xfb"
        assert b"Xing" not in clip and b"Info" not in clip
        assert mp3_duration(clip) == pytest.approx(duration)


@pytest.mark.skipif(not os.environ.get("DEEZER_LIVE"),
                    reason="consulta o Deezer real; rode com DEEZER_LIVE=1")
def test_live_deezer_preview_is_trimmed() -> None:  # pragma: no cover - depende da rede
    provider = DeezerProvider("https://api.deezer.com", 15, TTLCache(8, 60))
    track = _track()
    assert provider.check_availability(track) is True
    clip = provider.get_clip(track, 3)
    assert 3 <= clip.duration < 3.1
    assert not clip.data.startswith(b"ID3") and b"Xing" not in clip.data[:200]


def test_trim_mp3_rejects_garbage() -> None:
    with pytest.raises(Mp3FormatError):
        trim_mp3(b"isto nao e mp3" * 100, 1)


def test_wav_roundtrip_and_trim() -> None:
    samples = (np.sin(np.linspace(0, 1000, 22050 * 3)) * 10000).astype(np.int16)
    data = encode_wav(samples, 22050)
    clip, duration = trim_wav(data, 1.5)
    decoded, rate, channels = decode_wav(clip)
    assert rate == 22050 and channels == 1
    assert duration == 1.5 and len(decoded) == 33075
    assert abs(int(decoded[-1])) < 50  # fade-out evita estalo


def test_all_demo_melodies_render() -> None:
    for key in load_songs():
        audio = render_int16(key, "rock", 2)
        assert len(audio) == 2 * 22050
        assert np.abs(audio).max() > 1000  # não está mudo


def _deezer(handler) -> DeezerProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return DeezerProvider("https://api.deezer.test", 5, TTLCache(8, 60), client=client)


def _track(**kwargs) -> MusicTrack:
    base = {"slug": "queen--bohemian-rhapsody", "title": "Bohemian Rhapsody", "artist": "Queen",
            "aliases": [], "edition": "main", "primary_category": "rock"}
    base.update(kwargs)
    return MusicTrack(**base)


def test_deezer_resolves_and_trims_preview() -> None:
    mp3 = fake_mp3(30)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/search":
            return httpx.Response(200, json={"data": [
                {"id": 1, "title": "Bohemian Rhapsody (Live)", "title_short": "Bohemian Rhapsody",
                 "artist": {"name": "Queen Tribute Band"}, "preview": "https://cdn.test/x.mp3"},
                {"id": 7, "title": "Bohemian Rhapsody - Remastered 2011",
                 "title_short": "Bohemian Rhapsody", "link": "https://www.deezer.com/track/7",
                 "artist": {"name": "Queen"}, "preview": "https://cdn.test/7.mp3",
                 "album": {"cover_big": "https://cdn.test/cover.jpg"}},
            ]})
        if request.url.path == "/track/7":
            return httpx.Response(200, json={"id": 7, "preview": "https://cdn.test/7.mp3",
                                             "readable": True})
        if request.url.path == "/7.mp3":
            return httpx.Response(200, content=mp3)
        return httpx.Response(404)

    provider = _deezer(handler)
    track = _track()
    assert provider.check_availability(track) is True
    assert track.external_id == "7"
    assert track.cover_url == "https://cdn.test/cover.jpg"
    clip = provider.get_clip(track, 2)
    assert clip.media_type == "audio/mpeg"
    assert 2 <= clip.duration < 2.1
    assert b"ID3" not in clip.data
    provider.get_clip(track, 5)
    assert calls.count("/7.mp3") == 1  # prévia reaproveitada do cache entre estágios


def _item(id_: int, title_short: str, artist: str, rank: int, version: str = "",
          album: str = "Álbum") -> dict:
    return {"id": id_, "title": f"{title_short} {version}".strip(), "title_short": title_short,
            "title_version": version, "artist": {"name": artist}, "rank": rank,
            "album": {"title": album}, "preview": f"https://cdn.test/{id_}.mp3"}


def _search_provider(results: list[dict], queries: list[str] | None = None) -> DeezerProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        if queries is not None:
            queries.append(request.url.params["q"])
        return httpx.Response(200, json={"data": results})

    return _deezer(handler)


def test_deezer_prefers_studio_recording_over_live_and_covers() -> None:
    # Ordem real da busca "Queen Bohemian Rhapsody" (14/10/2026), com versões ao vivo do
    # próprio Queen e covers. Aqui a ao vivo vem antes e é mais popular que outras.
    results = [
        _item(1, "Bohemian Rhapsody", "Queen", 990_000, "(Live Aid)"),
        _item(2, "Bohemian Rhapsody", "The Karaoke Channel", 999_999, "(Karaoke Version)"),
        _item(3, "Bohemian Rhapsody", "Queen", 958_949, album="A Night At The Opera"),
        _item(4, "Bohemian Rhapsody", "Queen", 100_000, album="Greatest Hits"),
        _item(5, "Bohemian Rhapsody", "Queen", 999_000, album="Live at Wembley Stadium"),
    ]
    queries: list[str] = []
    track = _track()
    assert _search_provider(results, queries).check_availability(track) is True
    assert track.external_id == "3"  # estúdio mais popular
    assert queries == ["Queen Bohemian Rhapsody"]  # busca simples resolve na 1ª tentativa


def test_deezer_accepts_live_version_when_catalog_asks_for_it() -> None:
    results = [
        _item(1, "Evidências", "Chitãozinho & Xororó", 900_000, "(Ao Vivo)"),
        _item(2, "Evidências", "Chitãozinho & Xororó", 500_000),
    ]
    track = _track(title="Evidências", artist="Chitãozinho & Xororó",
                   aliases=["Evidências - Ao Vivo"])
    assert _search_provider(results).check_availability(track) is True
    assert track.external_id == "1"


def test_deezer_falls_back_to_advanced_search() -> None:
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(request.url.params["q"])
        if request.url.params["q"].startswith("artist:"):
            return httpx.Response(200, json={"data": [_item(8, "Bohemian Rhapsody", "Queen", 1)]})
        return httpx.Response(200, json={"data": [_item(9, "Other Song", "Queen", 1)]})

    track = _track()
    assert _deezer(handler).check_availability(track) is True
    assert track.external_id == "8"
    assert queries == ["Queen Bohemian Rhapsody", 'artist:"Queen" track:"Bohemian Rhapsody"']


def test_deezer_finds_collaboration_credited_to_the_other_artist() -> None:
    # Real (14/10/2026): o Deezer credita "Something Just Like This" ao Coldplay; The
    # Chainsmokers só aparece em `contributors` de /track/<id>.
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/search":
            return httpx.Response(200, json={"data": [
                _item(5, "Something Just Like This", "Coldplay", 896_671),
                _item(6, "Something Just Like This", "Coldplay", 422_389, "(Alesso Remix)"),
            ]})
        if request.url.path == "/track/5":
            return httpx.Response(200, json={"id": 5, "contributors": [
                {"name": "Coldplay", "role": "Main"}, {"name": "The Chainsmokers", "role": "Main"},
            ]})
        return httpx.Response(404)

    track = _track(title="Something Just Like This", artist="The Chainsmokers")
    assert _deezer(handler).check_availability(track) is True
    assert track.external_id == "5"
    assert "/track/6" not in calls  # só consulta o candidato de estúdio mais popular


def test_deezer_looks_for_studio_version_in_artist_top_tracks() -> None:
    # Real (14/10/2026): a busca "Oasis Wonderwall" só devolve versões ao vivo do Oasis.
    def live(id_: int, rank: int) -> dict:
        item = _item(id_, "Wonderwall", "Oasis", rank, "(Live at Knebworth, 10 August '96)")
        item["artist"]["id"] = 927
        return item

    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/search":
            return httpx.Response(200, json={"data": [live(1, 470_004), live(2, 421_237)]})
        if request.url.path == "/artist/927/top":
            return httpx.Response(200, json={"data": [
                _item(3, "Wonderwall", "Oasis", 846_066, "(Remastered)",
                      album="(What's The Story) Morning Glory? (Remastered)"),
                live(1, 470_004),
            ]})
        return httpx.Response(404)

    track = _track(title="Wonderwall", artist="Oasis", aliases=["Wonderwall - Remastered"])
    assert _deezer(handler).check_availability(track) is True
    assert track.external_id == "3"
    assert paths == ["/search", "/search", "/artist/927/top"]


def test_deezer_prefers_right_version_credited_to_partner_over_other_remix() -> None:
    # Real (14/10/2026): o sucesso do Spotify é "Friday - Dopamine Re-Edit" (Riton). No
    # Deezer essa versão sai como Nightcrawlers; com o Riton só há outro remix.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(200, json={"data": [
                _item(1, "Friday (feat. Mufasa & Hypeman)", "Nightcrawlers", 828_383,
                      "(Dopamine Re-Edit)"),
                _item(2, "Friday", "Riton", 93_582, "(Violett Sky Remix)"),
            ]})
        if request.url.path == "/track/1":
            return httpx.Response(200, json={"id": 1, "contributors": [
                {"name": "Riton"}, {"name": "Nightcrawlers"}, {"name": "Mufasa & Hypeman"},
            ]})
        return httpx.Response(200, json={"data": []})

    track = _track(title="Friday", artist="Riton", aliases=["Friday - Dopamine Re-Edit"])
    assert _deezer(handler).check_availability(track) is True
    assert track.external_id == "1"


def test_deezer_live_and_ao_vivo_are_the_same_version() -> None:
    results = [
        _item(1, "Liberdade Provisória", "Henrique & Juliano", 900_000,
              "(Live - Ibirapuera / 2019)", album="Ao Vivo No Ibirapuera, Vol. 1"),
        _item(2, "Liberdade Provisória", "Henrique & Juliano", 100_000, "(Acústico)"),
    ]
    track = _track(title="Liberdade Provisória", artist="Henrique & Juliano",
                   aliases=["Liberdade Provisória (Live - Ibirapuera / 2019)"])
    assert _search_provider(results).check_availability(track) is True
    assert track.external_id == "1"


def test_deezer_artist_names_ignore_spaces() -> None:
    results = [_item(1, "Seven (feat. Latto)", "Jungkook", 771_507)]
    track = _track(title="Seven", artist="Jung Kook")
    assert _search_provider(results).check_availability(track) is True


def test_deezer_rejects_covers_by_other_artists() -> None:
    results = [_item(1, "Bohemian Rhapsody", "Lucia Micarelli", 5),
               _item(2, "Bohemian Rhapsody", "The Backing Track Collective", 5, "(Instrumental)")]
    track = _track()
    assert _search_provider(results).check_availability(track) is False


def test_deezer_marks_missing_preview_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [
            {"id": 9, "title": "Bohemian Rhapsody", "artist": {"name": "Queen"}, "preview": ""}
        ]})

    track = _track()
    assert _deezer(handler).check_availability(track) is False
    assert track.availability == "unavailable"


@pytest.mark.parametrize("response", [
    httpx.Response(500),
    httpx.Response(200, json={"error": {"type": "Exception", "message": "Quota", "code": 4}}),
    httpx.Response(200, content=b"not json"),
])
def test_deezer_errors_become_audio_unavailable(response: httpx.Response) -> None:
    provider = _deezer(lambda request: response)
    track = _track(external_provider="deezer", external_id="7")
    with pytest.raises(AudioUnavailableError):
        provider.get_clip(track, 1)
    assert track.availability != "unavailable"  # falha temporária não condena a faixa


def test_deezer_network_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    with pytest.raises(AudioUnavailableError):
        _deezer(handler).check_availability(_track())


def test_local_provider_reads_files_and_blocks_traversal(tmp_path) -> None:
    (tmp_path / "queen--bohemian-rhapsody.mp3").write_bytes(fake_mp3(10))
    provider = LocalFileProvider(str(tmp_path))
    track = _track()
    assert provider.check_availability(track)
    assert 1 <= provider.get_clip(track, 1).duration < 1.1
    evil = _track(audio_ref="../../etc/passwd")
    assert provider.check_availability(evil) is False
    with pytest.raises(AudioUnavailableError):
        provider.get_clip(evil, 1)


def test_audio_failure_returns_503_and_keeps_attempts(main_harness: Harness,
                                                      fake_provider: FakeProvider) -> None:
    headers = main_harness.new_player()
    game = main_harness.start(headers)
    fake_provider.fail_clips = True
    response = main_harness.client.get(f"/api/games/{game['id']}/audio?stage=1",
                                       headers=headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "audio_unavailable"
    state = main_harness.client.get(f"/api/games/{game['id']}", headers=headers).json()
    assert state["attempts_used"] == 0 and state["status"] == "in_progress"
    fake_provider.fail_clips = False
    ok = main_harness.client.get(f"/api/games/{game['id']}/audio?stage=1", headers=headers)
    assert ok.status_code == 200
    assert fake_provider.clip_requests == [1.0]


def test_ttl_cache_evicts_oldest() -> None:
    cache = TTLCache(2, 60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None and cache.get("c") == 3
    assert json.dumps(cache.get("b")) == "2"
