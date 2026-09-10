"""Roda o relatório comercial direto no SQL Warehouse do Databricks — login
interativo via OAuth (abre o navegador para você logar, sem precisar de
PAT/token) — e substitui a base inteira em `people_rows` no Neon.

Uso:
    python scripts/sync_from_databricks.py

Pré-requisito em `.streamlit/secrets.toml` -> [databricks]:
    server_hostname, http_path (connection details do SQL Warehouse) e
    gestor_referencia (nome do gestor usado no ranking de reportes — fica só
    no secrets.toml, nunca no código, porque o repositório é público).

Nunca imprime dado de colaborador (nome, cidade, datas) — só contagens.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from databricks import sql

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _neon_people import SECRETS_PATH, EmptySourceError, load_secrets, replace_people_rows  # noqa: E402


def _query(ref_str: str, gestor_referencia: str) -> str:
    gestor_sql = gestor_referencia.replace("'", "''")
    return f"""
WITH reportes_breno AS (
  SELECT id_funcionario, nome_funcionario, descricao_cargo
  FROM rh.gold.fato_funcionario_ativo
  WHERE nome_gestor = '{gestor_sql}'
),
hierarquia AS (
  SELECT id_funcionario, CAST(id_gestor AS STRING) AS id_gestor
  FROM rh.gold.fato_funcionario_ativo
)

SELECT
  f.descricao_departamento AS Setor,
  l.cidade AS Cidade,
  f.id_funcionario AS Registro,
  f.nome_funcionario AS Nome,
  f.descricao_cargo AS `Cargo Atual`,
  COALESCE(f.data_admissao_grupo, f.data_admissao) AS Admissao,
  f.data_desligamento AS Demissao,
  COALESCE(rb1.nome_funcionario, rb2.nome_funcionario, rb3.nome_funcionario, rb4.nome_funcionario, rb5.nome_funcionario) AS Gestor,
  COALESCE(rb1.descricao_cargo, rb2.descricao_cargo, rb3.descricao_cargo, rb4.descricao_cargo, rb5.descricao_cargo) AS `Cargo Gestor`,
  'Ativo' AS Status,
  NULL AS `Tipo Desligamento`
FROM rh.gold.fato_funcionario_ativo f
LEFT JOIN enterprise.data.dim_local l ON f.descricao_local = l.descricao_local
LEFT JOIN reportes_breno rb1 ON f.id_funcionario = rb1.id_funcionario
LEFT JOIN reportes_breno rb2 ON CAST(f.id_gestor AS STRING) = rb2.id_funcionario
LEFT JOIN hierarquia h2 ON CAST(f.id_gestor AS STRING) = h2.id_funcionario
LEFT JOIN reportes_breno rb3 ON h2.id_gestor = rb3.id_funcionario
LEFT JOIN hierarquia h3 ON h2.id_gestor = h3.id_funcionario
LEFT JOIN reportes_breno rb4 ON h3.id_gestor = rb4.id_funcionario
LEFT JOIN hierarquia h4 ON h3.id_gestor = h4.id_funcionario
LEFT JOIN reportes_breno rb5 ON h4.id_gestor = rb5.id_funcionario
WHERE (f.nome_diretoria = 'Diretoria Comercial'
       OR (f.nome_diretoria IS NULL
           AND (LOWER(f.descricao_departamento) LIKE '%vendas comercial%'
                OR LOWER(f.descricao_departamento) LIKE '%equipe vendas%'
                OR LOWER(f.descricao_departamento) LIKE '%equipe de vendas%'
                OR LOWER(f.descricao_cargo) LIKE '%vendas%'
                OR LOWER(f.descricao_cargo) LIKE '%comercial%')))
  AND COALESCE(f.data_admissao_grupo, f.data_admissao) <= '{ref_str}'
  AND (f.data_desligamento IS NULL OR f.data_desligamento > '{ref_str}')

UNION ALL

SELECT
  f.descricao_departamento, l.cidade, f.id_funcionario, f.nome_funcionario, f.descricao_cargo,
  COALESCE(f.data_admissao_grupo, f.data_admissao), f.data_desligamento,
  NULL AS Gestor, NULL AS `Cargo Gestor`,
  'Ativo',
  NULL AS `Tipo Desligamento`
