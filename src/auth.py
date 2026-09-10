"""Autenticação por e-mail, persistida em Postgres (Neon) via st.connection.

O acesso é liberado pelo DO inserindo o e-mail na tabela `app_users` (sem
senha — ver scripts/grant_access.py). No primeiro login a própria pessoa
define sua senha; nos acessos seguintes, ela só precisa digitar a senha.
Quem não tem o e-mail cadastrado não passa da primeira tela.

Trava por tentativas (2026-09-10): depois de MAX_FAILED_ATTEMPTS senhas
erradas seguidas, a conta fica bloqueada por LOCKOUT_MINUTES — mitiga força
bruta sem precisar de nenhum serviço externo (rate-limit por e-mail, no
próprio Postgres).
"""

from __future__ import annotations

import bcrypt
import pandas as pd
import streamlit as st
from sqlalchemy import text

SUPPORT_EMAIL = "rian.jesus@pacaembu.com"

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app_users (
    email TEXT PRIMARY KEY,
    name TEXT,
    password_hash TEXT,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

# Cobre tabelas criadas antes destas 2 colunas existirem (idempotente).
ALTER_TABLE_SQL = [
    "ALTER TABLE app_users ADD COLUMN IF NOT EXISTS failed_attempts INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE app_users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ",
]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_connection():
    return st.connection("sql")


@st.cache_resource
def _ensure_schema() -> None:
    conn = get_connection()
    with conn.session as session:
        session.execute(text(CREATE_TABLE_SQL))
        for stmt in ALTER_TABLE_SQL:
            session.execute(text(stmt))
        session.commit()


def init_db() -> None:
    _ensure_schema()


def get_user(email: str) -> dict | None:
    conn = get_connection()
    df = conn.query(
        "SELECT email, name, password_hash, failed_attempts, locked_until FROM app_users WHERE email = :email",
        params={"email": normalize_email(email)},
        ttl=0,
    )
    return None if df.empty else df.iloc[0].to_dict()


def needs_password_setup(user: dict) -> bool:
    """True quando o e-mail tem acesso liberado mas ainda não definiu uma senha."""
    return not user.get("password_hash")


def is_locked(user: dict) -> bool:
    locked_until = user.get("locked_until")
    if locked_until is None or pd.isna(locked_until):
        return False
    return locked_until > pd.Timestamp.now(tz="UTC")


def lock_remaining_minutes(user: dict) -> int:
    """Minutos restantes de bloqueio (arredondado pra cima) — só chamar se is_locked(user)."""
    locked_until = user["locked_until"]
    remaining = (locked_until - pd.Timestamp.now(tz="UTC")).total_seconds()
    return max(1, int(-(-remaining // 60)))


def _register_failed_attempt(email: str) -> None:
    conn = get_connection()
    with conn.session as session:
        session.execute(
            text(
                """
                UPDATE app_users
                SET failed_attempts = failed_attempts + 1,
                    locked_until = CASE
                        WHEN failed_attempts + 1 >= :max_attempts THEN now() + (:lockout_minutes * interval '1 minute')
                        ELSE locked_until
                    END,
                    updated_at = now()
                WHERE email = :email
                """
            ),
            {"email": normalize_email(email), "max_attempts": MAX_FAILED_ATTEMPTS, "lockout_minutes": LOCKOUT_MINUTES},
        )
        session.commit()


def _reset_failed_attempts(email: str) -> None:
    conn = get_connection()
    with conn.session as session:
        session.execute(
            text("UPDATE app_users SET failed_attempts = 0, locked_until = NULL, updated_at = now() WHERE email = :email"),
            {"email": normalize_email(email)},
        )
        session.commit()


def verify_login(email: str, password: str) -> dict | None:
    user = get_user(email)
    if not user or not user.get("password_hash"):
        return None
    if is_locked(user):
        return None
    if check_password(password, user["password_hash"]):
        _reset_failed_attempts(email)
        return user
    _register_failed_attempt(email)
    return None


def set_initial_password(email: str, password: str) -> dict | None:
    conn = get_connection()
    email = normalize_email(email)
    with conn.session as session:
        session.execute(
            text("UPDATE app_users SET password_hash = :hash, updated_at = now() WHERE email = :email"),
            {"hash": hash_password(password), "email": email},
        )
        session.commit()
    return get_user(email)
