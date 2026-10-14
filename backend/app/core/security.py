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


# --------------------------------------------------------------- senhas (multiplayer)
# Senhas escolhidas por pessoas precisam de um hash lento e com sal: scrypt (biblioteca
# padrão), com parâmetros guardados junto do hash para poderem ser endurecidos depois.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R,
                            p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt),
                                   n=int(n), r=int(r), p=int(p), dklen=len(digest) // 2)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate.hex(), digest)
