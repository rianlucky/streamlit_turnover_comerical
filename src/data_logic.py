"""Loading and business rules for the Turnover Comercial dashboard."""

from __future__ import annotations

import calendar
import json
import re
import unicodedata
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


# Cidade -> UF (chave já em forma "bonita", com acento — ver CITY_RAW_TO_DISPLAY).
# A base local não traz o estado por colaborador, então este mapeamento é inferido
# manualmente a partir do nome da cidade — vale conferir caso a empresa opere em uma
# cidade homônima de outro estado. "Lotes"/"Repasses" não são cidades (são segmentos
# de negócio) e ficam sem UF.
CITY_UF = {
    "Arapongas": "PR", "Araraquara": "SP", "Araçatuba": "SP", "Assis": "SP",
    "Assis Chateaubriand": "PR", "Avaré": "SP", "Barretos": "SP", "Bauru": "SP",
    "Botucatu": "SP", "Brasília": "DF", "Bálsamo": "SP", "Campo Grande": "MS",
    "Campo Mourão": "PR", "Catanduva": "SP", "Cianorte": "PR", "Cuiabá": "MT",
    "Diamantino": "MT", "Itapetininga": "SP", "Ituiutaba": "MG", "Leme": "SP",
    "Lins": "SP", "Londrina": "PR", "Lucas do Rio Verde": "MT", "Marília": "SP",
    "Nova Marilândia": "MT", "Ourinhos": "SP", "Palotina": "PR", "Paranavaí": "PR",
    "Piratininga": "SP", "Ponta Grossa": "PR", "Presidente Prudente": "SP",
    "Primavera do Leste": "MT", "Ribeirão Preto": "SP", "São José do Rio Preto": "SP",
    "Rondonópolis": "MT", "Sinop": "MT", "Sorriso": "MT", "São Carlos": "SP",
    "Tatuí": "SP", "Taubaté": "SP", "Uberlândia": "MG", "Votuporanga": "SP",
    "São Paulo": "SP",
}

# O Databricks devolve a cidade em CAIXA ALTA e sem acento (ex.: "SAO JOSE DO RIO
# PRETO") — mapeia pro nome "bonito" (usado em CITY_UF/CITY_COORDS e exibido na
# tela). Cidade fora daqui (não mapeada ainda) cai no fallback _title_case_pt.
CITY_RAW_TO_DISPLAY = {
    "ARAPONGAS": "Arapongas", "ARARAQUARA": "Araraquara", "ARACATUBA": "Araçatuba",
    "ASSIS": "Assis", "ASSIS CHATEAUBRIAND": "Assis Chateaubriand", "AVARE": "Avaré",
    "BARRETOS": "Barretos", "BAURU": "Bauru", "BOTUCATU": "Botucatu",
    "BRASILIA": "Brasília", "BALSAMO": "Bálsamo", "CAMPO GRANDE": "Campo Grande",
    "CAMPO MOURAO": "Campo Mourão", "CATANDUVA": "Catanduva", "CIANORTE": "Cianorte",
    "CUIABA": "Cuiabá", "DIAMANTINO": "Diamantino", "ITAPETININGA": "Itapetininga",
    "ITUIUTABA": "Ituiutaba", "LEME": "Leme", "LINS": "Lins", "LONDRINA": "Londrina",
    "LUCAS DO RIO VERDE": "Lucas do Rio Verde", "MARILIA": "Marília",
    "NOVA MARILANDIA": "Nova Marilândia", "OURINHOS": "Ourinhos", "PALOTINA": "Palotina",
    "PARANAVAI": "Paranavaí", "PIRATININGA": "Piratininga", "PONTA GROSSA": "Ponta Grossa",
    "PRESIDENTE PRUDENTE": "Presidente Prudente", "PRIMAVERA DO LESTE": "Primavera do Leste",
    "RIBEIRAO PRETO": "Ribeirão Preto", "RONDONOPOLIS": "Rondonópolis", "SINOP": "Sinop",
    "SORRISO": "Sorriso", "SAO CARLOS": "São Carlos",
    "SAO JOSE DO RIO PRETO": "São José do Rio Preto", "TATUI": "Tatuí",
    "TAUBATE": "Taubaté", "UBERLANDIA": "Uberlândia", "VOTUPORANGA": "Votuporanga",
    "SAO PAULO": "São Paulo",
}

