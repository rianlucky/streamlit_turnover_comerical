"""Concede (ou remove) acesso ao painel para um e-mail.

Não cadastra senha nenhuma — a própria pessoa cria a senha dela no primeiro
login (ver src/auth_ui.py). Roda direto contra o Neon usando
`.streamlit/secrets.toml` — não precisa do Streamlit rodando.

Uso:
    python scripts/grant_access.py
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import sqlalchemy
from sqlalchemy import text

SECRETS_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app_users (
    email TEXT PRIMARY KEY,
    name TEXT,
    password_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

GRANT_SQL = """
INSERT INTO app_users (email, name)
VALUES (:email, :name)
ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, updated_at = now()
"""

REVOKE_SQL = "DELETE FROM app_users WHERE email = :email"


def _engine() -> sqlalchemy.Engine:
    with SECRETS_PATH.open("rb") as f:
        secrets = tomllib.load(f)
    return sqlalchemy.create_engine(secrets["connections"]["sql"]["url"])


def grant(engine: sqlalchemy.Engine, email: str, name: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        conn.execute(text(GRANT_SQL), {"email": email.strip().lower(), "name": name.strip()})


def revoke(engine: sqlalchemy.Engine, email: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(REVOKE_SQL), {"email": email.strip().lower()})


def main() -> None:
    if not SECRETS_PATH.exists():
        print(f"Não encontrei {SECRETS_PATH}.")
        print('Configure [connections.sql] com a URL do Neon antes de rodar este script (veja .streamlit/secrets.toml.example).')
        sys.exit(1)

    engine = _engine()
    print("Conceder acesso ao painel — deixe o e-mail em branco e aperte Enter para parar.")
    print("(a pessoa define a própria senha no primeiro login; não se cadastra senha aqui)\n")
    while True:
        entry = input("E-mail (ou 'remover:email@empresa.com' para tirar o acesso): ").strip()
        if not entry:
            break
        if entry.lower().startswith("remover:"):
            alvo = entry.split(":", 1)[1].strip()
            revoke(engine, alvo)
            print(f"-> acesso de {alvo.lower()} removido.\n")
            continue
        name = input("Nome de exibição: ").strip()
        grant(engine, entry, name)
        print(f"-> acesso concedido para {entry.strip().lower()}.\n")


if __name__ == "__main__":
    main()
