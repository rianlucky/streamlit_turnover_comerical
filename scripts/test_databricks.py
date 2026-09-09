"""Testa a conexão com o SQL Warehouse do Databricks usando o que estiver
preenchido em `.streamlit/secrets.toml` na seção [databricks]: PAT (token) ou
M2M (client_id + client_secret) — o que o time liberar primeiro.

Uso:
    python scripts/test_databricks.py
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from databricks import sql

SECRETS_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"


def _config() -> dict:
    with SECRETS_PATH.open("rb") as f:
        secrets = tomllib.load(f)
    return secrets["databricks"]


def _connect(cfg: dict):
    server_hostname = cfg["server_hostname"]
    http_path = cfg["http_path"]
    token = cfg.get("token", "").strip()
    client_id = cfg.get("client_id", "").strip()
    client_secret = cfg.get("client_secret", "").strip()

    if token:
        print("Autenticando com PAT (token)...")
        return sql.connect(
            server_hostname=server_hostname,
            http_path=http_path,
            access_token=token,
        )

    if client_id and client_secret:
        print("Autenticando com OAuth M2M (service principal)...")
        return sql.connect(
            server_hostname=server_hostname,
            http_path=http_path,
            auth_type="databricks-oauth",
            client_id=client_id,
            client_secret=client_secret,
        )

    print("Nenhuma credencial preenchida em [databricks] (token ou client_id/client_secret).")
    print("Preencha .streamlit/secrets.toml antes de rodar este script (veja secrets.toml.example).")
    sys.exit(1)


def main() -> None:
    if not SECRETS_PATH.exists():
        print(f"Não encontrei {SECRETS_PATH}.")
        sys.exit(1)

    cfg = _config()
    connection = _connect(cfg)

    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user(), current_catalog(), current_schema()")
            print("Conectado com sucesso.")
            print("current_user, current_catalog, current_schema:", cursor.fetchone())

            cursor.execute("SHOW SCHEMAS")
            print("\nSchemas visíveis para essa credencial:")
            for row in cursor.fetchall():
                print(" -", row)


if __name__ == "__main__":
    main()
