"""Ferramentas de operação (uso exclusivo de quem administra o servidor).

    python -m app.cli migrate            # aplica migrações
    python -m app.cli sync-catalog       # sincroniza JSON -> banco
    python -m app.cli publish-today      # publica os desafios do dia nas 6 categorias
    python -m app.cli check-audio        # valida a disponibilidade de áudio do catálogo
    python -m app.cli reveal --category rock   # mostra a resposta de hoje (suporte/testes E2E)
    python -m app.cli purge-inactive --days 400  # retenção: apaga jogadores inativos
    python -m app.cli import-kworb               # gera o catálogo a partir do Spotify (kworb)

`reveal` lê o banco diretamente e não existe como endpoint HTTP.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select

from app.audio import build_provider
from app.catalog_import.kworb import (
    GLOBAL_SONGS_URL,
    KworbClient,
    KworbFormatError,
    import_kworb,
    load_seeds,
)
from app.core.categories import CATEGORY_SLUGS
from app.core.clock import Clock
from app.core.config import get_settings
from app.core.errors import AudioUnavailableError
from app.database.migrate import upgrade_to_head
from app.database.session import build_engine, build_session_factory
from app.models import MusicTrack, Player
from app.services.catalog import DATA_DIR, sync_catalog
from app.services.daily import get_challenge, get_or_create_challenge


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    sub.add_parser("sync-catalog")
    sub.add_parser("publish-today")
    check = sub.add_parser("check-audio")
    check.add_argument("--limit", type=int, default=50)
    reveal = sub.add_parser("reveal")
    reveal.add_argument("--category", choices=CATEGORY_SLUGS, required=True)
    reveal.add_argument("--json", action="store_true")
    purge = sub.add_parser("purge-inactive")
    purge.add_argument("--days", type=int, default=400)
    kworb = sub.add_parser("import-kworb", help="Gera o catálogo a partir dos streams do Spotify")
    kworb.add_argument("--categories", nargs="+", choices=CATEGORY_SLUGS,
                       default=list(CATEGORY_SLUGS))
    kworb.add_argument("--out", type=Path, default=DATA_DIR / "catalog")
    kworb.add_argument("--seeds", type=Path, default=DATA_DIR / "kworb_seeds.json")
    kworb.add_argument("--cache", type=Path, default=Path(".kworb-cache"))
    kworb.add_argument("--delay", type=float, default=2.0,
                       help="Segundos entre requisições ao kworb (seja gentil)")
    kworb.add_argument("--limit", type=int, default=100)
    kworb.add_argument("--max-per-artist", type=int, default=3)
    kworb.add_argument("--general-url", default=GLOBAL_SONGS_URL,
                       help="Lista do kworb usada na categoria Geral")
    kworb.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "import-kworb":
        client = KworbClient(cache_dir=args.cache, delay_seconds=args.delay)
        try:
            import_kworb(client, args.out, load_seeds(args.seeds), args.categories,
                         retrieved_on=datetime.now(UTC).date(), limit=args.limit,
                         max_per_artist=args.max_per_artist, general_url=args.general_url,
                         allow_partial=args.allow_partial)
        except KworbFormatError as exc:
            print(f"Importação interrompida: {exc}", file=sys.stderr)
            return 1
        print("Pronto. Reinicie a API ou rode `python -m app.cli sync-catalog`.")
        return 0

    settings = get_settings()
    if args.command == "migrate":
        upgrade_to_head(settings.database_url)
        print("Migrações aplicadas.")
        return 0

    factory = build_session_factory(build_engine(settings.database_url))
    provider = build_provider(settings)
    clock = Clock(settings.tz)
    with factory() as db:
        if args.command == "sync-catalog":
            print(sync_catalog(db))
        elif args.command == "publish-today":
            for category in CATEGORY_SLUGS:
                ch = get_or_create_challenge(db, settings, provider, category, clock.today(),
                                             clock.now())
                print(f"{category}: desafio #{ch.id} publicado para {ch.challenge_date}")
        elif args.command == "check-audio":
            tracks = db.scalars(
                select(MusicTrack)
                .where(MusicTrack.edition == settings.catalog_edition,
                       MusicTrack.availability == "unknown")
                .limit(args.limit)
            ).all()
            for track in tracks:
                try:
                    ok = provider.check_availability(track)
                    print(f"{'OK ' if ok else 'N/D'} {track.artist} — {track.title}")
                except AudioUnavailableError as exc:
                    print(f"ERRO {track.slug}: {exc.message}")
                    break
            db.commit()
        elif args.command == "reveal":
            ch = get_challenge(db, args.category, clock.today(), settings.catalog_edition)
            if ch is None:
                print("Desafio de hoje ainda não publicado.", file=sys.stderr)
                return 1
            payload = {"category": args.category, "date": str(ch.challenge_date),
                       "title": ch.track.title, "artist": ch.track.artist}
            print(json.dumps(payload, ensure_ascii=False) if args.json
                  else f"{payload['title']} — {payload['artist']}")
        elif args.command == "purge-inactive":
            cutoff = datetime.now(UTC) - timedelta(days=args.days)
            result = db.execute(delete(Player).where(Player.last_seen_at < cutoff))
            db.commit()
            print(f"{result.rowcount} jogadores inativos removidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
