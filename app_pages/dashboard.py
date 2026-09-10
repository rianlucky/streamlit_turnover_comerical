from __future__ import annotations

import io

import streamlit as st

from src import charts
from src.components import card_close, card_open, chart_card, kpi_row, render_table, stat_pair
from src.data_logic import (
    city_concentration,
    city_label,
    filter_people,
    get_series,
    humanize_days,
    humanize_tenure,
    last_active_month,
    load_source_data,
    mean_nonzero,
    month_start_end,
    select_period,
)

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


@st.cache_data(ttl=600)
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

min_date, _ = month_start_end(source_data["keys"][0])
_, max_date = month_start_end(source_data["keys"][-1])
default_start_date, _ = month_start_end(source_data["keys"][default_start_idx])
_, default_end_date = month_start_end(last_key)

st.html('<div class="page-title"><h1>Movimentação de Pessoas</h1><p>Análise de admissões, demissões, turnover e headcount por cidade e cargo</p></div>')

with st.container(border=True):
    filters = st.columns([1.2, 1.3, 1.3, 1.1, 1.8])
    with filters[0]:
        cidades = st.multiselect("Cidade", source_data["cidades"], placeholder="Global (todas)", format_func=city_label)
    with filters[1]:
        grupos = st.multiselect("Cargo", source_data["grupos"], placeholder="Todos")
    with filters[2]:
        gestores = st.multiselect("Gestor", source_data["gestores"], placeholder="Todos")
    with filters[3]:
        equipes = st.multiselect("Equipe", source_data["equipes"], placeholder="Todas")
    with filters[4]:
        date_range = st.date_input(
            "Período",
            value=(default_start_date, default_end_date),
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",
        )

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start_date, default_end_date
start, end = start_date.strftime("%Y-%m"), end_date.strftime("%Y-%m")

if start > end:
    st.error("O mês inicial precisa ser anterior ou igual ao mês final.")
    st.stop()

series = get_series(source_data, cidades, grupos, gestores, equipes)
period = select_period(source_data, series, start, end)
admissions_total, terminations_total = int(period["Admissões"].sum()), int(period["Desligamentos"].sum())
active_final = int(period["Ativos"].iloc[-1]) if not period.empty else 0
turnover_media = mean_nonzero(period["Turnover real (%)"])
legado_media = mean_nonzero(period["Legado (%)"])
voluntario_media = mean_nonzero(period["Turnover Voluntário (%)"])
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

row_three = st.columns(2)
with row_three[0]:
    chart_card(
        charts.desligamentos_por_tipo(period),
        "Desligamentos por Tipo",
        "Voluntário × Involuntário, empilhados por mês",
        [("#dc2626", "Voluntário", 1), ("#64748b", "Involuntário", 1)],
    )
with row_three[1]:
    chart_card(
        charts.turnover_voluntario(period, voluntario_media),
        "Turnover Voluntário Mensal (%)",
        "Desligamentos voluntários ÷ Efetivo médio do mês",
        [("#9333ea", "Turnover voluntário %", 1), ("#9333ea", "Média do período", 0.35)],
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
population = filter_people(source_data["rows"], cidades, grupos, gestores, equipes, start, end, "", [])
population_days = [humanize_tenure(row["Admissão"], row["Demissão"])[1] for _, row in population.iterrows()]
population = population.assign(_Dias=population_days)
dias_ativos = population.loc[population["Status"] == "Ativo", "_Dias"]
dias_desligados = population.loc[population["Status"] != "Ativo", "_Dias"]

indicadores_cols = st.columns(2)
with indicadores_cols[0]:
    chart_card(
        charts.concentracao_mapa(city_concentration(population)),
        "Concentração da Mão de Obra",
        "Colaboradores ativos por cidade, dentro do filtro atual",
        [("#2563eb", "Ativos por cidade", 1)],
    )
with indicadores_cols[1]:
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

st.write("")
header_left, header_right = st.columns([3, 2])
with header_left:
    st.html('<span class="table-title">Colaboradores no filtro</span>')
with header_right:
    search = st.text_input("Buscar", placeholder="Buscar por ID, nome, cargo ou cidade…", label_visibility="collapsed")

sort_col_1, sort_col_2, status_col, count_col, export_col = st.columns([1.6, 0.9, 1.3, 1.7, 1.2])
with sort_col_1:
    sort_label = st.selectbox("Ordenar por", list(SORT_COLUMNS.keys()), index=list(SORT_COLUMNS.keys()).index("Admissão"), label_visibility="collapsed")
with sort_col_2:
    sort_dir = st.selectbox("Direção", ["Decrescente", "Crescente"], label_visibility="collapsed")
with status_col:
    status_selected = st.multiselect("Status", STATUS_VALUES, default=["Ativo"], label_visibility="collapsed")

people = filter_people(source_data["rows"], cidades, grupos, gestores, equipes, start, end, search, status_selected)

filter_signature = (tuple(cidades), tuple(grupos), tuple(gestores), tuple(equipes), start, end, search, tuple(status_selected))
if st.session_state.get("_filter_signature") != filter_signature:
    st.session_state["_filter_signature"] = filter_signature
    st.session_state["page"] = 1

with count_col:
    st.html(f'<span class="table-count">{len(people):,} colaboradores</span>'.replace(",", "."))

tenure = [humanize_tenure(row["Admissão"], row["Demissão"]) for _, row in people.iterrows()]
people = people.assign(TenureText=[text for text, _ in tenure], TenureDays=[days for _, days in tenure])

sort_column = SORT_COLUMNS[sort_label]
people = people.sort_values(sort_column, ascending=sort_dir == "Crescente", na_position="last")

with export_col:
    export_df = people[["Registro", "Nome", "Cargo Atual2", "Equipe", "Cidade", "Gestor", "Status", "Admissão", "Demissão", "TenureText"]].rename(
        columns={"Registro": "ID", "Cargo Atual2": "Cargo", "TenureText": "Permanência"}
    )
    excel_buffer = io.BytesIO()
    export_df.to_excel(excel_buffer, index=False, sheet_name="Colaboradores", engine="openpyxl")
    st.download_button(
        "⬇ Exportar",
        data=excel_buffer.getvalue(),
        file_name=f"colaboradores_{start}_a_{end}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

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
