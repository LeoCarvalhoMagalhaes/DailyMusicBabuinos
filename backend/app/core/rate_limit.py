"""Limitador de requisições em memória (janela deslizante).

Suficiente para uma instância única (plano gratuito). Com várias instâncias, troque
por um armazenamento compartilhado (ex.: Redis) mantendo a mesma interface.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque

from app.core.errors import RateLimitedError


class RateLimiter:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and bucket[0] <= now - window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                retry = max(1, math.ceil(bucket[0] + window_seconds - now))
                raise RateLimitedError(
                    "Calma, roqueiro! Muitas requisições. Tente de novo em instantes.",
                    headers={"Retry-After": str(retry)},
                )
            bucket.append(now)
            if len(self._hits) > 10_000:
                self._prune(now, window_seconds)

    def _prune(self, now: float, window_seconds: float) -> None:
        stale = [k for k, b in self._hits.items() if not b or b[-1] <= now - window_seconds]
        for key in stale:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
