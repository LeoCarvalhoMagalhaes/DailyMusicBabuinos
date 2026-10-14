"""Camada de áudio: provedores intercambiáveis atrás da interface `AudioProvider`."""

from __future__ import annotations

from app.audio.base import AudioClip, AudioProvider, TTLCache
from app.core.config import Settings


def build_provider(settings: Settings) -> AudioProvider:
    cache = TTLCache(settings.audio_cache_max_items, settings.audio_cache_ttl_seconds)
    if settings.audio_provider == "deezer":
        from app.audio.deezer import DeezerProvider

        return DeezerProvider(settings.deezer_api_base, settings.deezer_timeout_seconds, cache)
    if settings.audio_provider == "local":
        from app.audio.local import LocalFileProvider

        return LocalFileProvider(settings.audio_local_dir)
    from app.audio.demo import DemoSynthProvider

    return DemoSynthProvider(cache)


__all__ = ["AudioClip", "AudioProvider", "TTLCache", "build_provider"]
