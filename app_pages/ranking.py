"""Ranking (Top 5) de turnover médio e de desligamentos por Cidade, Cargo e Gestor.

Sem filtro de cidade/cargo/gestor — cada valor da própria dimensão é o filtro,
igual à lógica de data_logic.dimension_ranking. Só o período é selecionável.
"""

from __future__ import annotations

import streamlit as st

from src import charts
from src.components import chart_card
from src.data_logic import dimension_ranking, last_active_month, load_source_data, month_start_end

TOP_N = 5

source_data = load_source_data()
rows = source_data["rows"]

last_key = last_active_month(rows)
if last_key not in source_data["keys"]:
    last_key = source_data["keys"][-1]
default_end_idx = source_data["keys"].index(last_key)
default_start_idx = max(0, default_end_idx - 11)

min_date, _ = month_start_end(source_data["keys"][0])
_, max_date = month_start_end(source_data["keys"][-1])
default_start_date, _ = month_start_end(source_data["keys"][default_start_idx])
_, default_end_date = month_start_end(last_key)

st.html('<div class="page-title"><h1>Ranking</h1><p>Top 5 por turnover médio e por total de desligamentos no período — Cidade, Cargo e Gestor</p></div>')

with st.container(border=True):
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


def render_dimension(dimension: str, label: str, caveat: str | None = None) -> None:
    st.write("")
    st.html(f'<span class="table-title">{label}</span>')
    if caveat:
        st.caption(caveat)
    ranking = dimension_ranking(source_data, dimension, start, end)
    if ranking.empty:
        st.info(f"Sem dados suficientes para o ranking por {label.lower()} no período selecionado.")
        return

    top_turnover = ranking.sort_values("Turnover médio (%)", ascending=False).head(TOP_N)
    top_desligamentos = ranking.sort_values("Desligamentos", ascending=False).head(TOP_N)

    cols = st.columns(2)
    with cols[0]:
        chart_card(
            charts.ranking_bar(top_turnover, dimension, "Turnover médio (%)", "#d97706", "%", 1),
            f"Top {TOP_N} — Turnover médio (%)",
            "Média mensal do turnover real no período selecionado",
            [("#d97706", "Turnover médio %", 1)],
        )
    with cols[1]:
        if ranking["Desligamentos"].sum() == 0:
            st.info("Não há desligamento nenhum atribuído a gestor nesta base — quem já saiu não tem gestor registrado (limitação da fonte, não do dashboard).")
        else:
            chart_card(
                charts.ranking_bar(top_desligamentos, dimension, "Desligamentos", "#dc2626"),
                f"Top {TOP_N} — Desligamentos",
                "Total de desligamentos no período selecionado",
                [("#dc2626", "Desligamentos", 1)],
            )


render_dimension("Cidade", "Cidade")
render_dimension("Grupo", "Cargo")
render_dimension(
    "Gestor", "Gestor",
    caveat="⚠️ Desligados não têm gestor registrado na base — o turnover aqui reflete só admissões e o headcount de quem continua ativo, não desligamentos.",
)
