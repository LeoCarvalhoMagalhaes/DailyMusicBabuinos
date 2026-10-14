"""Importador do kworb, testado com páginas simuladas a partir de trechos reais do site.

O formato foi conferido em 14/10/2026 (dados do kworb de 13/10/2026):
- songs.html: "<div>Artista - Título</div>" em texto, sem links;
- artists.html: link "/spotify/artist/<id>_songs.html" com o nome;
- artist/<id>_songs.html: tabela-resumo (Streams/Daily/Tracks) e depois a lista, com link
  "https://open.spotify.com/track/<id>" e "* " antes das participações.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.catalog_import.kworb import (
    ARTISTS_URL,
    GLOBAL_SONGS_URL,
    KWORB_BASE,
    KworbClient,
    KworbFormatError,
    KworbSong,
    clean_title,
    import_kworb,
    parse_artist_rows,
    parse_song_rows,
    resolve_artist,
    select_tracks,
)
from app.services.catalog import load_catalog_files, sync_catalog
from tests.conftest import Harness


def sid(n: int) -> str:
    """Id de faixa/artista no formato do Spotify (22 caracteres base62)."""
    return f"{n:022d}"


def table(rows: list[str], header: str) -> str:
    return (
        "<html><body><table class=\"addpos sortable\"><thead><tr>" + header +
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></body></html>"
    )


def global_row(artist: str, title: str, streams: int) -> str:
    # Linha real: <tr><td class="text"><div>The Weeknd - Blinding Lights</div></td>
    # <td>5,632,731,972</td><td>1,455,905</td></tr>
    return (
        f'<tr><td class="text"><div>{artist} - {title}</div></td>'
        f"<td>{streams:,}</td><td>1,455,905</td></tr>"
    )


def artist_row(name: str, artist_id: str, streams_millions: str) -> str:
    return (
        f'<tr>\n<td class="text"><div><a href="/spotify/artist/{artist_id}_songs.html">{name}'
        f"</a></div></td>\n<td>{streams_millions}</td>\n<td>57.688</td>\n"
        '<td class="smaller">98,510.0</td>\n<td class="smaller">55,617.6</td>\n'
        '<td class="smaller">44,282.3</td></tr>\n'
    )


def artist_song_row(title: str, track_id: str, streams: int, feature: bool = False) -> str:
    star = "* " if feature else ""
    return (
        f'<tr><td class="text"><div>{star}<a href="https://open.spotify.com/track/{track_id}" '
        f'target="_blank">{title}</a></div></td><td>{streams:,}</td><td>980,555</td></tr>'
    )


# Tabela-resumo que abre a página de cada artista (deve ser ignorada).
ARTIST_SUMMARY = (
    '<table style="width: 580px;"><thead><tr><th class="text"></th><th>Total</th>'
    "<th>As lead</th><th>Solo</th><th>As feature (*)</th></tr></thead><tbody>"
    '<tr><td class="text">Streams</td><td>30,065,864,559</td><td class="smaller">'
    '29,980,888,398</td><td class="smaller">27,541,171,826</td><td class="smaller">'
    "84,976,161</td></tr>"
    '<tr><td class="text">Tracks</td><td>635</td><td class="smaller">631</td>'
    '<td class="smaller">559</td><td class="smaller">4</td></tr></tbody></table>'
)

GLOBAL_HTML = table(
    [
        global_row("The Weeknd", "Blinding Lights", 5_632_731_972),
        global_row("Ed Sheeran", "Shape of You", 5_140_610_305),
        global_row("The Weeknd", "Starboy", 4_808_854_299),
        global_row("The Weeknd", "Save Your Tears", 3_800_000_000),
        global_row("The Weeknd", "The Hills", 3_000_000_000),  # 4ª do artista: pula
        global_row("Queen", "Bohemian Rhapsody - Remastered 2011", 2_900_000_000),
        global_row("Ed Sheeran", "Shape of You", 1_000_000_000),  # repetida
    ],
    '<th class="text">Artist and Title</th>\n<th>Streams</th>\n<th>Daily</th>\n',
)

ARTISTS_HTML = table(
    [
        artist_row("Queen", sid(3), "30,065.9"),
        artist_row("Nirvana", sid(4), "10,000.0"),
        artist_row("Chitãozinho &amp; Xororó", sid(5), "3,000.0"),
    ],
    '<th class="text">Artist</th>\n<th>Streams</th>\n<th>Daily</th>\n<th>As lead</th>\n'
    "<th>Solo</th>\n<th>As feature</th>\n",
)

QUEEN_HTML = ARTIST_SUMMARY + table(
    [
        artist_song_row("Bohemian Rhapsody - Remastered 2011", sid(201), 2_900_000_000),
        artist_song_row("Don't Stop Me Now - Remastered 2011", sid(202), 2_000_000_000),
        artist_song_row("Under Pressure - Remastered 2011", sid(203), 1_500_000_000),
        artist_song_row("Another One Bites The Dust - Remastered 2011", sid(204), 1_400_000_000),
        artist_song_row("Some Feature (feat. Queen)", sid(205), 9_000_000_000, feature=True),
    ],
    "<th>Song Title</th><th>Streams</th><th>Daily</th>",
)

NIRVANA_HTML = ARTIST_SUMMARY + table(
    [
        artist_song_row("Smells Like Teen Spirit", sid(301), 2_100_000_000),
        artist_song_row("Come As You Are", sid(302), 1_200_000_000),
    ],
    "<th>Song Title</th><th>Streams</th><th>Daily</th>",
)

PAGES = {
    GLOBAL_SONGS_URL: GLOBAL_HTML,
    ARTISTS_URL: ARTISTS_HTML,
    f"{KWORB_BASE}/artist/{sid(3)}_songs.html": QUEEN_HTML,
    f"{KWORB_BASE}/artist/{sid(4)}_songs.html": NIRVANA_HTML,
}


def make_client(pages: dict[str, str] = PAGES, cache: Path | None = None,
                calls: list[str] | None = None, sleeps: list[float] | None = None
                ) -> KworbClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        body = pages.get(str(request.url))
        return httpx.Response(200, text=body) if body else httpx.Response(404)

    return KworbClient(
        cache_dir=cache, delay_seconds=2.0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=(sleeps.append if sleeps is not None else lambda _: None),
        log=lambda _: None,
    )


def test_parse_global_songs_list() -> None:
    songs = parse_song_rows(GLOBAL_HTML)
    # A lista global não tem link da faixa: o id do Spotify fica vazio.
    assert songs[0] == KworbSong("Blinding Lights", "The Weeknd", None, 5_632_731_972)
    assert songs[5].title == "Bohemian Rhapsody - Remastered 2011"
    assert songs[5].artist == "Queen"
    assert len(songs) == 7


def test_parse_global_row_with_dash_in_title() -> None:
    html = table([global_row("Post Malone", "Sunflower - Spider-Man: Into the Spider-Verse",
                             4_510_725_961)], "<th>Artist and Title</th>")
    song = parse_song_rows(html)[0]
    assert (song.artist, song.title) == ("Post Malone",
                                         "Sunflower - Spider-Man: Into the Spider-Verse")


def test_artist_page_summary_table_is_ignored() -> None:
    songs = parse_song_rows(NIRVANA_HTML, default_artist="Nirvana")
    assert [s.title for s in songs] == ["Smells Like Teen Spirit", "Come As You Are"]


def test_parse_artist_page_marks_features() -> None:
    songs = parse_song_rows(QUEEN_HTML, default_artist="Queen")
    assert [s.feature for s in songs] == [False, False, False, False, True]
    assert songs[0].artist == "Queen" and songs[0].spotify_id == sid(201)


def test_parse_artists_and_resolve_names() -> None:
    artists = {a.name.casefold(): a for a in parse_artist_rows(ARTISTS_HTML)}
    assert artists["chitãozinho & xororó"].artist_id == sid(5)
    from app.services.answers import normalize

    index = {normalize(a.name): a for a in artists.values()}
    assert resolve_artist("queen", index).artist_id == sid(3)
    assert resolve_artist("Chitãozinho & Xororó", index).artist_id == sid(5)
    assert resolve_artist("Nirvana & Amigos", index).artist_id == sid(4)  # tenta as partes
    assert resolve_artist("Desconhecido", index) is None
    assert artists["queen"].artist_id == sid(3)
    manual = resolve_artist(f"Racionais MC's|{sid(9)}", index)
    assert manual.name == "Racionais MC's" and manual.artist_id == sid(9)


def test_unexpected_layout_raises_clear_error() -> None:
    with pytest.raises(KworbFormatError):
        parse_song_rows("<html><p>Página nova sem tabela</p></html>")
    with pytest.raises(KworbFormatError):
        parse_artist_rows("<table><tr><td>sem links</td></tr></table>")


@pytest.mark.parametrize(("raw", "title"), [
    ("Bohemian Rhapsody - Remastered 2011", "Bohemian Rhapsody"),
    ("Hotel California - 2013 Remaster", "Hotel California"),
    ("Despacito (feat. Daddy Yankee)", "Despacito"),
    ("Stay (with Justin Bieber)", "Stay"),
    ("(I Can't Get No) Satisfaction - Mono Version", "(I Can't Get No) Satisfaction"),
    ("Evidências - Ao Vivo", "Evidências"),
    ("Blinding Lights", "Blinding Lights"),
])
def test_clean_title(raw: str, title: str) -> None:
    cleaned, aliases = clean_title(raw)
    assert cleaned == title
    assert aliases == ([] if raw == title else [raw])


def test_select_tracks_limits_artist_and_duplicates() -> None:
    songs = parse_song_rows(GLOBAL_HTML)
    picked = select_tracks(songs, limit=10, max_per_artist=3, keep_order_rank=True)
    assert [t.title for t in picked] == [
        "Blinding Lights", "Shape of You", "Starboy", "Save Your Tears", "Bohemian Rhapsody"
    ]
    # A posição continua sendo a do kworb (a 5ª da lista foi pulada).
    assert [t.rank for t in picked] == [1, 2, 3, 4, 6]
    assert picked[-1].aliases == ["Bohemian Rhapsody - Remastered 2011"]


def test_import_writes_chart_catalog_files(tmp_path: Path) -> None:
    calls: list[str] = []
    sleeps: list[float] = []
    seeds = {"rock": ["Queen", "Nirvana", "Banda Que Não Existe"]}
    results = import_kworb(make_client(calls=calls, sleeps=sleeps), tmp_path, seeds,
                           ["geral", "rock"], retrieved_on=date(2026, 10, 14), limit=5,
                           max_per_artist=3, allow_partial=True, log=lambda _: None)
    rock = next(r for r in results if r.category == "rock")
    assert rock.unresolved_artists == ["Banda Que Não Existe"]
    assert [t.title for t in rock.tracks] == [
        "Bohemian Rhapsody", "Smells Like Teen Spirit", "Don't Stop Me Now",
        "Under Pressure", "Come As You Are",
    ]  # ordem por streams, participação excluída, no máximo 3 do Queen
    assert [t.rank for t in rock.tracks] == [1, 2, 3, 4, 5]
    assert len(sleeps) == len(calls) - 1  # intervalo entre requisições

    data = json.loads((tmp_path / "rock.json").read_text(encoding="utf-8"))
    assert data["source"]["kind"] == "chart"
    assert data["source"]["retrieved_on"] == "2026-10-14"
    assert "kworb" in data["source"]["methodology"]
    first = data["tracks"][0]
    assert first == {
        "title": "Bohemian Rhapsody", "artist": "Queen", "rank": 1, "spotify_id": sid(201),
        "streams": 2_900_000_000, "genres": ["rock"],
        "aliases": ["Bohemian Rhapsody - Remastered 2011"],
    }
    # Os arquivos gerados são aceitos pelo carregador do catálogo (posições só em "chart").
    bundle = load_catalog_files((tmp_path,))
    spec = bundle.tracks["queen--bohemian-rhapsody"]
    assert spec.categories == {"rock": 1, "geral": 6}  # posição em cada lista
    assert spec.spotify_id == sid(201)

    # Geral: sem link no kworb; o id vem das páginas de artista já baixadas, quando existe.
    geral = json.loads((tmp_path / "geral.json").read_text(encoding="utf-8"))["tracks"]
    by_title = {t["title"]: t for t in geral}
    assert by_title["Bohemian Rhapsody"]["spotify_id"] == sid(201)
    assert "spotify_id" not in by_title["Blinding Lights"]


def test_import_warns_about_partial_name_matches(tmp_path: Path) -> None:
    logs: list[str] = []
    results = import_kworb(make_client(), tmp_path, {"rock": ["Nirvana & Amigos"]}, ["rock"],
                           retrieved_on=date(2026, 10, 14), limit=2, allow_partial=True,
                           log=logs.append)
    assert results[0].partial_matches == ["Nirvana & Amigos -> Nirvana"]
    assert any("Nirvana & Amigos -> Nirvana" in line for line in logs)


def test_track_without_spotify_id_links_to_spotify_search() -> None:
    from app.models import MusicTrack
    from app.services.game import spotify_link

    main = MusicTrack(title="Blinding Lights", artist="The Weeknd", edition="main")
    assert spotify_link(main) == "https://open.spotify.com/search/Blinding%20Lights%20The%20Weeknd"
    main.spotify_id = sid(101)
    assert spotify_link(main) == f"https://open.spotify.com/track/{sid(101)}"
    assert spotify_link(MusicTrack(title="Greensleeves", artist="Tradicional",
                                   edition="demo")) is None


def test_import_refuses_incomplete_categories(tmp_path: Path) -> None:
    with pytest.raises(KworbFormatError, match="menos de 100"):
        import_kworb(make_client(), tmp_path, {"rock": ["Queen"]}, ["rock"],
                     retrieved_on=date(2026, 10, 14), log=lambda _: None)
    assert not (tmp_path / "rock.json").exists()  # nada gravado pela metade


def test_cache_avoids_refetching(tmp_path: Path) -> None:
    calls: list[str] = []
    cache = tmp_path / "cache"
    make_client(cache=cache, calls=calls).get(GLOBAL_SONGS_URL)
    make_client(cache=cache, calls=calls).get(GLOBAL_SONGS_URL)
    assert calls == [GLOBAL_SONGS_URL]


def test_http_error_is_reported() -> None:
    with pytest.raises(KworbFormatError, match="HTTP 404"):
        make_client(pages={}).get(GLOBAL_SONGS_URL)


def test_imported_catalog_links_to_spotify_after_the_game(main_harness: Harness,
                                                          tmp_path: Path) -> None:
    import_kworb(make_client(), tmp_path, {"rock": ["Queen", "Nirvana"]}, ["rock"],
                 retrieved_on=date(2026, 10, 14), limit=5, allow_partial=True,
                 log=lambda _: None)
    with main_harness.app.state.session_factory() as db:
        sync_catalog(db, load_catalog_files((tmp_path,)))
    headers = main_harness.new_player()
    game = main_harness.start(headers, "rock")
    assert "spotify" not in json.dumps(game)  # nada vaza durante a partida
    secret = main_harness.secret("rock")
    body = main_harness.guess(headers, game, secret.title).json()
    assert body["game"]["answer"]["spotify_url"] == (
        f"https://open.spotify.com/track/{secret.spotify_id}"
    )
