"""Pontuação: acertos com menos pistas valem mais. Tabela em `Settings.score_table`."""

from __future__ import annotations

from collections.abc import Sequence


def score_for(attempt_number: int, won: bool, table: Sequence[int]) -> int:
    if not won:
        return 0
    if not 1 <= attempt_number <= len(table):
        raise ValueError(f"Tentativa fora do intervalo: {attempt_number}")
    return table[attempt_number - 1]
