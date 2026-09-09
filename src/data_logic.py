"""Loading and business rules for the Turnover Comercial dashboard."""

from __future__ import annotations

import calendar
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"

MONTH_ABBR_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _find_html_source() -> Path:
    """Locate the local source HTML in assets/ — not versioned (contém dado real de
    colaborador), então o nome do arquivo não fica hardcoded nem aparece no repositório."""
    matches = sorted(ASSETS_DIR.glob("*.html"))
    if not matches:
        raise FileNotFoundError(f"Nenhum arquivo .html encontrado em {ASSETS_DIR} — ele não é versionado, precisa existir localmente.")
    return matches[0]


# Cidade -> UF. A base local não traz o estado por colaborador, então este mapeamento
# é inferido manualmente a partir do nome da cidade — vale conferir caso a empresa
# opere em uma cidade homônima de outro estado. "Lotes" não é uma cidade (é um
# segmento de negócio) e fica sem UF.
CITY_UF = {
    "Arapongas": "PR", "Araraquara": "SP", "Araçatuba": "SP", "Assis": "SP",
    "Assis Chateaubriand": "PR", "Avaré": "SP", "Barretos": "SP", "Bauru": "SP",
    "Botucatu": "SP", "Brasília": "DF", "Bálsamo": "SP", "Campo Grande": "MS",
    "Campo Mourão": "PR", "Catanduva": "SP", "Cianorte": "PR", "Cuiabá": "MT",
    "Diamantino": "MT", "Itapetininga": "SP", "Ituiutaba": "MG", "Leme": "SP",
    "Lins": "SP", "Londrina": "PR", "Lucas do Rio Verde": "MT", "Marília": "SP",
    "Nova Marilândia": "MT", "Ourinhos": "SP", "Palotina": "PR", "Paranavaí": "PR",
    "Piratininga": "SP", "Ponta Grossa": "PR", "Presidente Prudente": "SP",
    "Primavera do Leste": "MT", "Ribeirão Preto": "SP", "Rio Preto": "SP",
    "Rondonópolis": "MT", "Sinop": "MT", "Sorriso": "MT", "São Carlos": "SP",
    "Tatuí": "SP", "Taubaté": "SP", "Uberlândia": "MG", "Votuporanga": "SP",
}


def city_label(cidade: str) -> str:
    """"Cidade/UF" para o dropdown; cidades sem UF mapeada (ex.: "Lotes") aparecem sem sufixo."""
    uf = CITY_UF.get(cidade)
    return f"{cidade}/{uf}" if uf else cidade


# Cargo Atual2 (título de RH) -> grupo de filtro solicitado. Cobre os títulos observados
# na base atual e variações citadas para cobrir futuras cargas de dados.
CARGO_GROUP_MAP = {
    "Gerente de Vendas": "Gerente",
    "Gerente de Lotes Comercial": "Gerente",
    "Gerente Comercial": "Gerente",
    "Coordenador de Vendas": "Coordenador",
    "Coordenador Comercial": "Coordenador",
    "Supervisor de Vendas": "Supervisor",
    "Analista de Parcerias": "Analistas Parcerias",
    "Analista de Suporte de Vendas": "Analistas",
    "Analista de Vendas Junior": "Analistas",
    "Analista de Lotes Comerciais": "Analistas",
    "Assistente de Vendas": "Assistentes",
    "Auxiliar de Vendas": "Auxiliar",
}
CARGO_GROUP_ORDER = ["Auxiliar", "Assistentes", "Analistas", "Analistas Parcerias", "Supervisor", "Coordenador", "Gerente"]


