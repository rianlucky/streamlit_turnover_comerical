"""Autenticação por e-mail, persistida em Postgres (Neon) via st.connection.

O acesso é liberado pelo DO inserindo o e-mail na tabela `app_users` (sem
senha — ver scripts/grant_access.py). No primeiro login a própria pessoa
define sua senha; nos acessos seguintes, ela só precisa digitar a senha.
Quem não tem o e-mail cadastrado não passa da primeira tela.
"""

from __future__ import annotations

import bcrypt
import streamlit as st
from sqlalchemy import text

SUPPORT_EMAIL = "rian.jesus@pacaembu.com"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app_users (
    email TEXT PRIMARY KEY,
    name TEXT,
    password_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


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
        session.commit()


def init_db() -> None:
    _ensure_schema()


def get_user(email: str) -> dict | None:
    conn = get_connection()
    df = conn.query(
        "SELECT email, name, password_hash FROM app_users WHERE email = :email",
        params={"email": normalize_email(email)},
        ttl=0,
    )
    return None if df.empty else df.iloc[0].to_dict()


def needs_password_setup(user: dict) -> bool:
    """True quando o e-mail tem acesso liberado mas ainda não definiu uma senha."""
    return not user.get("password_hash")


def verify_login(email: str, password: str) -> dict | None:
    user = get_user(email)
    if user and user.get("password_hash") and check_password(password, user["password_hash"]):
        return user
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