# Coordenadas aproximadas (centro da cidade) para o mapa de concentração de mão de
# obra — não precisa de precisão de endereço, só de posicionar a bolha no mapa.
CITY_COORDS = {
    "Arapongas": (-23.4192, -51.4256), "Araraquara": (-21.7845, -48.1781),
    "Araçatuba": (-21.2089, -50.4328), "Assis": (-22.6619, -50.4116),
    "Assis Chateaubriand": (-24.4102, -53.5405), "Avaré": (-23.0996, -48.9250),
    "Barretos": (-20.5572, -48.5683), "Bauru": (-22.3246, -49.0871),
    "Botucatu": (-22.8858, -48.4450), "Brasília": (-15.7939, -47.8828),
    "Bálsamo": (-20.7364, -49.5872), "Campo Grande": (-20.4697, -54.6201),
    "Campo Mourão": (-24.0453, -52.3778), "Catanduva": (-21.1377, -48.9728),
    "Cianorte": (-23.6620, -52.6053), "Cuiabá": (-15.6014, -56.0979),
    "Diamantino": (-14.4093, -56.4467), "Itapetininga": (-23.5917, -48.0533),
    "Ituiutaba": (-18.9678, -49.4650), "Leme": (-22.1875, -47.3900),
    "Lins": (-21.6789, -49.7425), "Londrina": (-23.3103, -51.1628),
    "Lucas do Rio Verde": (-13.0508, -55.9147), "Marília": (-22.2139, -49.9458),
    "Nova Marilândia": (-14.4189, -56.9500), "Ourinhos": (-22.9787, -49.8700),
    "Palotina": (-24.2836, -53.8400), "Paranavaí": (-23.0728, -52.4650),
    "Piratininga": (-22.4142, -49.1414), "Ponta Grossa": (-25.0916, -50.1668),
    "Presidente Prudente": (-22.1256, -51.3889), "Primavera do Leste": (-15.5589, -54.2967),
    "Ribeirão Preto": (-21.1775, -47.8103), "Rondonópolis": (-16.4706, -54.6356),
    "Sinop": (-11.8642, -55.5028), "Sorriso": (-12.5453, -55.7217),
    "São Carlos": (-22.0087, -47.8909), "São José do Rio Preto": (-20.8113, -49.3758),
    "Tatuí": (-23.3553, -47.8567), "Taubaté": (-23.0264, -45.5553),
    "Uberlândia": (-18.9186, -48.2772), "Votuporanga": (-20.4237, -49.9756),
    "São Paulo": (-23.5505, -46.6333),
}

_LOWERCASE_PT_WORDS = {"de", "do", "da", "dos", "das", "e"}


def _title_case_pt(value: str) -> str:
    """Fallback para cidade sem entrada em CITY_RAW_TO_DISPLAY: Title Case simples,
    mantendo preposições comuns (de/do/da/dos/das/e) em minúsculo. Sem acento — só
    evita ficar em CAIXA ALTA até alguém adicionar a cidade nova ao mapeamento."""
    words = value.lower().split(" ")
    return " ".join(w if w in _LOWERCASE_PT_WORDS else w.capitalize() for w in words)


def _display_city(cidade: str) -> str:
    if not cidade:
        return cidade
    return CITY_RAW_TO_DISPLAY.get(cidade, _title_case_pt(cidade))


def city_label(cidade: str) -> str:
    """"Cidade/UF" para o dropdown; cidades sem UF mapeada (ex.: "Lotes") aparecem sem sufixo."""
    uf = CITY_UF.get(cidade)
    return f"{cidade}/{uf}" if uf else cidade


