"""Roda o relatório comercial direto no SQL Warehouse do Databricks — login
interativo via OAuth (abre o navegador para você logar, sem precisar de
PAT/token) — e substitui a base inteira em `people_rows` no Neon.

Uso:
    python scripts/sync_from_databricks.py                   # até o último mês fechado
    python scripts/sync_from_databricks.py --ref 2026-09-25  # até a data informada

Pré-requisito em `.streamlit/secrets.toml` -> [databricks]:
    server_hostname, http_path (connection details do SQL Warehouse) e
    gestor_referencia (nome do gestor usado no ranking de reportes — fica só
    no secrets.toml, nunca no código, porque o repositório é público).

Nunca imprime dado de colaborador (nome, cidade, datas) — só contagens.
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from databricks import sql

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _neon_people import SECRETS_PATH, EmptySourceError, engine, load_secrets, replace_people_rows  # noqa: E402

DIRETORIA = "Diretoria Comercial"

# A descrição do departamento sempre termina com essa etiqueta genérica de equipe
# (ex.: "Uberlândia (Faz. Campo Alegre 1) - Equipe Vendas Comercial") — tirada do
# nome porque já repete em quase todo departamento comercial e não ajuda a
# diferenciar um do outro no relatório.
_SUFIXO_EQUIPE_VENDAS = re.compile(r"\s*-\s*Equipe(?:\s+de)?\s+Vendas(?:\s+Comercial)?\s*$", re.IGNORECASE)


def _formatar_setor(codigo: object, nome: object) -> str:
    """Monta "<código> - <nome>" (ex.: "48326 - Uberlândia (Faz. Campo Alegre 1)"),
    tirando o sufixo genérico de equipe do nome antes de juntar com o código."""
    codigo = "" if pd.isna(codigo) else str(codigo).strip()
    nome = "" if pd.isna(nome) else _SUFIXO_EQUIPE_VENDAS.sub("", str(nome)).strip()
    if codigo and nome:
        return f"{codigo} - {nome}"
    return codigo or nome


def _query(ref_str: str, gestor_referencia: str, ccs: list[int]) -> str:
    gestor_sql = gestor_referencia.replace("'", "''")
    ccs_sql = ", ".join(str(int(c)) for c in ccs) or "NULL"
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
  f.departamento AS CodDepartamento,
  l.cidade AS Cidade,
  f.id_funcionario AS Registro,
  f.nome_funcionario AS Nome,
  f.descricao_cargo AS `Cargo Atual`,
  COALESCE(f.data_admissao_grupo, f.data_admissao) AS Admissao,
  f.data_desligamento AS Demissao,
  COALESCE(rb1.nome_funcionario, rb2.nome_funcionario, rb3.nome_funcionario, rb4.nome_funcionario, rb5.nome_funcionario) AS Gestor,
  COALESCE(rb1.descricao_cargo, rb2.descricao_cargo, rb3.descricao_cargo, rb4.descricao_cargo, rb5.descricao_cargo) AS `Cargo Gestor`,
  'Ativo' AS Status,
  NULL AS `Tipo Desligamento`,
  f.descricao_posicao AS Posicao,
  f.descricao_local AS DescLocal
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
       OR TRY_CAST(f.departamento AS BIGINT) IN ({ccs_sql})
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
  f.descricao_departamento, f.departamento, l.cidade, f.id_funcionario, f.nome_funcionario, f.descricao_cargo,
  COALESCE(f.data_admissao_grupo, f.data_admissao), f.data_desligamento,
  d.nome_gestor AS Gestor,
  d.descricao_reporta_se AS `Cargo Gestor`,
  'Ativo',
  NULL AS `Tipo Desligamento`,
  f.descricao_posicao,
  f.descricao_local
FROM rh.gold.fato_funcionario_inativo f
LEFT JOIN enterprise.data.dim_local l ON f.descricao_local = l.descricao_local
LEFT JOIN rh.silver.oracle_hcm_pit_adm_00003_desligados_relatorio d
  ON f.id_funcionario = d.numero_pessoa
  AND f.data_desligamento = d.data_desligamento
WHERE (f.nome_diretoria = 'Diretoria Comercial'
       OR TRY_CAST(f.departamento AS BIGINT) IN ({ccs_sql})
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
  f.descricao_departamento, f.departamento, l.cidade, f.id_funcionario, f.nome_funcionario, f.descricao_cargo,
  COALESCE(f.data_admissao_grupo, f.data_admissao), f.data_desligamento,
  d.nome_gestor AS Gestor,
  d.descricao_reporta_se AS `Cargo Gestor`,
  'Desligado',
  COALESCE(d.tipo_desligamento,
    CASE
      WHEN f.acao = 'Pedido de Demissão' THEN 'Voluntário'
      WHEN f.acao IN ('Demissão sem Justa Causa', 'Demissão por Justa Causa',
                       'Término do Contrato a Termo', 'Morte') THEN 'Involuntário'
      WHEN f.acao = 'Acordo entre Empregado e Empregador' THEN 'Acordo'
      WHEN f.acao = 'Transferência Global' THEN 'Transferência'
      ELSE f.acao
    END
  ) AS `Tipo Desligamento`,
  f.descricao_posicao,
  f.descricao_local
FROM rh.gold.fato_funcionario_inativo f
LEFT JOIN enterprise.data.dim_local l ON f.descricao_local = l.descricao_local
LEFT JOIN rh.silver.oracle_hcm_pit_adm_00003_desligados_relatorio d
  ON f.id_funcionario = d.numero_pessoa
  AND f.data_desligamento = d.data_desligamento
WHERE (f.nome_diretoria = 'Diretoria Comercial'
       OR TRY_CAST(f.departamento AS BIGINT) IN ({ccs_sql})
       OR (f.nome_diretoria IS NULL
           AND (LOWER(f.descricao_departamento) LIKE '%vendas comercial%'
                OR LOWER(f.descricao_departamento) LIKE '%equipe vendas%'
                OR LOWER(f.descricao_departamento) LIKE '%equipe de vendas%'
                OR LOWER(f.descricao_cargo) LIKE '%vendas%'
                OR LOWER(f.descricao_cargo) LIKE '%comercial%')))
  AND f.data_desligamento <= '{ref_str}'

ORDER BY Status, Setor, Nome
"""


