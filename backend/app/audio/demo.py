"""Provedor do MODO DEMONSTRAÇÃO.

Toca arranjos sintetizados pelo próprio jogo de melodias em domínio público. Serve
para desenvolvimento, testes e para o jogo funcionar sem credenciais ou acesso a
serviços externos. A interface sempre identifica este modo como demonstração.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.audio.base import AudioClip, AudioProvider, TTLCache
from app.audio.synth import SR, load_songs, render_int16
from app.audio.wav import encode_wav, trim_wav
from app.core.errors import AudioUnavailableError
from app.models import MusicTrack

RENDER_SECONDS = 20.0


class DemoSynthProvider(AudioProvider):
    name = "demo"
    max_seconds = RENDER_SECONDS
    is_demo = True
    attribution = "Modo demonstração: arranjo sintetizado de composição em domínio público"

    def __init__(self, cache: TTLCache) -> None:
        self.cache = cache

    def check_availability(self, track: MusicTrack) -> bool:
        available = bool(track.audio_ref) and track.audio_ref in load_songs()
        track.availability = "available" if available else "unavailable"
        track.availability_checked_at = datetime.now(UTC)
        return available

    def _full_wav(self, track: MusicTrack, style: str) -> bytes:
        key = f"demo:{track.audio_ref}:{style}"
        cached = self.cache.get(key)
        if isinstance(cached, bytes):
            return cached
        try:
            samples = render_int16(track.audio_ref or "", style, RENDER_SECONDS)
        except KeyError as exc:
            raise AudioUnavailableError("Melodia de demonstração não encontrada.") from exc
        data = encode_wav(samples, SR)
        self.cache.set(key, data)
        return data

    def get_clip(self, track: MusicTrack, seconds: float, category: str | None = None) -> AudioClip:
        data = self._full_wav(track, category or track.primary_category)
        clip, duration = trim_wav(data, min(seconds, self.max_seconds))
        return AudioClip(clip, "audio/wav", duration)
