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


# A base tem os mesmos cargos em variações de senioridade (Junior/Pleno/Sênior) — o
# dash não distingue nível, então agrupa todas sob o cargo "base" antes de comparar
# com CARGO_GROUP_MAP. Cobre também grafias sem acento vistas na base (ex.: "Senior").
_SENIORITY_SUFFIXES = (" Júnior", " Junior", " Pleno", " Sênior", " Senior")

# Typos/inconsistência de plural observados na base para o mesmo cargo.
_CARGO_ALIASES = {
    "Gerente de Lotes Comerciais": "Gerente de Lotes Comercial",
}


def _normalize_cargo(cargo: str) -> str:
    for suffix in _SENIORITY_SUFFIXES:
        if cargo.endswith(suffix):
            cargo = cargo[: -len(suffix)]
            break
    return _CARGO_ALIASES.get(cargo, cargo)


# Cargo (já normalizado por _normalize_cargo) -> grupo de filtro. Única lista de
# cargos que o dash usa — qualquer título fora daqui é descartado em
# load_source_data() (a query do Databricks é ampla o suficiente pra trazer gente
# de outras áreas, ex.: Marketing, Financeiro Comercial, RH).
CARGO_GROUP_MAP = {
    "Gerente de Vendas": "Gerente",
    "Gerente de Lotes Comercial": "Gerente",
    "Gerente de Repasses": "Gerente",
    "Coordenador de Vendas": "Coordenador",
    "Coordenador de Repasses": "Coordenador",
    "Supervisor de Vendas": "Supervisor",
    "Analista de Parcerias": "Analistas Parcerias",
    "Analista de Suporte de Vendas": "Analistas",
    "Analista de Vendas": "Analistas",
    "Analista de Lotes Comerciais": "Analistas",
    "Analista de Repasses": "Analistas",
    "Assistente de Vendas": "Assistentes",
    "Assistente de Repasses": "Assistentes",
    "Auxiliar de Vendas": "Auxiliar",
    "Auxiliar de Repasses": "Auxiliar",
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
    perm_meses AS "Perm_meses",
    gestor AS "Gestor"
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


# Corte de 10 anos pedido pelo usuário (2026-09-09): desligados até essa data saem da
# análise (ruído histórico demais antigo). Não afeta ativos (não têm Demissão).
TERMINATION_CUTOFF = "2015-12-31"


def load_source_data() -> dict[str, Any]:
    """Read the row-level base from Postgres (Neon, table `people_rows`) and derive
    every filter option from it. `people_rows` é carregada por `scripts/load_people_data.py`
    (a partir do HTML local ou de um export do Databricks — ver README)."""
    conn = st.connection("sql")
    rows = conn.query(PEOPLE_ROWS_QUERY, ttl=600)
    rows = rows[(rows["Demissão"] == "") | (rows["Demissão"] > TERMINATION_CUTOFF)].copy()
    rows["Cargo Atual2"] = rows["Cargo Atual2"].map(_normalize_cargo)
    rows = rows[rows["Cargo Atual2"].isin(CARGO_GROUP_MAP)].copy()
    rows["Grupo"] = rows["Cargo Atual2"].map(CARGO_GROUP_MAP)

    cidades = sorted(rows["Cidade"].unique())
    grupos_presentes = set(rows["Grupo"])
    grupos = [g for g in CARGO_GROUP_ORDER if g in grupos_presentes] + sorted(grupos_presentes - set(CARGO_GROUP_ORDER))
    gestores = sorted(g for g in rows["Gestor"].dropna().unique() if g)

    keys, labels = _month_range()

    return {
        "rows": rows,
        "cidades": cidades,
        "grupos": grupos,
        "gestores": gestores,
        "labels": labels,
        "keys": keys,
    }


def _month_bounds(key: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    period = pd.Period(key, freq="M")
    return period.start_time, period.end_time


def month_start_end(key: str) -> tuple[date, date]:
    """Como `_month_bounds`, mas em `date` puro — usado pelo `st.date_input` do filtro
    de período (que precisa de `date`, não `Timestamp`)."""
    start, end = _month_bounds(key)
    return start.date(), end.date()


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


def filter_cidade_grupo(rows: pd.DataFrame, cidades: list[str], grupos: list[str], gestores: list[str]) -> pd.DataFrame:
    """Only the Cidade/Grupo/Gestor filters (empty lists = every city/grupo/gestor) — shared by charts, table and indicators."""
    if cidades:
        rows = rows[rows["Cidade"].isin(cidades)]
    if grupos:
        rows = rows[rows["Grupo"].isin(grupos)]
    if gestores:
        rows = rows[rows["Gestor"].isin(gestores)]
    return rows


def get_series(source_data: dict[str, Any], cidades: list[str], grupos: list[str], gestores: list[str]) -> dict[str, list[float]]:
    """Monthly series for the selected filters (empty lists = every city/grupo/gestor)."""
    filtered = filter_cidade_grupo(source_data["rows"], cidades, grupos, gestores)
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


def filter_people(rows: pd.DataFrame, cidades: list[str], grupos: list[str], gestores: list[str], start: str, end: str, search: str, status_selected: list[str] | None = None) -> pd.DataFrame:
    filtered = filter_cidade_grupo(rows, cidades, grupos, gestores)
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
