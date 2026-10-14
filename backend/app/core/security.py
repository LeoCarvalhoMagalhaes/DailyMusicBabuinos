"""Identidade anônima do jogador.

O jogador recebe um token aleatório de 256 bits. O banco guarda apenas o SHA-256
do token: um vazamento do banco não permite se passar por ninguém. Como o token já
tem alta entropia, um hash rápido é adequado (diferente de senhas escolhidas por humanos).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

TOKEN_BYTES = 32


def new_player_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def looks_like_token(token: str) -> bool:
    return 32 <= len(token) <= 128 and all(c.isalnum() or c in "-_" for c in token)


def hmac_hex(secret: str, message: str) -> str:
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
