"""Abstração do provedor de áudio.

As regras do jogo só conhecem esta interface: trocar Deezer por arquivos licenciados
(ou outro serviço) não exige mudar tentativas, pontuação ou desafios.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass

from app.models import MusicTrack


@dataclass(frozen=True)
class AudioClip:
    data: bytes
    media_type: str
    duration: float


@dataclass(frozen=True)
class TrackMetadata:
    """Dados públicos opcionais revelados ao fim da partida (capa, link oficial)."""

    cover_url: str | None = None
    external_url: str | None = None
    attribution: str | None = None


class AudioProvider(ABC):
    name: str = "abstract"
    # Duração máxima de áudio que o provedor consegue fornecer (ex.: prévia de 30 s).
    max_seconds: float = 30.0
    is_demo: bool = False
    attribution: str | None = None

    @abstractmethod
    def check_availability(self, track: MusicTrack) -> bool:
        """Verifica (e, se necessário, resolve) se a faixa tem áudio disponível.
        Pode atualizar campos externos da faixa (id, capa, link)."""

    @abstractmethod
    def get_clip(self, track: MusicTrack, seconds: float, category: str | None = None) -> AudioClip:
        """Retorna os primeiros `seconds` de áudio. Lança AudioUnavailableError.
        `category` permite ao provedor adaptar o arranjo (usado no modo demo)."""

    def metadata(self, track: MusicTrack) -> TrackMetadata:
        return TrackMetadata(track.cover_url, track.external_url, self.attribution)


class TTLCache:
    """Cache LRU com expiração, usado para não baixar a mesma prévia a cada estágio."""

    def __init__(self, max_items: int, ttl_seconds: float) -> None:
        self.max_items = max_items
        self.ttl = ttl_seconds
        self._items: OrderedDict[str, tuple[float, object]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> object | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires, value = item
            if expires < time.monotonic():
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: str, value: object) -> None:
        if self.max_items <= 0 or self.ttl <= 0:
            return
        with self._lock:
            self._items[key] = (time.monotonic() + self.ttl, value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_items:
                self._items.popitem(last=False)
