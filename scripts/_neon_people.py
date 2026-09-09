"""Schema e upload de `people_rows` no Neon — compartilhado por
`load_people_data.py` (HTML local / CSV) e `sync_from_databricks.py` (OAuth).

Nunca imprime dado de colaborador (nome, cidade, datas) — só contagens.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pandas as pd
import sqlalchemy
from sqlalchemy import text

SECRETS_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS people_rows (
    registro INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    cargo_atual2 TEXT NOT NULL,
    cidade TEXT NOT NULL,
    admissao TEXT NOT NULL,
    demissao TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    perm_meses DOUBLE PRECISION,
    setor TEXT,
    gestor TEXT,
    cargo_gestor TEXT
)
"""

# Cobre tabelas criadas antes destas 3 colunas existirem (idempotente).
ALTER_TABLE_SQL = [
    "ALTER TABLE people_rows ADD COLUMN IF NOT EXISTS setor TEXT",
    "ALTER TABLE people_rows ADD COLUMN IF NOT EXISTS gestor TEXT",
    "ALTER TABLE people_rows ADD COLUMN IF NOT EXISTS cargo_gestor TEXT",
]

# DataFrame column (fonte) -> coluna da tabela. Colunas ausentes na origem
# (ex.: Setor/Gestor no bootstrap via HTML) viram NULL.
COLUMN_MAP = {
    "Registro": "registro",
    "Nome": "nome",
    "Cargo Atual2": "cargo_atual2",
    "Cidade": "cidade",
    "Admissão": "admissao",
    "Demissão": "demissao",
    "Status": "status",
    "Perm_meses": "perm_meses",
    "Setor": "setor",
    "Gestor": "gestor",
    "Cargo Gestor": "cargo_gestor",
}


def load_secrets() -> dict:
    with SECRETS_PATH.open("rb") as f:
        return tomllib.load(f)


def engine() -> sqlalchemy.Engine:
    return sqlalchemy.create_engine(load_secrets()["connections"]["sql"]["url"])


class EmptySourceError(RuntimeError):
    """A origem (HTML/CSV/Databricks) voltou sem nenhuma linha — recusa substituir
    a base boa que já está no Neon por uma tabela vazia."""


def replace_people_rows(df: pd.DataFrame) -> int:
    """TRUNCATE + insert completo — a tabela sempre reflete só o último df carregado,
    nunca é incremental. Retorna o número de linhas gravadas."""
    if df.empty:
        raise EmptySourceError(
            "A origem voltou com 0 linhas — nada foi gravado no Neon (people_rows continua como estava)."
        )
    df = df.copy()
    for col in COLUMN_MAP:
        if col not in df.columns:
            df[col] = None
    df = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    df["demissao"] = df["demissao"].fillna("")

    eng = engine()
    with eng.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        for stmt in ALTER_TABLE_SQL:
            conn.execute(text(stmt))
        conn.execute(text("TRUNCATE TABLE people_rows"))
    df.to_sql("people_rows", eng, if_exists="append", index=False, method="multi", chunksize=200)
    return len(df)
