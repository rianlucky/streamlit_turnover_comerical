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
CREATE TABLE IF NOT EXISTS turnover.people_rows (
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
    cargo_gestor TEXT,
    tipo_desligamento TEXT
)
"""

# Uma linha só (id=1) — timestamp da última carga bem-sucedida, exibido na barra
# lateral do app ("dados atualizados em"). Ver OBSOLETO.md pra outros campos
# gravados mas não lidos — esse aqui é o oposto: só escrito e lido, sem PII.
CREATE_SYNC_META_SQL = """
CREATE TABLE IF NOT EXISTS turnover.sync_meta (
    id INTEGER PRIMARY KEY DEFAULT 1,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sync_meta_single_row CHECK (id = 1)
)
"""

# Mantém `sync_meta` correto mesmo quando `people_rows` é editada fora destes
# scripts (ex.: INSERT/UPDATE direto no SQL Editor do Neon) — sem isso a barra
# lateral mostraria uma data de sync antiga mesmo com dado novo na tabela.
CREATE_TOUCH_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION turnover.touch_sync_meta() RETURNS trigger
LANGUAGE plpgsql SET search_path = turnover, pg_temp AS $$
BEGIN
    INSERT INTO turnover.sync_meta (id, synced_at) VALUES (1, now())
    ON CONFLICT (id) DO UPDATE SET synced_at = now();
    RETURN NULL;
END;
$$
"""

CREATE_TOUCH_TRIGGER_SQL = """
DROP TRIGGER IF EXISTS trg_people_rows_touch_sync_meta ON turnover.people_rows;
CREATE TRIGGER trg_people_rows_touch_sync_meta
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON turnover.people_rows
FOR EACH STATEMENT EXECUTE FUNCTION turnover.touch_sync_meta()
"""

# Cobre tabelas criadas antes destas colunas existirem (idempotente).
ALTER_TABLE_SQL = [
    "ALTER TABLE turnover.people_rows ADD COLUMN IF NOT EXISTS setor TEXT",
    "ALTER TABLE turnover.people_rows ADD COLUMN IF NOT EXISTS gestor TEXT",
    "ALTER TABLE turnover.people_rows ADD COLUMN IF NOT EXISTS cargo_gestor TEXT",
    "ALTER TABLE turnover.people_rows ADD COLUMN IF NOT EXISTS tipo_desligamento TEXT",
    "ALTER TABLE turnover.people_rows ADD COLUMN IF NOT EXISTS area TEXT",
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
    "Tipo Desligamento": "tipo_desligamento",
    "Area": "area",
}


def load_secrets() -> dict:
    with SECRETS_PATH.open("rb") as f:
        return tomllib.load(f)


def _etl_url(secrets: dict) -> str:
    """Escrita = usuário de carga (migração 005), em [etl] url no
    secrets.toml local. [connections.sql] agora tem o usuário do painel
    (usuário do painel), que só lê. NÃO colar [etl] nos Secrets do Streamlit Cloud."""
    url = (secrets.get("etl") or {}).get("url")
    if not url:
        raise SystemExit("Falta [etl] url (usuário de carga) em .streamlit/secrets.toml")
    return url


def engine() -> sqlalchemy.Engine:
    return sqlalchemy.create_engine(_etl_url(load_secrets()))


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

    # `registro` é PRIMARY KEY, mas a origem pode trazer o mesmo registro mais de uma
    # vez (ex.: histórico de múltiplos vínculos na fato_funcionario_inativo, ou um JOIN
    # que multiplicou a linha) — mantém a primeira ocorrência e avisa, em vez de quebrar
    # o carregamento inteiro por causa de uma duplicata.
    before = len(df)
    df = df.drop_duplicates(subset="registro", keep="first")
    duplicated = before - len(df)
    if duplicated:
        print(f"Aviso: {duplicated} registro(s) duplicado(s) na origem — mantida só a primeira ocorrência de cada.")

    # O Databricks devolve admissao/demissao como datetime.date; o HTML/CSV já manda
    # string. Normaliza os dois pra texto ISO antes de gravar na coluna TEXT.
    for col in ("admissao", "demissao"):
        df[col] = df[col].apply(lambda v: v.isoformat() if hasattr(v, "isoformat") else v)
    df["demissao"] = df["demissao"].fillna("")
    # cidade/nome/cargo_atual2/status são NOT NULL na tabela; evita erro de integridade
    # quando a origem não tem correspondência (ex.: join de cidade sem match).
    for col in ("cidade", "nome", "cargo_atual2", "status"):
        df[col] = df[col].fillna("")

    eng = engine()
    # TRUNCATE + insert na MESMA transação: se o insert falhar por qualquer motivo
    # (tipo de dado, chave duplicada, NOT NULL), o TRUNCATE também é desfeito — nunca
    # fica uma tabela vazia no meio do caminho.
    with eng.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        for stmt in ALTER_TABLE_SQL:
            conn.execute(text(stmt))
        # sync_meta e o trigger precisam existir ANTES do TRUNCATE, que já dispara
        # touch_sync_meta() (ver CREATE_TOUCH_TRIGGER_SQL).
        conn.execute(text(CREATE_SYNC_META_SQL))
        conn.execute(text(CREATE_TOUCH_FUNCTION_SQL))
        conn.execute(text(CREATE_TOUCH_TRIGGER_SQL))
        conn.execute(text("TRUNCATE TABLE turnover.people_rows"))
        df.to_sql("people_rows", conn, schema="turnover", if_exists="append", index=False, method="multi", chunksize=200)
        conn.execute(text("INSERT INTO turnover.sync_meta (id, synced_at) VALUES (1, now()) ON CONFLICT (id) DO UPDATE SET synced_at = now()"))
    return len(df)