def city_concentration(rows: pd.DataFrame) -> pd.DataFrame:
    """Headcount ativo por cidade, com coordenadas — para o mapa de concentração de
    mão de obra. `rows` já deve vir filtrado (cidade/cargo/gestor/período); ignora
    "Lotes"/"Repasses" e qualquer cidade sem coordenada conhecida."""
    ativos = rows[rows["Status"] == "Ativo"]
    counts = ativos.groupby("Cidade").size().rename("Ativos").reset_index()
    coords = counts["Cidade"].map(CITY_COORDS)
    counts["Lat"] = coords.map(lambda c: c[0] if isinstance(c, tuple) else None)
    counts["Lon"] = coords.map(lambda c: c[1] if isinstance(c, tuple) else None)
    return counts.dropna(subset=["Lat", "Lon"])


# A base tem os mesmos cargos em variações de senioridade (Junior/Pleno/Sênior) — o
# dash não distingue nível, então agrupa todas sob o cargo "base" antes de comparar
# com CARGO_GROUP_MAP. Cobre também grafias sem acento vistas na base (ex.: "Senior").
_SENIORITY_SUFFIXES = (" Júnior", " Junior", " Pleno", " Sênior", " Senior")

# Typos/plural inconsistente ou nomes alternativos para o mesmo cargo, confirmados
# pelo usuário (2026-09-09) como sendo o mesmo papel.
_CARGO_ALIASES = {
    "Gerente de Lotes Comerciais": "Gerente de Lotes Comercial",
    "Gerente Comercial": "Gerente de Vendas",
    "Coordenador Comercial": "Coordenador de Vendas",
    "Coordenadora de Vendas": "Coordenador de Vendas",
    "Supervisora Comercial": "Supervisor de Vendas",
}


def _normalize_cargo(cargo: str) -> str:
    for suffix in _SENIORITY_SUFFIXES:
        if cargo.endswith(suffix):
            cargo = cargo[: -len(suffix)]
            break
    return _CARGO_ALIASES.get(cargo, cargo)


# Cargo (já normalizado por _normalize_cargo) -> grupo de filtro, para os cargos de vendas e
# repasses. Desde 29/09/2026 o painel cobre a Diretoria Comercial inteira (recorte pelo
# mapeamento oficial, no sync): cargo fora desta lista entra pelo nível do título
# (_grupo_por_nivel) — ex.: "Analista de Marketing" -> "Analistas".
CARGO_GROUP_MAP = {
    "Executivo Comercial": "Executivos",
    "Executivo de Repasses": "Executivos",
    "Gerente de Vendas": "Gerente",
    "Gerente de Lotes Comercial": "Gerente",
    "Gerente de Repasses": "Gerente",
    "Coordenador de Vendas": "Coordenador",
    "Coordenador de Repasses": "Coordenador",
    "Supervisor de Vendas": "Supervisor",
    "Supervisor de Repasses": "Supervisor",
    "Analista de Parcerias": "Analistas Parcerias",
    "Analista de Suporte de Vendas": "Analistas",
    "Analista de Vendas": "Analistas",
    "Analista de Lotes Comerciais": "Analistas",
    "Analista de Repasses": "Analistas",
    "Analista de Treinamento": "Analistas",
    "Assistente de Vendas": "Assistentes",
    "Assistente de Repasses": "Assistentes",
    "Auxiliar de Vendas": "Auxiliar",
    "Auxiliar de Repasses": "Auxiliar",
}
CARGO_GROUP_ORDER = ["Auxiliar", "Assistentes", "Analistas", "Analistas Parcerias", "Especialistas", "Supervisor",
                     "Coordenador", "Gerente", "Executivos", "Outros"]

# Primeira palavra do título -> grupo, para cargos fora do CARGO_GROUP_MAP.
_NIVEL_POR_PREFIXO = {
    "Auxiliar": "Auxiliar", "Assistente": "Assistentes", "Analista": "Analistas", "Especialista": "Especialistas",
    "Supervisor": "Supervisor", "Supervisora": "Supervisor", "Coordenador": "Coordenador", "Coordenadora": "Coordenador",
    "Gerente": "Gerente", "Executivo": "Executivos", "Executiva": "Executivos",
}


