"""Importação do catálogo a partir das estatísticas do Spotify publicadas pelo kworb.net.

O kworb (https://kworb.net/spotify/) publica contagens de streams do Spotify por música
e por artista. Ele não tem API: este módulo lê as páginas públicas com educação (uma
requisição por vez, intervalo configurável, cache local e User-Agent identificado) e gera
os arquivos JSON do catálogo com fonte do tipo "chart", posição, data da consulta e o id
da faixa no Spotify.

Metodologia:
- Geral: as músicas mais tocadas de todos os tempos no Spotify (lista global do kworb), na
  ordem do kworb; posição = posição no kworb. Essa página traz só "Artista - Título" em
  texto (sem link da faixa); o id do Spotify é completado com as páginas de artista
  baixadas para os gêneros, quando a música aparece nelas.
- Gêneros: o kworb não classifica por gênero. Cada categoria tem uma lista editorial de
  artistas do gênero (app/data/kworb_seeds.json). Juntamos as músicas desses artistas
  (como artista principal), ordenamos pelo total de streams no Spotify e ficamos com as 100
  primeiras; posição = posição nesse ranking.
- Em todas as listas: no máximo N músicas por artista e sem títulos repetidos.

Apenas títulos, artistas, ids e números de streams são usados; nenhum áudio vem do Spotify.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import httpx

from app.services.answers import normalize

KWORB_BASE = "https://kworb.net/spotify"
GLOBAL_SONGS_URL = f"{KWORB_BASE}/songs.html"
ARTISTS_URL = f"{KWORB_BASE}/artists.html"
USER_AGENT = "MusicasBabuinas-catalog-import/1.0 (importacao manual, baixa frequencia)"

TRACK_ID_RE = re.compile(r"track/([0-9A-Za-z]{22})")
ARTIST_ID_RE = re.compile(r"artist/([0-9A-Za-z]{22})")
NUMBER_RE = re.compile(r"^[\d.,\s]+$")

CATEGORY_NAMES = {
    "rock": "Rock", "pop": "Pop", "rap": "Rap", "country": "Country",
    "eletronica": "Eletrônica", "geral": "Geral",
}


class KworbFormatError(RuntimeError):
    """A página não tem o formato esperado (o kworb pode ter mudado o layout)."""


# --------------------------------------------------------------------------
# Leitura das tabelas HTML (somente biblioteca padrão)
# --------------------------------------------------------------------------

@dataclass
class Cell:
    text: str = ""
    links: list[tuple[str, str]] = field(default_factory=list)  # (href, texto)


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[Cell]] = []
        self._row: list[Cell] | None = None
        self._cell: Cell | None = None
        self._href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = Cell()
        elif tag == "a" and self._cell is not None:
            self._href = dict(attrs).get("href") or ""
            self._link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._cell is not None and self._href is not None:
            self._cell.links.append((self._href, "".join(self._link_text).strip()))
            self._href = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._cell.text = " ".join(self._cell.text.split())
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.text += data
            if self._href is not None:
                self._link_text.append(data)


def parse_rows(html: str) -> list[list[Cell]]:
    parser = _TableParser()
    parser.feed(html)
    return parser.rows


def _to_int(text: str) -> int | None:
    text = text.strip()
    if not text or not NUMBER_RE.match(text):
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


@dataclass(frozen=True)
class KworbSong:
    title: str
    artist: str
    spotify_id: str | None
    streams: int
    feature: bool = False


@dataclass(frozen=True)
class KworbArtist:
    name: str
    artist_id: str


def parse_song_rows(html: str, default_artist: str | None = None) -> list[KworbSong]:
    """Linhas com a música e o total de streams (primeira coluna numérica depois dela).

    Serve para a página de músicas de um artista (link da faixa no Spotify; participações
    marcadas com "*") e para a lista global, que traz só o texto "Artista - Título", sem
    link (formato conferido em 14/10/2026); nesse caso `spotify_id` fica vazio."""
    songs: list[KworbSong] = []
    for row in parse_rows(html):
        for index, cell in enumerate(row):
            streams = next(
                (n for c in row[index + 1:] if (n := _to_int(c.text)) is not None), None
            )
            track_links = [(h, t) for h, t in cell.links if TRACK_ID_RE.search(h)]
            spotify_id: str | None
            if track_links:
                href, title = track_links[0]
                spotify_id = TRACK_ID_RE.search(href).group(1)  # type: ignore[union-attr]
                artist_links = [t for h, t in cell.links if ARTIST_ID_RE.search(h) and t]
                artist = artist_links[0] if artist_links else default_artist
                if not artist and " - " in cell.text:
                    artist = cell.text.split(" - ", 1)[0].strip()
            elif default_artist is None and " - " in cell.text and streams is not None:
                artist, title = (part.strip() for part in cell.text.split(" - ", 1))
                spotify_id = None
            else:
                continue
            if artist and title and streams is not None:
                songs.append(KworbSong(title=title, artist=artist, spotify_id=spotify_id,
                                       streams=streams,
                                       feature=cell.text.lstrip().startswith("*")))
            break
    if not songs:
        raise KworbFormatError("Nenhuma música encontrada na página do kworb.")
    return songs


def parse_artist_rows(html: str) -> list[KworbArtist]:
    artists: list[KworbArtist] = []
    seen: set[str] = set()
    for row in parse_rows(html):
        for cell in row:
            for href, text in cell.links:
                match = ARTIST_ID_RE.search(href)
                if match and text and match.group(1) not in seen:
                    seen.add(match.group(1))
                    artists.append(KworbArtist(text, match.group(1)))
    if not artists:
        raise KworbFormatError("Nenhum artista encontrado na página do kworb.")
    return artists


# --------------------------------------------------------------------------
# Limpeza de títulos
# --------------------------------------------------------------------------

_FEAT_PARENS = re.compile(r"\s*[\(\[](?:feat\.?|ft\.?|with|com|part\.?)\s[^\)\]]*[\)\]]", re.I)
# No Spotify, " - " sempre introduz versão ou contexto ("- Remastered 2011", "- PNAU Remix",
# "- Spider-Man: Into the Spider-Verse", "- feat. ..."): tudo depois dele sai do título.
_VERSION_SUFFIX = re.compile(r"\s+-\s+.*$")
_VERSION_PARENS = re.compile(
    r"\s*[\(\[][^\)\]]*\b(?:remaster(?:ed)?|live|ao vivo|radio edit|single version|mono|"
    r"stereo|remix|re-edit|edit|mix|rework|version|versão)\b[^\)\]]*[\)\]]"
    r"|\s*[\(\[]from\s[^\)\]]*[\)\]]",
    re.I,
)


def clean_title(raw: str) -> tuple[str, list[str]]:
    """Título para exibir e aliases (o título original, se mudou). Revisado com os
    dados reais de 14/10/2026."""
    # Parênteses primeiro: "(Live - Ibirapuera / 2019)" tem " - " lá dentro.
    title = _VERSION_PARENS.sub("", raw)
    title = _VERSION_SUFFIX.sub("", title)
    title = _FEAT_PARENS.sub("", title)
    title = " ".join(title.split()).strip(" -")
    title = title or raw.strip()
    aliases = [raw.strip()] if title != raw.strip() else []
    return title, aliases


# --------------------------------------------------------------------------
# Cliente HTTP educado, com cache
# --------------------------------------------------------------------------

class KworbClient:
    def __init__(self, cache_dir: Path | None = None, delay_seconds: float = 2.0,
                 client: httpx.Client | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 log: Callable[[str], None] = print) -> None:
        self.cache_dir = cache_dir
        self.delay = delay_seconds
        self.client = client or httpx.Client(timeout=30, follow_redirects=True,
                                             headers={"User-Agent": USER_AGENT})
        self.sleep = sleep
        self.log = log
        self._last_request = 0.0
        self.requests = 0

    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".html")

    def get(self, url: str) -> str:
        cached = self._cache_path(url)
        if cached and cached.exists():
            return cached.read_text(encoding="utf-8")
        wait = self.delay - (time.monotonic() - self._last_request)
        if self.requests and wait > 0:
            self.sleep(wait)
        self.log(f"  GET {url}")
        response = self.client.get(url)
        self._last_request = time.monotonic()
        self.requests += 1
        if response.status_code != 200:
            raise KworbFormatError(f"{url} respondeu HTTP {response.status_code}")
        response.encoding = response.encoding or "utf-8"
        text = response.text
        if cached:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(text, encoding="utf-8")
        return text


# --------------------------------------------------------------------------
# Montagem das listas
# --------------------------------------------------------------------------

@dataclass
class ImportedTrack:
    title: str
    artist: str
    spotify_id: str | None
    streams: int
    rank: int
    aliases: list[str]

    def to_json(self, category: str) -> dict:
        data: dict = {"title": self.title, "artist": self.artist, "rank": self.rank}
        if self.spotify_id:
            data["spotify_id"] = self.spotify_id
        data |= {"streams": self.streams, "genres": [CATEGORY_NAMES[category].lower()]}
        if self.aliases:
            data["aliases"] = self.aliases
        return data


def select_tracks(songs: Iterable[KworbSong], limit: int, max_per_artist: int,
                  keep_order_rank: bool, exclude_artists: frozenset[str] = frozenset(),
                  ) -> list[ImportedTrack]:
    """Filtra repetições e excesso por artista. `keep_order_rank` preserva a posição
    original (lista global); senão a posição é a ordem final do ranking."""
    per_artist: dict[str, int] = {}
    seen_titles: set[str] = set()
    seen_ids: set[str] = set()
    selected: list[ImportedTrack] = []
    for position, song in enumerate(songs, start=1):
        title, aliases = clean_title(song.title)
        key = normalize(title)
        artist_key = normalize(song.artist)
        if not key or key in seen_titles or (song.spotify_id and song.spotify_id in seen_ids):
            continue
        if artist_key in exclude_artists:
            continue  # ex.: faixas de ruído branco na lista global (não são música)
        if per_artist.get(artist_key, 0) >= max_per_artist:
            continue
        per_artist[artist_key] = per_artist.get(artist_key, 0) + 1
        seen_titles.add(key)
        if song.spotify_id:
            seen_ids.add(song.spotify_id)
        rank = position if keep_order_rank else len(selected) + 1
        selected.append(ImportedTrack(title, song.artist, song.spotify_id, song.streams, rank,
                                      aliases))
        if len(selected) >= limit:
            break
    return selected


def resolve_artist(name: str, index: dict[str, KworbArtist]) -> KworbArtist | None:
    """Acha o artista pelo nome; aceita "Nome|idDoSpotify" para fixar o id manualmente."""
    if "|" in name:
        label, artist_id = (part.strip() for part in name.split("|", 1))
        return KworbArtist(label, artist_id)
    found = index.get(normalize(name))
    if found:
        return found
    for part in re.split(r"\s+(?:&|e|and|x|feat\.?)\s+|,\s*", name):
        found = index.get(normalize(part))
        if found:
            return found
    return None


@dataclass
class CategoryResult:
    category: str
    tracks: list[ImportedTrack]
    source_url: str
    unresolved_artists: list[str] = field(default_factory=list)
    failed_artists: list[str] = field(default_factory=list)
    # Seeds achados só por parte do nome (ex.: "A & B" -> "A"): confira se é o artista certo.
    partial_matches: list[str] = field(default_factory=list)
    # Todas as músicas lidas nas páginas de artista (para completar ids da Geral).
    pool: list[KworbSong] = field(default_factory=list)


def build_general(client: KworbClient, url: str, limit: int, max_per_artist: int,
                  exclude_artists: frozenset[str] = frozenset()) -> CategoryResult:
    songs = parse_song_rows(client.get(url))
    tracks = select_tracks(songs, limit, max_per_artist, keep_order_rank=True,
                           exclude_artists=exclude_artists)
    return CategoryResult("geral", tracks, url)


def build_genre(client: KworbClient, category: str, seeds: list[str],
                artist_index: dict[str, KworbArtist], limit: int, max_per_artist: int,
                exclude_artists: frozenset[str] = frozenset()) -> CategoryResult:
    unresolved: list[str] = []
    failed: list[str] = []
    partial: list[str] = []
    pool: list[KworbSong] = []
    for seed in seeds:
        artist = resolve_artist(seed, artist_index)
        if artist is None:
            unresolved.append(seed)
            continue
        if "|" not in seed and normalize(artist.name) != normalize(seed):
            partial.append(f"{seed} -> {artist.name}")
        url = f"{KWORB_BASE}/artist/{artist.artist_id}_songs.html"
        try:
            songs = parse_song_rows(client.get(url), default_artist=artist.name)
        except (KworbFormatError, httpx.HTTPError):
            failed.append(seed)
            continue
        # Só músicas em que o artista é o principal; participações ficam de fora.
        pool.extend(KworbSong(s.title, artist.name, s.spotify_id, s.streams)
                    for s in songs if not s.feature)
    pool.sort(key=lambda s: s.streams, reverse=True)
    tracks = select_tracks(pool, limit, max_per_artist, keep_order_rank=False,
                           exclude_artists=exclude_artists)
    return CategoryResult(category, tracks, f"{KWORB_BASE}/artist/", unresolved, failed,
                          partial, pool)


def fill_spotify_ids(result: CategoryResult, songs: Iterable[KworbSong]) -> int:
    """Completa o id do Spotify das faixas sem link (lista global) com as músicas lidas
    nas páginas de artista: mesmo artista e mesmo título limpo. Devolve quantas achou."""
    known: dict[tuple[str, str], str] = {}
    for song in songs:
        if song.spotify_id:
            key = (normalize(song.artist), normalize(clean_title(song.title)[0]))
            known.setdefault(key, song.spotify_id)
    filled = 0
    for track in result.tracks:
        if not track.spotify_id:
            track.spotify_id = known.get((normalize(track.artist), normalize(track.title)))
            filled += track.spotify_id is not None
    return filled


def methodology(category: str, source_url: str, max_per_artist: int) -> str:
    if category == "geral":
        return (
            "Músicas mais tocadas de todos os tempos no Spotify, segundo a lista de streams "
            f"acumulados do kworb.net ({source_url}). A posição é a do kworb; foram puladas "
            f"faixas além de {max_per_artist} por artista e títulos repetidos. Dados de "
            "terceiros (kworb), não oficiais do Spotify."
        )
    return (
        f"Ranking da categoria {CATEGORY_NAMES[category]} por total de streams no Spotify, "
        "calculado com os dados públicos do kworb.net (páginas de músicas de cada artista). "
        "O kworb não classifica gêneros: os artistas de cada categoria vêm de uma lista "
        "editorial (app/data/kworb_seeds.json). Entram só músicas em que o artista é o "
        f"principal, no máximo {max_per_artist} por artista, sem títulos repetidos. A posição "
        "é a ordem por streams nesse recorte; não é uma parada oficial do Spotify."
    )


def write_category(out_dir: Path, result: CategoryResult, retrieved_on: date,
                   max_per_artist: int) -> Path:
    data = {
        "edition": "main",
        "category": result.category,
        "source": {
            "id": f"kworb-spotify-{result.category}-{retrieved_on.isoformat()}",
            "name": f"Spotify via kworb.net — {CATEGORY_NAMES[result.category]}",
            "kind": "chart",
            "url": result.source_url,
            "retrieved_on": retrieved_on.isoformat(),
            "methodology": methodology(result.category, result.source_url, max_per_artist),
        },
    }
    header = json.dumps(data, ensure_ascii=False, indent=2)
    body = ",\n".join(
        "    " + json.dumps(t.to_json(result.category), ensure_ascii=False)
        for t in result.tracks
    )
    text = header[:-2] + ',\n  "tracks": [\n' + body + "\n  ]\n}\n"
    json.loads(text)
    path = out_dir / f"{result.category}.json"
    path.write_text(text, encoding="utf-8")
    return path


def load_seeds(path: Path) -> dict[str, list[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def import_kworb(client: KworbClient, out_dir: Path, seeds: dict[str, list[str]],
                 categories: Iterable[str], retrieved_on: date, limit: int = 100,
                 max_per_artist: int = 3, general_url: str = GLOBAL_SONGS_URL,
                 allow_partial: bool = False, log: Callable[[str], None] = print,
                 ) -> list[CategoryResult]:
    """Gera os JSON das categorias pedidas. Só grava se todas tiverem `limit` faixas
    (a menos que `allow_partial`), para nunca deixar o catálogo pela metade."""
    categories = list(categories)
    results: list[CategoryResult] = []
    artist_index: dict[str, KworbArtist] | None = None
    # "excluir" no arquivo de seeds: artistas que nunca entram (ex.: faixas de ruído branco).
    exclude = frozenset(normalize(name) for name in seeds.get("excluir", []))
    for category in categories:
        log(f"[{category}]")
        if category == "geral":
            result = build_general(client, general_url, limit, max_per_artist, exclude)
        else:
            if artist_index is None:
                artist_index = {normalize(a.name): a for a in parse_artist_rows(
                    client.get(ARTISTS_URL))}
            result = build_genre(client, category, seeds.get(category, []), artist_index,
                                 limit, max_per_artist, exclude)
        log(f"  {len(result.tracks)} faixas"
            + (f"; artistas não encontrados: {', '.join(result.unresolved_artists)}"
               if result.unresolved_artists else ""))
        if result.partial_matches:
            log(f"  confira (achados por parte do nome): {', '.join(result.partial_matches)}")
        if result.failed_artists:
            log(f"  páginas que falharam: {', '.join(result.failed_artists)}")
        results.append(result)
    pool = [song for r in results for song in r.pool]
    for result in results:
        missing = sum(1 for t in result.tracks if not t.spotify_id)
        if missing:
            filled = fill_spotify_ids(result, pool)
            log(f"[{result.category}] id do Spotify completado em {filled} de {missing} "
                "faixas sem link")
    short = [r for r in results if len(r.tracks) < limit]
    if short and not allow_partial:
        detail = ", ".join(f"{r.category} ({len(r.tracks)})" for r in short)
        raise KworbFormatError(
            f"Categorias com menos de {limit} faixas: {detail}. Acrescente artistas em "
            "kworb_seeds.json (formato 'Nome' ou 'Nome|idDoArtistaNoSpotify') ou use "
            "--allow-partial."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        path = write_category(out_dir, result, retrieved_on, max_per_artist)
        log(f"  gravado {path}")
    return results
