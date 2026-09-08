"""Loading and business rules for the Turnover Comercial dashboard."""

from __future__ import annotations

import calendar
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_SOURCE = PROJECT_ROOT / "assets" / "painel_cidade_CLT_media_turnover.html"

# Cidade -> UF. A base atual (assets/painel_cidade_CLT_media_turnover.html) não traz
# o estado por colaborador, então este mapeamento é inferido manualmente a partir do
# nome da cidade — vale conferir caso a empresa opere em uma cidade homônima de outro
# estado. "Lotes" não é uma cidade (é um segmento de negócio) e fica sem UF.
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


def load_source_data() -> dict[str, Any]:
    """Read the embedded row-level payload and derive every filter option from it."""
    source = HTML_SOURCE.read_text(encoding="utf-8")
    payload = _extract_json(source, "PAYLOAD", "ALL_ROWS")
    raw_rows = _extract_json(source, "ALL_ROWS", "CIDADES")

    rows = pd.DataFrame(raw_rows)
    rows["Grupo"] = rows["Cargo Atual2"].map(CARGO_GROUP_MAP).fillna(rows["Cargo Atual2"])

    cidades = sorted(rows["Cidade"].unique())
    grupos_presentes = set(rows["Grupo"])
    grupos = [g for g in CARGO_GROUP_ORDER if g in grupos_presentes] + sorted(grupos_presentes - set(CARGO_GROUP_ORDER))

    return {
        "rows": rows,
        "cidades": cidades,
        "grupos": grupos,
        "labels": payload["meses_labels"],
        "keys": payload["meses_keys"],
    }


def _month_bounds(key: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    period = pd.Period(key, freq="M")
    return period.start_time, period.end_time


def build_monthly_series(rows: pd.DataFrame, keys: list[str]) -> dict[str, list[float]]:
    """Compute headcount/admissions/terminations per month directly from row-level dates,
    then derive turnover real e indicador legado com a mesma regra de negócio de sempre."""
    if rows.empty:
        zeros = [0] * len(keys)
        return {"at": zeros, "adm": zeros, "dem": zeros, "turn": [0.0] * len(keys), "turn_dem_ant": [0.0] * len(keys)}

    admissao = pd.to_datetime(rows["Admissão"], errors="coerce")
    demissao = pd.to_datetime(rows["Demissão"].replace("", None), errors="coerce")

    at, adm, dem = [], [], []
    for key in keys:
        start, end = _month_bounds(key)
        adm.append(int(((admissao >= start) & (admissao <= end)).sum()))
        dem.append(int(((demissao >= start) & (demissao <= end)).sum()))
        at.append(int(((admissao <= end) & (demissao.isna() | (demissao > end))).sum()))

    turn, turn_dem_ant, previous_at = [], [], None
    for current_at, admissions, terminations in zip(at, adm, dem):
        at_start = current_at if previous_at is None else previous_at
        average_headcount = (at_start + current_at) / 2
        turn.append(round((admissions + terminations) / 2 / average_headcount * 100, 2) if average_headcount else 0.0)
        turn_dem_ant.append(round(terminations / at_start * 100, 2) if at_start else 0.0)
        previous_at = current_at
    return {"at": at, "adm": adm, "dem": dem, "turn": turn, "turn_dem_ant": turn_dem_ant}


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
    return pd.DataFrame({"Mês": source_data["labels"][start_index:end_index + 1], "Chave": source_data["keys"][start_index:end_index + 1], "Ativos": series["at"][start_index:end_index + 1], "Admissões": series["adm"][start_index:end_index + 1], "Desligamentos": series["dem"][start_index:end_index + 1], "Turnover real (%)": series["turn"][start_index:end_index + 1], "Legado (%)": series["turn_dem_ant"][start_index:end_index + 1]})


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


def retention_curve(rows: pd.DataFrame, keys: list[str], labels: list[str], last_data_key: str) -> pd.DataFrame:
    """Para cada mês de admissão (coorte), % da leva ainda ativa após 3/6/12 meses.

    Um horizonte só é calculado quando já se passou tempo suficiente (o mês de checagem
    precisa estar dentro do último mês com dados na base); caso contrário fica ausente
    (NaN) em vez de ser tratado como 0%.
    """
    columns = ["Chave", "Mês", "Tamanho", "3m_pct", "3m_n", "6m_pct", "6m_n", "12m_pct", "12m_n"]
    if rows.empty or last_data_key not in keys:
        return pd.DataFrame(columns=columns)

    admissao = pd.to_datetime(rows["Admissão"], errors="coerce")
    demissao = pd.to_datetime(rows["Demissão"].replace("", None), errors="coerce")
    _, last_end = _month_bounds(last_data_key)

    records = []
    for i, key in enumerate(keys):
        start, end = _month_bounds(key)
        cohort_mask = (admissao >= start) & (admissao <= end)
        size = int(cohort_mask.sum())
        if size == 0:
            continue
        cohort_dem = demissao[cohort_mask]
        record: dict[str, Any] = {"Chave": key, "Mês": labels[i], "Tamanho": size}
        for months_after, prefix in ((3, "3m"), (6, "6m"), (12, "12m")):
            target_idx = i + months_after
            if target_idx >= len(keys) or _month_bounds(keys[target_idx])[1] > last_end:
                record[f"{prefix}_pct"] = None
                record[f"{prefix}_n"] = None
                continue
            _, target_end = _month_bounds(keys[target_idx])
            still_active = int((cohort_dem.isna() | (cohort_dem > target_end)).sum())
            record[f"{prefix}_pct"] = round(still_active / size * 100, 1)
            record[f"{prefix}_n"] = still_active
        records.append(record)

    return pd.DataFrame(records, columns=columns)


def weighted_retention(df: pd.DataFrame, prefix: str) -> float | None:
    """Média ponderada (pelo tamanho da coorte) da retenção em um horizonte, entre coortes elegíveis."""
    valid = df.dropna(subset=[f"{prefix}_pct"])
    total = valid["Tamanho"].sum()
    if total == 0:
        return None
    return float(valid[f"{prefix}_n"].sum() / total * 100)
