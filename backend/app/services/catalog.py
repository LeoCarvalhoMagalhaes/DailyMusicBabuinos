"""Catálogo musical: sincronização dos arquivos JSON com o banco e busca de títulos.

Os arquivos em `app/data/catalog` (catálogo real) e `app/data/demo` (modo
demonstração) são a fonte editorial. Atualizar o catálogo = editar/adicionar JSON e
reiniciar (ou rodar `python -m app.cli sync-catalog`); o jogo não precisa mudar.
"""

from __future__ import annotations

import json
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.categories import CATEGORY_SLUGS
from app.models import CatalogEntry, CatalogSource, MusicTrack
from app.services.answers import normalize

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOG_DIRS = (DATA_DIR / "catalog", DATA_DIR / "demo")

# Arquivos específicos de gênero vêm antes de "geral" para definir a categoria principal.
_FILE_ORDER = {slug: i for i, slug in enumerate(CATEGORY_SLUGS)}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def track_slug(artist: str, title: str) -> str:
    return f"{slugify(artist)}--{slugify(title)}"[:160]


@dataclass
class CatalogTrackSpec:
    slug: str
    edition: str
    title: str
    artist: str
    categories: dict[str, int | None]
    source_by_category: dict[str, str]
    genres: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    audio_ref: str | None = None
    license_note: str = ""
    spotify_id: str | None = None


@dataclass
class CatalogBundle:
    sources: dict[str, dict]
    tracks: dict[str, CatalogTrackSpec]


class CatalogFormatError(ValueError):
    pass


def _file_sort_key(path: Path) -> tuple[int, str]:
    return (_FILE_ORDER.get(path.stem, len(_FILE_ORDER)), path.name)


def load_catalog_files(dirs: tuple[Path, ...] = CATALOG_DIRS) -> CatalogBundle:
    sources: dict[str, dict] = {}
    tracks: dict[str, CatalogTrackSpec] = {}
    files = sorted((p for d in dirs if d.exists() for p in d.glob("*.json")), key=_file_sort_key)
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        edition = data.get("edition")
        if edition not in ("main", "demo"):
            raise CatalogFormatError(f"{path.name}: edition deve ser 'main' ou 'demo'")
        source = data.get("source") or {}
        if not source.get("id") or source.get("kind") not in ("editorial", "chart"):
            raise CatalogFormatError(f"{path.name}: source.id e source.kind são obrigatórios")
        sources[source["id"]] = source
        file_category = data.get("category")
        for raw in data.get("tracks", []):
            title, artist = raw.get("title", "").strip(), raw.get("artist", "").strip()
            if not title or not artist:
                raise CatalogFormatError(f"{path.name}: faixa sem título ou artista: {raw}")
            categories = raw.get("categories") or ([file_category] if file_category else [])
            for cat in categories:
                if cat not in CATEGORY_SLUGS:
                    raise CatalogFormatError(f"{path.name}: categoria desconhecida '{cat}'")
            rank = raw.get("rank")
            if rank is not None and source["kind"] != "chart":
                raise CatalogFormatError(
                    f"{path.name}: posição de ranking só é permitida em fontes do tipo 'chart'"
                )
            slug = raw.get("slug") or track_slug(artist, title)
            spec = tracks.get(slug)
            if spec is None:
                spec = CatalogTrackSpec(
                    slug=slug, edition=edition, title=title, artist=artist,
                    categories={}, source_by_category={},
                    genres=list(raw.get("genres", [])), aliases=list(raw.get("aliases", [])),
                    audio_ref=raw.get("audio_ref"), license_note=raw.get("license", ""),
                    spotify_id=raw.get("spotify_id"),
                )
                tracks[slug] = spec
            elif spec.edition != edition:
                raise CatalogFormatError(f"{slug}: a mesma faixa não pode estar em duas edições")
            else:
                for alias in raw.get("aliases", []):
                    if alias not in spec.aliases:
                        spec.aliases.append(alias)
                spec.spotify_id = spec.spotify_id or raw.get("spotify_id")
            for cat in categories:
                spec.categories.setdefault(cat, rank)
                spec.source_by_category.setdefault(cat, source["id"])
    return CatalogBundle(sources=sources, tracks=tracks)