def _extract_json(source: str, declaration: str, next_declaration: str) -> Any:
    pattern = rf"const {declaration}\s*=\s*(.*?)\s*;\s*const {next_declaration}"
    match = re.search(pattern, source, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Não foi possível localizar {declaration} no HTML de origem.")
    return json.loads(match.group(1))


PEOPLE_ROWS_QUERY = """
SELECT
    registro AS "Registro",
    nome AS "Nome",
    cargo_atual2 AS "Cargo Atual2",
    cidade AS "Cidade",
    admissao AS "Admissão",
    demissao AS "Demissão",
    status AS "Status",
    perm_meses AS "Perm_meses"
FROM people_rows
"""


def _month_range(start: str = "2015-04", months_ahead: int = 5) -> tuple[list[str], list[str]]:
    """Eixo de meses dos gráficos — independe da fonte de dados (por isso não vem mais
    do Databricks/Neon): começa fixo em `start` e vai até `months_ahead` meses à frente
    do mês atual, dando folga no eixo para dados dos próximos meses."""
    end = pd.Timestamp.now().to_period("M") + months_ahead
    periods = pd.period_range(start=start, end=end, freq="M")
    keys = [str(p) for p in periods]
    labels = [f"{MONTH_ABBR_EN[p.month - 1]}/{p.strftime('%y')}" for p in periods]
    return keys, labels


def load_source_data() -> dict[str, Any]:
    """Read the row-level base from Postgres (Neon, table `people_rows`) and derive
    every filter option from it. `people_rows` é carregada por `scripts/load_people_data.py`
    (a partir do HTML local ou de um export do Databricks — ver README)."""
    conn = st.connection("sql")
    rows = conn.query(PEOPLE_ROWS_QUERY, ttl=600)
    rows["Grupo"] = rows["Cargo Atual2"].map(CARGO_GROUP_MAP).fillna(rows["Cargo Atual2"])

    cidades = sorted(rows["Cidade"].unique())
    grupos_presentes = set(rows["Grupo"])
    grupos = [g for g in CARGO_GROUP_ORDER if g in grupos_presentes] + sorted(grupos_presentes - set(CARGO_GROUP_ORDER))

    keys, labels = _month_range()

    return {
        "rows": rows,
        "cidades": cidades,
        "grupos": grupos,
        "labels": labels,
        "keys": keys,
    }


def _month_bounds(key: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    period = pd.Period(key, freq="M")
    return period.start_time, period.end_time


def build_monthly_series(rows: pd.DataFrame, keys: list[str]) -> dict[str, list[float]]:
    """Compute headcount/admissions/terminations per month directly from row-level dates,
    then derive turnover real e indicador legado com a mesma regra de negócio de sempre.

    Também calcula ``turn_do``: a variante do turnover real usada pelo D.O., que divide
    pelo efetivo do último dia do mês anterior em vez da média entre início e fim do mês
    (ver ``charts.comparativo_turnover`` / página "Comparativo Turnover")."""
    if rows.empty:
        zeros = [0] * len(keys)
        return {"at": zeros, "adm": zeros, "dem": zeros, "turn": [0.0] * len(keys), "turn_do": [0.0] * len(keys), "turn_dem_ant": [0.0] * len(keys)}

    admissao = pd.to_datetime(rows["Admissão"], errors="coerce")
    demissao = pd.to_datetime(rows["Demissão"].replace("", None), errors="coerce")

    at, adm, dem = [], [], []
    for key in keys:
        start, end = _month_bounds(key)
        adm.append(int(((admissao >= start) & (admissao <= end)).sum()))
        dem.append(int(((demissao >= start) & (demissao <= end)).sum()))
        at.append(int(((admissao <= end) & (demissao.isna() | (demissao > end))).sum()))

    turn, turn_do, turn_dem_ant, previous_at = [], [], [], None
    for current_at, admissions, terminations in zip(at, adm, dem):
        at_start = current_at if previous_at is None else previous_at
        average_headcount = (at_start + current_at) / 2
        turn.append(round((admissions + terminations) / 2 / average_headcount * 100, 2) if average_headcount else 0.0)
        turn_do.append(round((admissions + terminations) / 2 / at_start * 100, 2) if at_start else 0.0)
        turn_dem_ant.append(round(terminations / at_start * 100, 2) if at_start else 0.0)
        previous_at = current_at
    return {"at": at, "adm": adm, "dem": dem, "turn": turn, "turn_do": turn_do, "turn_dem_ant": turn_dem_ant}


def filter_cidade_grupo(rows: pd.DataFrame, cidades: list[str], grupos: list[str]) -> pd.DataFrame:
    """Only the Cidade/Grupo filters (empty lists = every city/grupo) — shared by charts, table and indicators."""
    if cidades:
        rows = rows[rows["Cidade"].isin(cidades)]
    if grupos:
        rows = rows[rows["Grupo"].isin(grupos)]
    return rows


def get_series(source_data: dict[str, Any], cidades: list[str], grupos: list[str]) -> dict[str, list[float]]:
    """Monthly series for the selected filters (empty lists = every city/grupo)."""
    filtered = filter_cidade_grupo(source_data["rows"], cidades, grupos)
    return build_monthly_series(filtered, source_data["keys"])


def last_active_month(rows: pd.DataFrame) -> str:
    """Último mês (YYYY-MM) com pelo menos uma admissão ou um desligamento na base."""
    admissao = pd.to_datetime(rows["Admissão"], errors="coerce")
    demissao = pd.to_datetime(rows["Demissão"].replace("", None), errors="coerce")
    candidates = pd.concat([admissao, demissao]).dropna()
    if candidates.empty:
        return date.today().strftime("%Y-%m")
    return candidates.max().strftime("%Y-%m")


def select_period(source_data: dict[str, Any], series: dict[str, list[float]], start: str, end: str) -> pd.DataFrame:
    start_index, end_index = max(0, source_data["keys"].index(start)), min(len(source_data["keys"]) - 1, source_data["keys"].index(end))
    return pd.DataFrame({"Mês": source_data["labels"][start_index:end_index + 1], "Chave": source_data["keys"][start_index:end_index + 1], "Ativos": series["at"][start_index:end_index + 1], "Admissões": series["adm"][start_index:end_index + 1], "Desligamentos": series["dem"][start_index:end_index + 1], "Turnover real (%)": series["turn"][start_index:end_index + 1], "Turnover D.O. (%)": series["turn_do"][start_index:end_index + 1], "Legado (%)": series["turn_dem_ant"][start_index:end_index + 1]})


def filter_people(rows: pd.DataFrame, cidades: list[str], grupos: list[str], start: str, end: str, search: str, status_selected: list[str] | None = None) -> pd.DataFrame:
    filtered = filter_cidade_grupo(rows, cidades, grupos)
    admissions = filtered["Admissão"].fillna("")
    terminations = filtered["Demissão"].replace("", "2099-12-31").fillna("2099-12-31")
    filtered = filtered[(admissions <= f"{end}-31") & (terminations >= f"{start}-01")]
    if status_selected:
        filtered = filtered[filtered["Status"].isin(status_selected)]
    query = search.strip().lower()
    if query:
        mask = (
            filtered["Nome"].str.lower().str.contains(query, na=False)
            | filtered["Cargo Atual2"].str.lower().str.contains(query, na=False)
            | filtered["Cidade"].str.lower().str.contains(query, na=False)
            | filtered["Registro"].astype(str).str.contains(query, na=False)
        )
        filtered = filtered[mask]
    return filtered


def mean_nonzero(values: pd.Series) -> float:
    nonzero = values[values > 0]
    return float(nonzero.mean()) if not nonzero.empty else 0.0


def _tenure_parts(start: date, end: date) -> tuple[int, int, int]:
    years = end.year - start.year
    months = end.month - start.month
    days = end.day - start.day
    if days < 0:
        months -= 1
        prev_month = end.month - 1 or 12
        prev_year = end.year if end.month > 1 else end.year - 1
        days += calendar.monthrange(prev_year, prev_month)[1]
    if months < 0:
        months += 12
        years -= 1
    return years, months, days


def humanize_tenure(admissao: str, demissao: str) -> tuple[str, int]:
    """Retorna ("X anos e X meses" / "X anos" / "X meses" / "X dias", total_dias) — o total
    de dias serve de chave numérica para ordenação e para colorir por faixa."""
    start = datetime.strptime(admissao[:10], "%Y-%m-%d").date()
    end = datetime.strptime(demissao[:10], "%Y-%m-%d").date() if demissao else date.today()
    total_days = max(0, (end - start).days)
    years, months, days = _tenure_parts(start, end)
    if years > 0 and months > 0:
        text = f"{years} {'ano' if years == 1 else 'anos'} e {months} {'mês' if months == 1 else 'meses'}"
    elif years > 0:
        text = f"{years} {'ano' if years == 1 else 'anos'}"
    elif months > 0:
        text = f"{months} {'mês' if months == 1 else 'meses'}"
    else:
        text = f"{days} {'dia' if days == 1 else 'dias'}"
    return text, total_days


def tenure_class(total_days: int) -> str:
    if total_days < 91:
        return "perm-low"
    if total_days < 365:
        return "perm-mid"
    return "perm-ok"


def humanize_days(total_days: float) -> str:
    """Como humanize_tenure, mas para uma média agregada (dias -> anos/meses aproximados)."""
    days_int = max(0, int(round(total_days)))
    years, remainder = divmod(days_int, 365)
    months, days = divmod(remainder, 30)
    if years > 0 and months > 0:
        return f"{years} {'ano' if years == 1 else 'anos'} e {months} {'mês' if months == 1 else 'meses'}"
    if years > 0:
        return f"{years} {'ano' if years == 1 else 'anos'}"
    if months > 0:
        return f"{months} {'mês' if months == 1 else 'meses'}"
    return f"{days} {'dia' if days == 1 else 'dias'}"