def _grupo_por_nivel(cargo: str) -> str:
    return CARGO_GROUP_MAP.get(cargo) or _NIVEL_POR_PREFIXO.get(cargo.split(" ", 1)[0], "Outros")


# Equipe: segmento de negócio (separado de Cidade/Grupo) — ver load_source_data(). As três
# primeiras vêm do cargo de vendas; as demais, das outras áreas da Diretoria Comercial.
EQUIPE_ORDER = ["Vendas UH", "Lotes Comerciais", "Repasses", "Gerência Comercial", "Marketing e Relacionamento",
                "Financeiro Comercial", "Trade e Lojas", "Performance Comercial", "Apoio às Vendas"]

# Área oficial (mapeamento da Central) -> Equipe, para quem não é cargo de vendas/repasses.
# As áreas "Vendas (região)" juntam os CCs das lojas: quem está lá sem cargo de vendas e sem
# palavra-chave abaixo (ex.: motorista, manutenção) fica em "Apoio às Vendas".
_EQUIPE_POR_AREA = {
    "Marketing, Comunicação Interna e Relacionamento com Cliente": "Marketing e Relacionamento",
    "Financeiro Comercial": "Financeiro Comercial", "Performance Comercial": "Performance Comercial",
    "Gerência Comercial": "Gerência Comercial", "Repasses": "Repasses", "Lotes Comerciais": "Lotes Comerciais",
}
# Palavra no cargo -> Equipe (vale antes da área: o financeiro comercial e o trade ficam nos CCs das lojas)
_EQUIPE_POR_CARGO = [
    ("financeiro comercial", "Financeiro Comercial"),
    ("marketing", "Marketing e Relacionamento"), ("comunicação", "Marketing e Relacionamento"),
    ("relacionamento", "Marketing e Relacionamento"), ("áudio visual", "Marketing e Relacionamento"),
    ("trade", "Trade e Lojas"), ("infraestrutura de lojas", "Trade e Lojas"),
    ("performance", "Performance Comercial"), ("estratégico", "Performance Comercial"),
    ("inteligência de dados", "Performance Comercial"),
]


def _equipe_outras_areas(cargo: str, area: str | None) -> str:
    c = cargo.lower()
    for chave, equipe in _EQUIPE_POR_CARGO:
        if chave in c:
            return equipe
    return _EQUIPE_POR_AREA.get(area or "", "Apoio às Vendas")