def sync_catalog(db: Session, bundle: CatalogBundle | None = None) -> dict[str, int]:
    """Insere/atualiza fontes, faixas e entradas. Nunca apaga faixas (desafios antigos
    as referenciam); entradas que saíram do JSON ficam inativas."""
    bundle = bundle or load_catalog_files()
    existing_sources = {s.id: s for s in db.scalars(select(CatalogSource))}
    for sid, src in bundle.sources.items():
        row = existing_sources.get(sid) or CatalogSource(id=sid)
        row.name = src.get("name", sid)
        row.kind = src["kind"]
        row.url = src.get("url")
        retrieved = src.get("retrieved_on")
        row.retrieved_on = date.fromisoformat(retrieved) if retrieved else None
        row.methodology = src.get("methodology", "")
        db.add(row)
    db.flush()

    existing_tracks = {t.slug: t for t in db.scalars(select(MusicTrack))}
    created = updated = 0
    for spec in bundle.tracks.values():
        row = existing_tracks.get(spec.slug)
        if row is None:
            row = MusicTrack(slug=spec.slug, availability="unknown")
            existing_tracks[spec.slug] = row
            created += 1
        else:
            updated += 1
        row.edition = spec.edition
        row.title = spec.title
        row.artist = spec.artist
        row.primary_category = next(iter(spec.categories), "geral")
        row.extra_genres = spec.genres
        row.aliases = spec.aliases
        row.audio_ref = spec.audio_ref
        row.license_note = spec.license_note
        row.spotify_id = spec.spotify_id
        db.add(row)
    db.flush()

    entries = {(e.category, e.track_id): e for e in db.scalars(select(CatalogEntry))}
    seen: set[tuple[str, int]] = set()
    for spec in bundle.tracks.values():
        track = existing_tracks[spec.slug]
        for cat, rank in spec.categories.items():
            key = (cat, track.id)
            seen.add(key)
            entry = entries.get(key) or CatalogEntry(category=cat, track_id=track.id)
            entry.reference_rank = rank
            entry.source_id = spec.source_by_category[cat]
            entry.active = True
            db.add(entry)
    deactivated = 0
    for key, entry in entries.items():
        if key not in seen and entry.active:
            entry.active = False
            deactivated += 1
    db.commit()
    catalog_index.invalidate()
    return {"created": created, "updated": updated, "deactivated": deactivated,
            "tracks": len(bundle.tracks)}


@dataclass(frozen=True)
class IndexedTrack:
    track_id: int
    slug: str
    title: str
    artist: str
    norm_title: str
    norm_artist: str


class CatalogIndex:
    """Índice em memória dos títulos de cada edição, para autocomplete e validação."""

    def __init__(self) -> None:
        self._by_edition: dict[str, list[IndexedTrack]] = {}
        self._lock = threading.Lock()

    def invalidate(self) -> None:
        with self._lock:
            self._by_edition.clear()

    def tracks(self, db: Session, edition: str) -> list[IndexedTrack]:
        with self._lock:
            cached = self._by_edition.get(edition)
        if cached is not None:
            return cached
        rows = db.execute(
            select(MusicTrack.id, MusicTrack.slug, MusicTrack.title, MusicTrack.artist)
            .join(CatalogEntry, CatalogEntry.track_id == MusicTrack.id)
            .where(MusicTrack.edition == edition, CatalogEntry.active.is_(True))
            .distinct()
            .order_by(MusicTrack.title)
        ).all()
        built = [
            IndexedTrack(r.id, r.slug, r.title, r.artist, normalize(r.title), normalize(r.artist))
            for r in rows
        ]
        with self._lock:
            self._by_edition[edition] = built
        return built

    def titles(self, db: Session, edition: str) -> list[str]:
        return [t.title for t in self.tracks(db, edition)]

    def search(self, db: Session, edition: str, query: str, limit: int = 8) -> list[IndexedTrack]:
        """Busca por título e artista. A ordenação depende apenas do texto digitado,
        nunca de qual música é a resposta do dia."""
        q = normalize(query)
        if not q:
            return []
        scored: list[tuple[int, str, IndexedTrack]] = []
        for t in self.tracks(db, edition):
            if t.norm_title == q:
                rank = 0
            elif t.norm_title.startswith(q):
                rank = 1
            elif any(w.startswith(q) for w in t.norm_title.split()):
                rank = 2
            elif q in t.norm_title:
                rank = 3
            elif t.norm_artist.startswith(q) or q in t.norm_artist:
                rank = 4
            else:
                continue
            scored.append((rank, t.norm_title, t))
        scored.sort(key=lambda item: (item[0], item[1]))
        return [t for _, _, t in scored[:limit]]


catalog_index = CatalogIndex()
