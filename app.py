from __future__ import annotations

import streamlit as st

from src import charts
from src.auth import init_db
from src.auth_ui import render_logout_button, require_login
from src.components import card_close, card_open, chart_card, kpi_row, render_table, stat_pair
from src.data_logic import (
    city_label,
    filter_cidade_grupo,
    filter_people,
    get_series,
    humanize_days,
    humanize_tenure,
    last_active_month,
    load_source_data,
    mean_nonzero,
    retention_curve,
    select_period,
    weighted_retention,
)
from src.styles import inject_css

st.set_page_config(page_title="Turnover Comercial", page_icon=":material/insights:", layout="wide")
inject_css()

init_db()
require_login()

PAGE_SIZE = 20
SORT_COLUMNS = {
    "Admissão": "Admissão",
    "Demissão": "Demissão",
    "Permanência": "TenureDays",
    "Nome": "Nome",
    "Cargo": "Cargo Atual2",
    "Cidade": "Cidade",
    "ID": "Registro",
    "Status": "Status",
}
STATUS_VALUES = ["Ativo", "Desligado"]


@st.cache_data
def get_data():
    return load_source_data()


source_data = get_data()
label_by_key = dict(zip(source_data["keys"], source_data["labels"]))

# Padrão: últimos 12 meses contando do último mês com admissão ou desligamento na base
# (não necessariamente o mês corrente — a base pode não ter sido atualizada ainda).
last_key = last_active_month(source_data["rows"])
if last_key not in source_data["keys"]:
    last_key = source_data["keys"][-1]
default_end_idx = source_data["keys"].index(last_key)
default_start_idx = max(0, default_end_idx - 11)

header_title, header_logout = st.columns([6, 1])
with header_title:
    st.html('<div class="page-title"><h1>Movimentação de Pessoas</h1><p>Análise de admissões, demissões, turnover e headcount por cidade e cargo</p></div>')
with header_logout:
    st.write("")
    render_logout_button()

with st.container(border=True):
    filters = st.columns([1.3, 1.5, 2.0, 1.3])
    with filters[0]:
        cidades = st.multiselect("Cidade", source_data["cidades"], placeholder="Global (todas)", format_func=city_label)
    with filters[1]:
        grupos = st.multiselect("Cargo", source_data["grupos"], placeholder="Todos")
    with filters[2]:
        period_cols = st.columns(2)
        with period_cols[0]:
            start = st.selectbox("De", source_data["keys"], index=default_start_idx, format_func=lambda key: label_by_key[key])
        with period_cols[1]:
            end = st.selectbox("Até", source_data["keys"], index=default_end_idx, format_func=lambda key: label_by_key[key])
    with filters[3]:
        status_selected = st.multiselect("Status", STATUS_VALUES, placeholder="Ambos")

if start > end:
    st.error("O mês inicial precisa ser anterior ou igual ao mês final.")
    st.stop()

series = get_series(source_data, cidades, grupos)
period = select_period(source_data, series, start, end)
admissions_total, terminations_total = int(period["Admissões"].sum()), int(period["Desligamentos"].sum())
active_final = int(period["Ativos"].iloc[-1]) if not period.empty else 0
turnover_media = mean_nonzero(period["Turnover real (%)"])
legado_media = mean_nonzero(period["Legado (%)"])
saldo_total = admissions_total - terminations_total

kpi_row(
    {
        "ativos": f"{active_final:,}".replace(",", "."),
        "admissoes": f"{admissions_total:,}".replace(",", "."),
        "desligamentos": f"{terminations_total:,}".replace(",", "."),
        "turnover": f"{turnover_media:.2f}%",
        "legado": f"{legado_media:.2f}%",
        "saldo": f"{'+' if saldo_total >= 0 else ''}{saldo_total:,}".replace(",", "."),
    },
    saldo_positive=saldo_total >= 0,
)

row_one = st.columns(2)
with row_one[0]:
    chart_card(
        charts.admissoes_demissoes(period),
        "Admissões × Demissões",
        "Entradas e saídas mensais",
        [("#0d9488", "Admissões", 1), ("#dc2626", "Demissões", 1)],
    )
with row_one[1]:
    chart_card(
        charts.turnover_real(period, turnover_media),
        "Turnover Real Mensal (%)",
        "(Admissões + Demissões) / 2 ÷ Efetivo médio do mês",
        [("#d97706", "Turnover %", 1), ("#d97706", "Média do período", 0.35)],
    )

row_two = st.columns(2)
with row_two[0]:
    chart_card(
        charts.headcount_ativo(period),
        "Headcount Ativo",
        "Colaboradores ativos ao fim de cada mês",
        [("#2563eb", "Ativos", 1)],
    )
with row_two[1]:
    chart_card(
        charts.saldo_liquido(period),
        "Saldo Líquido Mensal",
        "Admissões − Demissões",
        [("#16a34a", "Positivo", 1), ("#dc2626", "Negativo", 1)],
    )

chart_card(
    charts.turnover_legado(period, legado_media),
    "Desligamentos ÷ Headcount do Mês Anterior (indicador legado)",
    'NÃO é o turnover — ignora admissões e não usa efetivo médio. Mantido apenas para referência histórica; veja o "Turnover Real" acima para a métrica correta.',
    [("#64748b", "Indicador legado %", 1), ("#64748b", "Média do período", 0.35)],
)