def _ref_date_from_args() -> date:
    """`--ref AAAA-MM-DD` força a data de referência (ex.: incluir o mês corrente,
    ainda parcial). Sem o argumento, usa o último dia do mês fechado anterior."""
    if "--ref" in sys.argv:
        idx = sys.argv.index("--ref")
        try:
            return date.fromisoformat(sys.argv[idx + 1])
        except (IndexError, ValueError):
            print("Uso: python scripts/sync_from_databricks.py [--ref AAAA-MM-DD]")
            sys.exit(1)
    return date.today().replace(day=1) - timedelta(days=1)


def _mapeamento_oficial() -> tuple[dict, dict]:
    """Mapeamento oficial da Central (core.mapeamento_diretoria + _especial, planilha
    _neon/mapeamento/Mapeamento Diretoria.xlsx) — o mesmo de todos os painéis."""
    with engine().connect() as conn:
        cc_map = {str(cc): (d, a) for cc, d, a in conn.exec_driver_sql(
            "SELECT centro_de_custo, diretoria, area FROM core.mapeamento_diretoria")}
        especiais: dict = {}
        for cc, tipo, chave, d, a in conn.exec_driver_sql(
                "SELECT centro_de_custo, tipo, chave, diretoria, area FROM core.mapeamento_diretoria_especial"):
            especiais.setdefault(str(cc), {})[(tipo, str(chave))] = (d, a)
    return cc_map, especiais


def _cidades_da_central() -> dict[str, str]:
    """descricao_local -> cidade em CAIXA ALTA sem acento (mesmo formato do dim_local do
    Databricks), a partir de core.local_cidade (tabela de locais da Central, completada com o
    IBGE). Cobre lojas novas que o enterprise.data.dim_local ainda não tem."""
    import unicodedata
    def bruto(c: str) -> str:
        return "".join(ch for ch in unicodedata.normalize("NFKD", c) if not unicodedata.combining(ch)).upper()
    with engine().connect() as conn:
        return {d: bruto(c) for d, c in conn.exec_driver_sql(
            "SELECT descricao_local, cidade FROM core.local_cidade WHERE cidade IS NOT NULL AND cidade <> ''")}


