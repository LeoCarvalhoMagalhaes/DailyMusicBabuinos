"""Provedor Deezer: prévias oficiais de 30 s da API pública.

Limitações reais (documentadas em docs/03-audio-e-licenciamento.md):
- A API pública entrega apenas prévias de ~30 s em MP3; não há trecho arbitrário
  nem faixa completa sem login Premium no SDK oficial.
- As URLs de prévia são assinadas e expiram; por isso o id da faixa é guardado e a
  URL é obtida de novo quando necessário.
- Nem toda faixa tem prévia em todas as regiões; faixas sem prévia são marcadas como
  indisponíveis e o sorteio diário passa para a próxima candidata.
- Os termos do Deezer para desenvolvedores exigem atribuição e permitem uso pessoal
  e não comercial; uso comercial exige contato/licença com o Deezer.

O MP3 é baixado pelo servidor e cortado no estágio liberado: o navegador nunca
recebe a URL da prévia nem o arquivo completo antes do fim da partida.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import UTC, datetime

import httpx

from app.audio.base import AudioClip, AudioProvider, TTLCache
from app.audio.mp3 import Mp3FormatError, trim_mp3
from app.core.errors import AudioUnavailableError
from app.models import MusicTrack
from app.services.answers import normalize, variants

logger = logging.getLogger("babuinos.audio.deezer")

MAX_PREVIEW_BYTES = 2 * 1024 * 1024

# Palavras que indicam uma versão diferente da gravação original.
_VERSION_WORDS = re.compile(
    r"\b(live|ao vivo|en vivo|karaoke|instrumental|remix|acoustic|acustico|cover|tribute|"
    r"demo|sped up|slowed|reverb|8d|orchestral|piano version|unplugged)\b"
)


def _versions(text: str) -> set[str]:
    """Marcas de versão num texto (minúsculas, sem acentos; mantém sufixos como
    "- Acoustic Version", que `normalize` removeria)."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return set(_VERSION_WORDS.findall(plain))