# ── Indicadores complementares ────────────────────────────────────────────
# Usam cidade/cargo/período do filtro atual, mas ignoram o filtro de Status —
# o objetivo aqui é justamente comparar quem ficou com quem saiu.
population = filter_people(source_data["rows"], cidades, grupos, start, end, "", [])
population_days = [humanize_tenure(row["Admissão"], row["Demissão"])[1] for _, row in population.iterrows()]
population = population.assign(_Dias=population_days)
dias_ativos = population.loc[population["Status"] == "Ativo", "_Dias"]
dias_desligados = population.loc[population["Status"] != "Ativo", "_Dias"]

card_open(
    "Permanência Média: Ativos × Desligados",
    "Tempo de casa médio de quem está ativo comparado a quem foi desligado, dentro do filtro atual de cidade, cargo e período",
)
stat_pair(
    [
        ("blue", humanize_days(dias_ativos.mean()) if not dias_ativos.empty else "—", f"Ativos ({len(dias_ativos)})"),
        ("red", humanize_days(dias_desligados.mean()) if not dias_desligados.empty else "—", f"Desligados ({len(dias_desligados)})"),
    ]
)
card_close()

cohort_rows = filter_cidade_grupo(source_data["rows"], cidades, grupos)
retention = retention_curve(cohort_rows, source_data["keys"], source_data["labels"], last_key)
v3, v6, v12 = weighted_retention(retention, "3m"), weighted_retention(retention, "6m"), weighted_retention(retention, "12m")

card_open(
    "Curva de Retenção por Coorte de Admissão",
    "% de cada leva mensal de admitidos que segue ativa após 3, 6 e 12 meses (cidade/cargo do filtro atual; não considera o período nem o status selecionados)",
)
stat_pair(
    [
        ("blue", f"{v3:.1f}%" if v3 is not None else "—", "Retenção média aos 3 meses"),
        ("amber", f"{v6:.1f}%" if v6 is not None else "—", "Retenção média aos 6 meses"),
        ("green", f"{v12:.1f}%" if v12 is not None else "—", "Retenção média aos 12 meses"),
    ]
)
st.plotly_chart(charts.retention_curve(retention), width="stretch", config={"displayModeBar": False})
card_close([("#2563eb", "3 meses", 1), ("#d97706", "6 meses", 1), ("#16a34a", "12 meses", 1)])

st.write("")
header_left, header_right = st.columns([3, 2])
with header_left:
    st.html('<span class="table-title">Colaboradores no filtro</span>')
with header_right:
    search = st.text_input("Buscar", placeholder="Buscar por ID, nome, cargo ou cidade…", label_visibility="collapsed")

people = filter_people(source_data["rows"], cidades, grupos, start, end, search, status_selected)

filter_signature = (tuple(cidades), tuple(grupos), start, end, search, tuple(status_selected))
if st.session_state.get("_filter_signature") != filter_signature:
    st.session_state["_filter_signature"] = filter_signature
    st.session_state["page"] = 1

sort_col_1, sort_col_2, count_col = st.columns([2, 1, 3])
with sort_col_1:
    sort_label = st.selectbox("Ordenar por", list(SORT_COLUMNS.keys()), index=list(SORT_COLUMNS.keys()).index("Admissão"), label_visibility="collapsed")
with sort_col_2:
    sort_dir = st.selectbox("Direção", ["Decrescente", "Crescente"], label_visibility="collapsed")
with count_col:
    st.html(f'<span class="table-count">{len(people):,} colaboradores</span>'.replace(",", "."))

tenure = [humanize_tenure(row["Admissão"], row["Demissão"]) for _, row in people.iterrows()]
people = people.assign(TenureText=[text for text, _ in tenure], TenureDays=[days for _, days in tenure])

sort_column = SORT_COLUMNS[sort_label]
people = people.sort_values(sort_column, ascending=sort_dir == "Crescente", na_position="last")

total_rows = len(people)
total_pages = max(1, -(-total_rows // PAGE_SIZE))
current_page = min(st.session_state.get("page", 1), total_pages)

start_index = (current_page - 1) * PAGE_SIZE
page_rows = people.iloc[start_index:start_index + PAGE_SIZE]
st.html(render_table(page_rows))

nav_prev, nav_info, nav_next = st.columns([1, 4, 1])
with nav_prev:
    if st.button("‹ Anterior", disabled=current_page <= 1, width="stretch"):
        st.session_state["page"] = current_page - 1
        st.rerun()
with nav_info:
    from_row = start_index + 1 if total_rows else 0
    to_row = min(start_index + PAGE_SIZE, total_rows)
    st.html(f'<div class="pag-info" style="text-align:center;padding-top:8px">Exibindo {from_row}–{to_row} de {total_rows} · Página {current_page} de {total_pages}</div>')
with nav_next:
    if st.button("Próxima ›", disabled=current_page >= total_pages, width="stretch"):
        st.session_state["page"] = current_page + 1
        st.rerun()