FROM rh.gold.fato_funcionario_inativo f
LEFT JOIN enterprise.data.dim_local l ON f.descricao_local = l.descricao_local
WHERE (f.nome_diretoria = 'Diretoria Comercial'
       OR (f.nome_diretoria IS NULL
           AND (LOWER(f.descricao_departamento) LIKE '%vendas comercial%'
                OR LOWER(f.descricao_departamento) LIKE '%equipe vendas%'
                OR LOWER(f.descricao_departamento) LIKE '%equipe de vendas%'
                OR LOWER(f.descricao_cargo) LIKE '%vendas%'
                OR LOWER(f.descricao_cargo) LIKE '%comercial%')))
  AND COALESCE(f.data_admissao_grupo, f.data_admissao) <= '{ref_str}'
  AND f.data_desligamento > '{ref_str}'

UNION ALL

SELECT
  f.descricao_departamento, l.cidade, f.id_funcionario, f.nome_funcionario, f.descricao_cargo,
  COALESCE(f.data_admissao_grupo, f.data_admissao), f.data_desligamento,
  NULL AS Gestor, NULL AS `Cargo Gestor`,
  'Desligado',
  CASE
    WHEN f.acao = 'Pedido de Demissão' THEN 'Voluntário'
    WHEN f.acao IN ('Demissão sem Justa Causa', 'Demissão por Justa Causa',
                     'Término do Contrato a Termo', 'Morte') THEN 'Involuntário'
    WHEN f.acao = 'Acordo entre Empregado e Empregador' THEN 'Acordo'
    WHEN f.acao = 'Transferência Global' THEN 'Transferência'
    ELSE f.acao
  END AS `Tipo Desligamento`
FROM rh.gold.fato_funcionario_inativo f
LEFT JOIN enterprise.data.dim_local l ON f.descricao_local = l.descricao_local
WHERE (f.nome_diretoria = 'Diretoria Comercial'
       OR (f.nome_diretoria IS NULL
           AND (LOWER(f.descricao_departamento) LIKE '%vendas comercial%'
                OR LOWER(f.descricao_departamento) LIKE '%equipe vendas%'
                OR LOWER(f.descricao_departamento) LIKE '%equipe de vendas%'
                OR LOWER(f.descricao_cargo) LIKE '%vendas%'
                OR LOWER(f.descricao_cargo) LIKE '%comercial%')))
  AND f.data_desligamento <= '{ref_str}'

ORDER BY Status, Setor, Nome
"""


def fetch_from_databricks() -> pd.DataFrame:
    cfg = load_secrets()["databricks"]
    gestor_referencia = cfg.get("gestor_referencia", "").strip()
    if not gestor_referencia:
        print("Preencha 'gestor_referencia' em .streamlit/secrets.toml -> [databricks].")
        sys.exit(1)

    today = date.today()
    ref_date = today.replace(day=1) - timedelta(days=1)
    ref_str = ref_date.strftime("%Y-%m-%d")

    print(f"Conectando ao Databricks via OAuth (o navegador deve abrir para login)... referência: {ref_str}")
    connection = sql.connect(
        server_hostname=cfg["server_hostname"],
        http_path=cfg["http_path"],
        auth_type="databricks-oauth",
    )
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(_query(ref_str, gestor_referencia))
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=columns)


def main() -> None:
    if not SECRETS_PATH.exists():
        print(f"Não encontrei {SECRETS_PATH}.")
        sys.exit(1)

    df = fetch_from_databricks()
    print(f"Query retornou {len(df)} linha(s) do Databricks.")
    df = df.rename(columns={"Cargo Atual": "Cargo Atual2", "Admissao": "Admissão", "Demissao": "Demissão"})

    n_ativos = int((df["Status"] == "Ativo").sum()) if not df.empty else 0
    n_desligados = int((df["Status"] == "Desligado").sum()) if not df.empty else 0
    n_voluntario = int((df["Tipo Desligamento"] == "Voluntário").sum()) if not df.empty else 0
    n_involuntario = int((df["Tipo Desligamento"] == "Involuntário").sum()) if not df.empty else 0
    try:
        total = replace_people_rows(df)
    except EmptySourceError as exc:
        print(f"ABORTADO: {exc}")
        print("Confira a query/permissões no Databricks antes de rodar de novo — people_rows não foi tocada.")
        sys.exit(1)
    print(f"Carregados {total} registros em people_rows (fonte: Databricks). Ativos: {n_ativos} | Desligados: {n_desligados}")
    print(f"Desligamentos por tipo — Voluntário: {n_voluntario} | Involuntário: {n_involuntario} | Outros/sem classificação: {n_desligados - n_voluntario - n_involuntario}")


if __name__ == "__main__":
    main()