def _resolver(cc, posicao, registro, cc_map: dict, especiais: dict) -> tuple[str | None, str | None]:
    """Diretoria/área pelo mapeamento oficial: regra por pessoa, por cargo da posição, depois o CC."""
    cc = None if cc is None or pd.isna(cc) else str(int(float(cc))) if str(cc).replace(".", "").isdigit() else str(cc).strip()
    esp = especiais.get(cc, {}) if cc else {}
    r = esp.get(("by_person", str(registro)))
    if r is None:
        pos = posicao if isinstance(posicao, str) else ""
        r = esp.get(("by_position", pos.rsplit(" - ", 1)[0].strip()))
    if r is None and cc:
        r = cc_map.get(cc)
    return r if r else (None, None)


def fetch_from_databricks() -> pd.DataFrame:
    cfg = load_secrets()["databricks"]
    gestor_referencia = cfg.get("gestor_referencia", "").strip()
    if not gestor_referencia:
        print("Preencha 'gestor_referencia' em .streamlit/secrets.toml -> [databricks].")
        sys.exit(1)

    ref_str = _ref_date_from_args().strftime("%Y-%m-%d")
    cc_map, especiais = _mapeamento_oficial()
    ccs = sorted({int(cc) for cc, (d, _) in cc_map.items() if d == DIRETORIA and cc.isdigit()}
                 | {int(cc) for cc, regras in especiais.items() if cc.isdigit() and any(d == DIRETORIA for d, _ in regras.values())})

    print(f"Conectando ao Databricks via OAuth (o navegador deve abrir para login)... referência: {ref_str}")
    connection = sql.connect(
        server_hostname=cfg["server_hostname"],
        http_path=cfg["http_path"],
        auth_type="databricks-oauth",
    )
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(_query(ref_str, gestor_referencia, ccs))
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=columns)

    # Recorte pelo mapeamento oficial (29/09/2026): entra toda a Diretoria Comercial — vendas,
    # repasses, marketing, financeiro comercial, performance... — e sai quem a gold marcava
    # como comercial mas o mapeamento põe em outra diretoria. A área vai para a coluna `area`.
    res = [_resolver(c, p, r, cc_map, especiais) for c, p, r in zip(df["CodDepartamento"], df["Posicao"], df["Registro"])]
    # cidade: dim_local do Databricks; se vier vazia (loja nova), a tabela de locais da Central
    sem_cidade = df["Cidade"].isna() | (df["Cidade"].astype(str).str.strip() == "")
    if sem_cidade.any():
        central = _cidades_da_central()
        df.loc[sem_cidade, "Cidade"] = df.loc[sem_cidade, "DescLocal"].map(central)
        print(f"Cidade completada pela tabela de locais da Central: {int(df.loc[sem_cidade, 'Cidade'].notna().sum())} "
              f"de {int(sem_cidade.sum())} linha(s) sem cidade no Databricks.")
    df["Diretoria"] = [d for d, _ in res]
    df["Area"] = [a for _, a in res]
    antes = len(df)
    df = df[df["Diretoria"] == DIRETORIA].copy()
    print(f"Mapeamento oficial: {len(df)} de {antes} linha(s) na {DIRETORIA} "
          f"({antes - len(df)} de outras diretorias ou sem mapeamento ficaram de fora).")
    return df


def main() -> None:
    if not SECRETS_PATH.exists():
        print(f"Não encontrei {SECRETS_PATH}.")
        sys.exit(1)

    df = fetch_from_databricks()
    print(f"Query retornou {len(df)} linha(s) do Databricks.")
    df = df.rename(columns={"Cargo Atual": "Cargo Atual2", "Admissao": "Admissão", "Demissao": "Demissão"})
    df["Setor"] = [_formatar_setor(cod, nome) for cod, nome in zip(df["CodDepartamento"], df["Setor"])]

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
