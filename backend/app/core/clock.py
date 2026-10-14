"""Relógio injetável: permite testar viradas de dia sem depender da hora real."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


class Clock:
    def __init__(self, tz: ZoneInfo, now_fn: Callable[[], datetime] | None = None) -> None:
        self.tz = tz
        self._now_fn = now_fn or (lambda: datetime.now(UTC))

    def now(self) -> datetime:
        """Instante atual em UTC (timezone-aware)."""
        return self._now_fn().astimezone(UTC)

    def today(self) -> date:
        """Data do desafio vigente, sempre calculada no fuso configurado."""
        return self.now().astimezone(self.tz).date()

    def next_reset(self) -> datetime:
        """Instante (UTC) da próxima virada de desafio."""
        tomorrow = self.today() + timedelta(days=1)
        return datetime.combine(tomorrow, time.min, tzinfo=self.tz).astimezone(UTC)


class FrozenClock(Clock):
    """Relógio controlável para testes."""

    def __init__(self, tz: ZoneInfo, current: datetime) -> None:
        self.current = current
        super().__init__(tz, lambda: self.current)

    def set(self, current: datetime) -> None:
        self.current = current

    def advance(self, **kwargs: float) -> None:
        self.current = self.current + timedelta(**kwargs)


def as_utc(value: datetime) -> datetime:
    """SQLite devolve datetimes sem fuso; tratamos como UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
