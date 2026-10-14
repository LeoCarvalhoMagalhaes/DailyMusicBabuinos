"""Normalização e validação de respostas.

Regra do jogo: a resposta principal é o TÍTULO da música. Aceitamos também os
aliases documentados no catálogo. A comparação ignora acentos, maiúsculas,
pontuação, espaços extras, artigos iniciais e trechos entre parênteses
("(Remastered 2011)", "(I Can't Get No)").

Tolerância a erros de digitação: uma distância de edição pequena é aceita apenas
quando o palpite não coincide exatamente com OUTRA música do catálogo — assim
"Hurt" não vira acerto para "Hurts".
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

_PARENS = re.compile(r"[\(\[][^\)\]]*[\)\]]")
_FEAT = re.compile(r"\s+(feat\.?|ft\.?|featuring|part\.?)\s+.*$")
_DASH_SUFFIX = re.compile(r"\s+-\s+(.*remaster.*|.*version.*|.*live.*|.*mix.*|.*edit.*)$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_LEADING_ARTICLES = ("the ", "a ", "an ", "o ", "os ", "as ")

MAX_GUESS_LENGTH = 120


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _basic(text: str) -> str:
    text = _strip_accents(text).lower().strip()
    text = text.replace("&", " and ").replace("’", "'").replace("'", "")
    # Abreviações com ponto: "U.K." -> "uk", "D.A.N.C.E." -> "dance".
    text = text.replace(".", "")
    text = _FEAT.sub("", text)
    text = _DASH_SUFFIX.sub("", text)
    return text


def _squash(text: str) -> str:
    text = _NON_ALNUM.sub(" ", text)
    text = " ".join(text.split())
    for article in _LEADING_ARTICLES:
        if text.startswith(article) and len(text) > len(article) + 2:
            text = text[len(article) :]
            break
    return text


def normalize(text: str) -> str:
    """Forma canônica completa (mantém o conteúdo entre parênteses)."""
    return _squash(_PARENS.sub(lambda m: " " + m.group(0)[1:-1] + " ", _basic(text)))


def variants(text: str) -> set[str]:
    """Formas aceitas de um título: completa e sem o conteúdo entre parênteses."""
    base = _basic(text)
    forms = {_squash(base.replace("(", " ").replace(")", " ").replace("[", " ").replace("]", " "))}
    without_parens = _squash(_PARENS.sub(" ", base))
    if without_parens:
        forms.add(without_parens)
    forms.discard("")
    return forms


def accepted_forms(title: str, aliases: Iterable[str]) -> set[str]:
    forms = variants(title)
    for alias in aliases:
        forms |= variants(alias)
    return forms


def edit_distance(a: str, b: str, limit: int = 3) -> int:
    """Distância de Damerau-Levenshtein (transposição adjacente), com corte."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev_prev: list[int] = []
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev_prev[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        prev_prev, prev = prev, cur
    return prev[-1]


def typo_tolerance(length: int) -> int:
    if length >= 12:
        return 2
    if length >= 5:
        return 1
    return 0


def is_correct(guess: str, title: str, aliases: Iterable[str],
               other_titles: Iterable[str] = ()) -> bool:
    guess_forms = variants(guess)
    if not guess_forms:
        return False
    accepted = accepted_forms(title, aliases)
    if guess_forms & accepted:
        return True
    # Palpite idêntico a outra música conhecida: é outra música, não um erro de digitação.
    others = set()
    for other in other_titles:
        others |= variants(other)
    if guess_forms & (others - accepted):
        return False
    for g in guess_forms:
        for a in accepted:
            tolerance = typo_tolerance(len(a))
            if tolerance and edit_distance(g, a, tolerance) <= tolerance:
                return True
    return False


def clean_guess(raw: str) -> str:
    """Limpa o texto enviado: remove controles e espaços repetidos, limita o tamanho."""
    text = "".join(ch for ch in raw if unicodedata.category(ch)[0] != "C")
    return " ".join(text.split())[:MAX_GUESS_LENGTH]
