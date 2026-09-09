"""Carrega a base de colaboradores na tabela `people_rows` do Postgres (Neon),
de onde `data_logic.load_source_data()` passa a ler (em vez do HTML local).

Faz um replace completo (TRUNCATE + insert) a cada execução — ver `_neon_people.py`.

Uso:
    # bootstrap a partir do HTML local (assets/*.html) — dado que já existe hoje
    python scripts/load_people_data.py

    # a partir de um export do Databricks (CSV com as colunas Registro, Nome,
    # Cargo Atual2, Cidade, Admissão, Demissão, Status, Perm_meses)
    python scripts/load_people_data.py --csv caminho/para/export.csv

Nunca imprime dado de colaborador (nome, cidade, datas) — só contagens. Para
carregar direto do Databricks via OAuth (sem exportar CSV manualmente), veja
scripts/sync_from_databricks.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_logic import _extract_json, _find_html_source  # noqa: E402

from _neon_people import SECRETS_PATH, replace_people_rows  # noqa: E402


def _load_from_html() -> pd.DataFrame:
    source = _find_html_source().read_text(encoding="utf-8")
    raw_rows = _extract_json(source, "ALL_ROWS", "CIDADES")
    return pd.DataFrame(raw_rows)


def _load_from_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"Registro": "int64"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path, default=None, help="Export do Databricks (default: HTML local em assets/)")
    args = parser.parse_args()

    if not SECRETS_PATH.exists():
        print(f"Não encontrei {SECRETS_PATH}.")
        print("Configure [connections.sql] com a URL do Neon antes de rodar este script.")
        sys.exit(1)

    df = _load_from_csv(args.csv) if args.csv else _load_from_html()

    required = {"Registro", "Nome", "Cargo Atual2", "Cidade", "Admissão", "Demissão", "Status"}
    missing = required - set(df.columns)
    if missing:
        print(f"Colunas faltando na origem: {sorted(missing)}")
        sys.exit(1)

    total = replace_people_rows(df)
    fonte = "CSV (Databricks)" if args.csv else "HTML local"
    print(f"Carregados {total} registros em people_rows (fonte: {fonte}).")


if __name__ == "__main__":
    main()