def _extract_json(source: str, declaration: str, next_declaration: str) -> Any:
    pattern = rf"const {declaration}\s*=\s*(.*?)\s*;\s*const {next_declaration}"
    match = re.search(pattern, source, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Não foi possível localizar {declaration} no HTML de origem.")
    return json.loads(match.group(1))


# `perm_meses` NÃO entra aqui de propósito — ver OBSOLETO.md. Continua sendo
# gravada em people_rows (histórico), só não é mais lida por lugar nenhum do app.
PEOPLE_ROWS_QUERY = """
SELECT
    registro AS "Registro",
    nome AS "Nome",
    cargo_atual2 AS "Cargo Atual2",
    cidade AS "Cidade",
    admissao AS "Admissão",
    demissao AS "Demissão",
    status AS "Status",
    gestor AS "Gestor",
    tipo_desligamento AS "Tipo Desligamento",
    setor AS "Setor",
    area AS "Area"
FROM turnover.people_rows
"""


def _years_ago(years: int) -> date:
    """Hoje menos N anos — usado pro corte de desligamento e pro início do eixo de
    meses, pra andarem sozinhos com o tempo em vez de precisar de revisão manual."""
    today = date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        # 29/02 caindo num ano não bissexto N anos atrás.
        return today.replace(year=today.year - years, day=28)


def _month_range(start: str | None = None, months_ahead: int = 5) -> tuple[list[str], list[str]]:
    """Eixo de meses dos gráficos — independe da fonte de dados (por isso não vem mais
    do Databricks/Neon): por padrão começa 10 anos atrás (mesma janela do corte de
    desligamento) e vai até `months_ahead` meses à frente do mês atual, dando folga
    no eixo para dados dos próximos meses."""
    if start is None:
        start = _years_ago(10).strftime("%Y-%m")
    end = pd.Timestamp.now().to_period("M") + months_ahead
    periods = pd.period_range(start=start, end=end, freq="M")
    keys = [str(p) for p in periods]
    labels = [f"{MONTH_ABBR_EN[p.month - 1]}/{p.strftime('%y')}" for p in periods]
    return keys, labels


def _termination_cutoff() -> str:
    """Corte de 10 anos (pedido do usuário, 2026-09-09): desligados até essa data
    saem da análise (ruído histórico demais antigo). Não afeta ativos (não têm
    Demissão). Calculado a cada chamada (não é mais uma constante fixa), pra não
    precisar de revisão manual daqui uns anos — sempre "hoje - 10 anos"."""
    return _years_ago(10).isoformat()


def _read_synced_at() -> "pd.Timestamp | None":
    """Quando `people_rows` foi carregada pela última vez (scripts/_neon_people.py
    grava isso em `sync_meta` a cada load_people_data.py/sync_from_databricks.py).
    None se a tabela ainda não existir (deploy novo, antes do primeiro sync) ou
    estiver vazia — tratado na tela como "sem registro de sincronização"."""
    conn = st.connection("sql")
    try:
        df = conn.query("SELECT synced_at FROM turnover.sync_meta WHERE id = 1", ttl=60)
    except Exception:
        return None
    return None if df.empty else df.iloc[0]["synced_at"]


def load_source_data() -> dict[str, Any]:
    """Read the row-level base from Postgres (Neon, table `people_rows`) and derive
    every filter option from it. `people_rows` é carregada por `scripts/load_people_data.py`
    (a partir do HTML local ou de um export do Databricks — ver README)."""
    conn = st.connection("sql")
    rows = conn.query(PEOPLE_ROWS_QUERY, ttl=600)
    rows = rows[(rows["Demissão"] == "") | (rows["Demissão"] > _termination_cutoff())].copy()
    rows["Cargo Atual2"] = rows["Cargo Atual2"].map(_normalize_cargo)
    # Diretoria Comercial inteira (o sync já recorta pelo mapeamento oficial): nenhum cargo é
    # descartado; "Outros" sinaliza título sem nível reconhecível (aparece no rodapé da barra).
    rows["Grupo"] = rows["Cargo Atual2"].map(_grupo_por_nivel)
    cargos_nao_mapeados = int((rows["Grupo"] == "Outros").sum())

    # Databricks devolve a cidade em CAIXA ALTA sem acento — normaliza pro nome
    # "bonito" (usado em CITY_UF/CITY_COORDS e exibido na tela). Cidade sempre é o
    # local real do colaborador agora — o segmento de negócio (Lotes/Repasses) vive
    # à parte, no campo Equipe (ver abaixo). Conta quem caiu no fallback de título
    # (_title_case_pt) — sinal de cidade nova ainda não cadastrada em CITY_RAW_TO_DISPLAY.
    cidade_bruta = rows["Cidade"]
    cidades_nao_mapeadas = int(((cidade_bruta != "") & ~cidade_bruta.isin(CITY_RAW_TO_DISPLAY)).sum())
    rows["Cidade"] = cidade_bruta.map(_display_city)

    # Equipe: segmento de negócio, separado de Cidade/Grupo. Regra pedida pelo
    # usuário (2026-09-10) — default "Vendas UH" pra quem não é Lotes/Repasses.
    rows["Equipe"] = "Vendas UH"
    rows.loc[rows["Cargo Atual2"].str.contains("Lotes"), "Equipe"] = "Lotes Comerciais"
    rows.loc[rows["Cargo Atual2"].str.contains("Repasses"), "Equipe"] = "Repasses"
    # Demais áreas da Diretoria Comercial (29/09/2026): cargo fora dos de vendas/repasses.
    outras = ~rows["Cargo Atual2"].isin(CARGO_GROUP_MAP)
    rows.loc[outras, "Equipe"] = [_equipe_outras_areas(c, a) for c, a in zip(rows.loc[outras, "Cargo Atual2"], rows.loc[outras, "Area"])]
    # A base antiga (HTML) já marcava estes 2 Registros como "Lotes" mesmo com cargo
    # formal de Vendas — mantém a mesma classificação de equipe na base real (Databricks).
    LOTES_REGISTRO_OVERRIDE = {2649, 2505}
    rows.loc[rows["Registro"].isin(LOTES_REGISTRO_OVERRIDE), "Equipe"] = "Lotes Comerciais"

    cidades = sorted(rows["Cidade"].unique())
    grupos_presentes = set(rows["Grupo"])
    grupos = [g for g in CARGO_GROUP_ORDER if g in grupos_presentes] + sorted(grupos_presentes - set(CARGO_GROUP_ORDER))
    gestores = sorted(g for g in rows["Gestor"].dropna().unique() if g)
    equipes_presentes = set(rows["Equipe"])
    equipes = [e for e in EQUIPE_ORDER if e in equipes_presentes] + sorted(equipes_presentes - set(EQUIPE_ORDER))

    keys, labels = _month_range()

    return {
        "rows": rows,
        "cidades": cidades,
        "grupos": grupos,
        "gestores": gestores,
        "equipes": equipes,
        "cargos_nao_mapeados": cargos_nao_mapeados,
        "cidades_nao_mapeadas": cidades_nao_mapeadas,
        "synced_at": _read_synced_at(),
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
    (ver ``charts.comparativo_turnover`` / página "Comparativo Turnover"), e
    ``voluntario``/``involuntario``/``turn_voluntario``: desligamentos por tipo (campo
    ``Tipo Desligamento``, vem do Databricks) e o turnover voluntário — mesma fórmula do
    turnover real (÷ efetivo médio do mês), mas só com desligamentos voluntários no
    numerador (sem admissões, já que a métrica mede especificamente saída por vontade
    própria, não movimento geral)."""
    if rows.empty:
        zeros = [0] * len(keys)
        zeros_f = [0.0] * len(keys)
        return {
            "at": zeros, "adm": zeros, "dem": zeros,
            "turn": zeros_f, "turn_do": zeros_f, "turn_dem_ant": zeros_f,
            "voluntario": zeros, "involuntario": zeros, "turn_voluntario": zeros_f,
        }

    admissao = pd.to_datetime(rows["Admissão"], errors="coerce")
    demissao = pd.to_datetime(rows["Demissão"].replace("", None), errors="coerce")
    tipo = rows["Tipo Desligamento"]
    is_voluntario = tipo == "Voluntário"
    is_involuntario = tipo == "Involuntário"

    at, adm, dem, voluntario, involuntario = [], [], [], [], []
    for key in keys:
        start, end = _month_bounds(key)
        in_month = (demissao >= start) & (demissao <= end)
        adm.append(int(((admissao >= start) & (admissao <= end)).sum()))
        dem.append(int(in_month.sum()))
        at.append(int(((admissao <= end) & (demissao.isna() | (demissao > end))).sum()))
        voluntario.append(int((in_month & is_voluntario).sum()))
        involuntario.append(int((in_month & is_involuntario).sum()))

    turn, turn_do, turn_dem_ant, turn_voluntario, previous_at = [], [], [], [], None
    for current_at, admissions, terminations, vol in zip(at, adm, dem, voluntario):
        at_start = current_at if previous_at is None else previous_at
        average_headcount = (at_start + current_at) / 2
        turn.append(round((admissions + terminations) / 2 / average_headcount * 100, 2) if average_headcount else 0.0)
        turn_do.append(round((admissions + terminations) / 2 / at_start * 100, 2) if at_start else 0.0)
        turn_dem_ant.append(round(terminations / at_start * 100, 2) if at_start else 0.0)
        turn_voluntario.append(round(vol / average_headcount * 100, 2) if average_headcount else 0.0)
        previous_at = current_at
    return {
        "at": at, "adm": adm, "dem": dem,
        "turn": turn, "turn_do": turn_do, "turn_dem_ant": turn_dem_ant,
        "voluntario": voluntario, "involuntario": involuntario, "turn_voluntario": turn_voluntario,
    }


def filter_cidade_grupo(rows: pd.DataFrame, cidades: list[str], grupos: list[str], gestores: list[str], equipes: list[str]) -> pd.DataFrame:
    """Only the Cidade/Grupo/Gestor/Equipe filters (empty lists = todos) — shared by charts, table and indicators."""
    if cidades:
        rows = rows[rows["Cidade"].isin(cidades)]
    if grupos:
        rows = rows[rows["Grupo"].isin(grupos)]
    if gestores:
        rows = rows[rows["Gestor"].isin(gestores)]
    if equipes:
        rows = rows[rows["Equipe"].isin(equipes)]
    return rows


def get_series(source_data: dict[str, Any], cidades: list[str], grupos: list[str], gestores: list[str], equipes: list[str]) -> dict[str, list[float]]:
    """Monthly series for the selected filters (empty lists = todos)."""
    filtered = filter_cidade_grupo(source_data["rows"], cidades, grupos, gestores, equipes)
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
    return pd.DataFrame({
        "Mês": source_data["labels"][start_index:end_index + 1],
        "Chave": source_data["keys"][start_index:end_index + 1],
        "Ativos": series["at"][start_index:end_index + 1],
        "Admissões": series["adm"][start_index:end_index + 1],
        "Desligamentos": series["dem"][start_index:end_index + 1],
        "Turnover real (%)": series["turn"][start_index:end_index + 1],
        "Turnover D.O. (%)": series["turn_do"][start_index:end_index + 1],
        "Legado (%)": series["turn_dem_ant"][start_index:end_index + 1],
        "Desligamentos Voluntários": series["voluntario"][start_index:end_index + 1],
        "Desligamentos Involuntários": series["involuntario"][start_index:end_index + 1],
        "Turnover Voluntário (%)": series["turn_voluntario"][start_index:end_index + 1],
    })


def dimension_ranking(source_data: dict[str, Any], dimension: str, start: str, end: str) -> pd.DataFrame:
    """Turnover médio e total de desligamentos no período, por valor de `dimension`
    ("Cidade", "Grupo" ou "Gestor") — cada valor tratado como um filtro isolado (mesma
    lógica de build_monthly_series). Usada pela página de Ranking (Top 5)."""
    rows = source_data["rows"]
    values = sorted(v for v in rows[dimension].dropna().unique() if v)

    records = []
    for value in values:
        subset = rows[rows[dimension] == value]
        series = build_monthly_series(subset, source_data["keys"])
        period = select_period(source_data, series, start, end)
        records.append({
            dimension: value,
            "Turnover médio (%)": mean_nonzero(period["Turnover real (%)"]),
            "Desligamentos": int(period["Desligamentos"].sum()),
        })
    return pd.DataFrame(records)


def _strip_accents(value: str) -> str:
    """Remove acentos (NFKD + descarta marcas de combinação) — usado na busca da
    tabela pra "aracatuba" achar "Araçatuba" mesmo sem cedilha (a Cidade passou a
    vir com acento depois da normalização de nome — ver _display_city)."""
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def filter_people(rows: pd.DataFrame, cidades: list[str], grupos: list[str], gestores: list[str], equipes: list[str], start: str, end: str, search: str, status_selected: list[str] | None = None) -> pd.DataFrame:
    filtered = filter_cidade_grupo(rows, cidades, grupos, gestores, equipes)
    admissions = filtered["Admissão"].fillna("")
    terminations = filtered["Demissão"].replace("", "2099-12-31").fillna("2099-12-31")
    filtered = filtered[(admissions <= f"{end}-31") & (terminations >= f"{start}-01")]
    if status_selected:
        filtered = filtered[filtered["Status"].isin(status_selected)]
    query = _strip_accents(search.strip().lower())
    if query:
        mask = (
            filtered["Nome"].str.lower().map(_strip_accents).str.contains(query, na=False)
            | filtered["Cargo Atual2"].str.lower().map(_strip_accents).str.contains(query, na=False)
            | filtered["Cidade"].str.lower().map(_strip_accents).str.contains(query, na=False)
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
