"""Cadastro e login do multiplayer.

- Nome de usuário: 3 a 20 caracteres [a-z0-9_], sem diferenciar maiúsculas.
- Senha: 8 a 128 caracteres, guardada com scrypt (core.security).
- Apelido exibido nas salas: 2 a 24 caracteres.
- Login devolve um token aleatório; o banco guarda só o SHA-256 dele, com validade.
- Mensagem de erro de login igual para usuário inexistente e senha errada, com o mesmo
  custo de hash nos dois casos (não revela quais usuários existem).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import as_utc
from app.core.errors import AppError, ConflictError, UnauthorizedError
from app.core.security import (
    hash_password,
    hash_token,
    looks_like_token,
    new_player_token,
    verify_password,
)
from app.models import Account, AuthSession, Player

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
# Hash de referência para gastar o mesmo tempo quando o usuário não existe.
_DUMMY_HASH = hash_password("senha-que-nao-existe")


def normalize_username(username: str) -> str:
    return username.strip().lower()


def clean_display_name(name: str) -> str:
    name = unicodedata.normalize("NFC", " ".join(name.split()))
    return "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")


def register(db: Session, username: str, password: str, display_name: str, now: datetime,
             session_days: int) -> tuple[Account, str]:
    username = normalize_username(username)
    display = clean_display_name(display_name)
    if not USERNAME_RE.match(username):
        raise AppError("O usuário deve ter de 3 a 20 letras minúsculas, números ou _.",
                       code="invalid_username", status_code=422)
    if not 8 <= len(password) <= 128:
        raise AppError("A senha precisa ter de 8 a 128 caracteres.", code="weak_password",
                       status_code=422)
    if not 2 <= len(display) <= 24:
        raise AppError("O apelido precisa ter de 2 a 24 caracteres.",
                       code="invalid_display_name", status_code=422)
    player = Player(id=str(uuid.uuid4()), token_hash=hash_token(new_player_token()),
                    created_at=now, last_seen_at=now)
    account = Account(id=str(uuid.uuid4()), username=username, display_name=display,
                      password_hash=hash_password(password), player_id=player.id,
                      created_at=now)
    db.add(player)
    db.flush()  # o jogador precisa existir antes da conta (chave estrangeira)
    db.add(account)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Esse usuário já existe. Escolha outro.",
                            code="username_taken") from exc
    token = _open_session(db, account, now, session_days)
    db.commit()
    return account, token


def login(db: Session, username: str, password: str, now: datetime,
          session_days: int) -> tuple[Account, str]:
    account = db.scalar(select(Account).where(Account.username == normalize_username(username)))
    valid = verify_password(password, account.password_hash if account else _DUMMY_HASH)
    if account is None or not valid:
        raise UnauthorizedError("Usuário ou senha incorretos.", code="invalid_credentials")
    token = _open_session(db, account, now, session_days)
    db.commit()
    return account, token


def _open_session(db: Session, account: Account, now: datetime, days: int) -> str:
    token = new_player_token()
    db.add(AuthSession(token_hash=hash_token(token), account_id=account.id, created_at=now,
                       expires_at=now + timedelta(days=days)))
    # Limpeza oportunista das sessões vencidas desta conta.
    db.execute(delete(AuthSession).where(AuthSession.account_id == account.id,
                                         AuthSession.expires_at < now))
    return token


def logout(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    db.commit()


def account_for_token(db: Session, token: str | None, now: datetime) -> Account | None:
    if not token or not looks_like_token(token):
        return None
    session = db.get(AuthSession, hash_token(token))
    if session is None or as_utc(session.expires_at) <= now:
        return None
    return session.account