class DeezerProvider(AudioProvider):
    name = "deezer"
    max_seconds = 29.0
    attribution = "Prévia de áudio fornecida pelo Deezer"

    def __init__(self, base_url: str, timeout: float, cache: TTLCache,
                 client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache = cache
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=True,
                                             headers={"User-Agent": "MusicasBabuinas/1.0"})

    # -- API -----------------------------------------------------------------
    def _api(self, path: str, params: dict | None = None) -> dict:
        try:
            response = self.client.get(f"{self.base_url}{path}", params=params)
        except httpx.HTTPError as exc:
            raise AudioUnavailableError("O serviço de áudio não respondeu.") from exc
        if response.status_code != 200:
            raise AudioUnavailableError(f"O serviço de áudio respondeu {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AudioUnavailableError("Resposta inválida do serviço de áudio.") from exc
        if isinstance(payload, dict) and payload.get("error"):
            # Ex.: {"error": {"type": "DataException", "code": 800}} ou cota excedida (code 4).
            raise AudioUnavailableError("O serviço de áudio recusou a consulta.")
        return payload

    def _search(self, track: MusicTrack) -> dict | None:
        # Busca simples primeiro: em 14/10/2026 o filtro avançado `artist:"..."` da API
        # real não funcionava (com `track:` voltava vazio). Ele fica como segunda tentativa.
        queries = [f"{track.artist} {track.title}",
                   f'artist:"{track.artist}" track:"{track.title}"']
        for query in queries:
            data = self._api("/search", {"q": query, "limit": 25}).get("data", [])
            item = self._best_match(track, data)
            if item:
                return item
        return None

    def _best_match(self, track: MusicTrack, data: list[dict]) -> dict | None:
        """Escolhe a gravação original: mesmo título, artista certo e, entre as versões do
        próprio artista (o `title_short` de "Bohemian Rhapsody (Live Aid)" é igual ao da
        original), a de estúdio mais popular. Covers e karaokê de outros artistas nunca
        entram, porque o artista precisa bater."""
        wanted_titles = variants(track.title)
        for alias in track.aliases:
            wanted_titles |= variants(alias)
        # Se o próprio catálogo pede uma versão (ex.: "Evidências - Ao Vivo"), ela vale.
        allowed_versions = _versions(" ".join([track.title, *track.aliases]))
        full_artist = normalize(track.artist)
        # "Kenny Rogers & Dolly Parton" -> aceita cada artista principal individualmente.
        exact_artists = {full_artist, *(a.strip() for a in full_artist.split(" and "))}
        best: tuple[tuple[int, int, int], dict] | None = None
        for item in data:
            artist = normalize((item.get("artist") or {}).get("name", ""))
            titles = variants(item.get("title_short") or item.get("title") or "")
            if not artist or not item.get("preview") or not titles & wanted_titles:
                continue
            if artist in exact_artists:
                artist_score = 2
            elif artist in full_artist or full_artist in artist:
                artist_score = 1  # ex.: "Jimi Hendrix" vs "The Jimi Hendrix Experience"
            else:
                continue
            unwanted = _versions(" ".join([
                item.get("title_version") or "", item.get("title") or "",
                (item.get("album") or {}).get("title") or "",
            ])) - allowed_versions
            key = (artist_score, 0 if unwanted else 1, int(item.get("rank") or 0))
            if best is None or key > best[0]:
                best = (key, item)
        return best[1] if best else None

    def _apply(self, track: MusicTrack, item: dict) -> None:
        track.external_provider = self.name
        track.external_id = str(item["id"])
        track.external_url = item.get("link")
        album = item.get("album") or {}
        track.cover_url = album.get("cover_big") or album.get("cover_medium")

    # -- AudioProvider ---------------------------------------------------------
    def check_availability(self, track: MusicTrack) -> bool:
        now = datetime.now(UTC)
        try:
            if track.external_provider == self.name and track.external_id:
                item = self._api(f"/track/{track.external_id}")
                available = bool(item.get("preview")) and item.get("readable", True)
                if available:
                    self._apply(track, item)
            else:
                item = self._search(track)
                available = item is not None
                if item:
                    self._apply(track, item)
        except AudioUnavailableError:
            # Falha de rede não marca a faixa como indisponível para sempre.
            logger.warning("Falha ao verificar %s no Deezer", track.slug)
            raise
        track.availability = "available" if available else "unavailable"
        track.availability_checked_at = now
        return available

    def _preview_bytes(self, track: MusicTrack) -> bytes:
        key = f"deezer:{track.external_id}"
        cached = self.cache.get(key)
        if isinstance(cached, bytes):
            return cached
        if not track.external_id and not self.check_availability(track):
            raise AudioUnavailableError("Esta faixa não tem prévia disponível.")
        item = self._api(f"/track/{track.external_id}")
        preview_url = item.get("preview")
        if not preview_url:
            raise AudioUnavailableError("Esta faixa não tem prévia disponível.")
        try:
            with self.client.stream("GET", preview_url) as response:
                if response.status_code != 200:
                    raise AudioUnavailableError("Não foi possível baixar a prévia.")
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    chunks += chunk
                    if len(chunks) > MAX_PREVIEW_BYTES:
                        raise AudioUnavailableError("Prévia maior que o esperado.")
        except httpx.HTTPError as exc:
            raise AudioUnavailableError("Não foi possível baixar a prévia.") from exc
        data = bytes(chunks)
        self.cache.set(key, data)
        return data

    def get_clip(self, track: MusicTrack, seconds: float, category: str | None = None) -> AudioClip:
        data = self._preview_bytes(track)
        try:
            clip, duration = trim_mp3(data, min(seconds, self.max_seconds))
        except Mp3FormatError as exc:
            raise AudioUnavailableError("A prévia recebida está corrompida.") from exc
        return AudioClip(clip, "audio/mpeg", duration)
