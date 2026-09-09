"""Página simples comparando a fórmula de turnover do Comercial com a do D.O.

Pedido da diretoria: mesmo numerador ((Admissões + Demissões) / 2), mas o
denominador difere — efetivo médio do mês (Comercial) vs. efetivo do último
dia do mês anterior (D.O.). Tela ilustrativa, sem os filtros de cidade/cargo/
status do dashboard principal — só para ver a diferença lado a lado.
"""

from __future__ import annotations

import streamlit as st

from src import charts
from src.components import chart_card
from src.data_logic import get_series, last_active_month, load_source_data, select_period

source_data = load_source_data()
label_by_key = dict(zip(source_data["keys"], source_data["labels"]))

last_key = last_active_month(source_data["rows"])
if last_key not in source_data["keys"]:
    last_key = source_data["keys"][-1]
default_end_idx = source_data["keys"].index(last_key)
default_start_idx = max(0, default_end_idx - 11)

st.html('<div class="page-title"><h1>Comparativo de Fórmulas de Turnover</h1><p>Duas contas diferentes para o mesmo mês — Comercial × D.O. (visão global, todas as cidades e cargos)</p></div>')

with st.container(border=True):
    period_cols = st.columns(2)
    with period_cols[0]:
        start = st.selectbox("De", source_data["keys"], index=default_start_idx, format_func=lambda key: label_by_key[key])
    with period_cols[1]:
        end = st.selectbox("Até", source_data["keys"], index=default_end_idx, format_func=lambda key: label_by_key[key])

if start > end:
    st.error("O mês inicial precisa ser anterior ou igual ao mês final.")
    st.stop()

series = get_series(source_data, [], [], [])
period = select_period(source_data, series, start, end)

st.html(
    '<div class="chart-card">'
    '<div class="ct">As duas fórmulas</div>'
    '<div class="cd">Mesmo numerador — (Admissões + Demissões) / 2 — o que muda é o efetivo usado no denominador</div>'
    '</div>'
)
formula_cols = st.columns(2)
with formula_cols[0]:
    st.markdown("**Turnover que o Comercial usa**")
    st.markdown("#### (Admissões + Demissões) / 2 ÷ Efetivo médio do mês")
    st.caption("Efetivo médio = média entre o headcount no início e no fim do mês.")
with formula_cols[1]:
    st.markdown("**Turnover que o D.O. usa**")
    st.markdown("#### (Admissões + Demissões) / 2 ÷ Efetivo do último dia do mês anterior")
    st.caption("Não faz média — usa direto o headcount de fechamento do mês anterior.")

chart_card(
    charts.comparativo_turnover(period),
    "Turnover Mensal (%) — Comercial × D.O.",
    "Mesmos meses, mesmas admissões e demissões; só o denominador muda",
    [("#d97706", "Comercial", 1), ("#2563eb", "D.O.", 1)],
)

st.warning(
    "**Recomendação de Mercado**\n\n"
    "O padrão de mercado (RH/SHRM) para índice de rotatividade usa o **efetivo médio do mês** "
    "no denominador — a fórmula do Comercial. Ela representa melhor a população realmente "
    "exposta a admissões/desligamentos no período, e evita distorção em meses com variação forte "
    "de quadro.\n\n"
    "A fórmula do D.O. (efetivo do fechamento do mês anterior) tende a **superestimar o turnover** "
    "em meses de crescimento forte de headcount, porque o denominador fica \"atrasado\" em relação "
    "ao quadro real do mês — é mais útil como referência de acompanhamento orçamentário/planejamento "
    "de headcount do que como indicador oficial de rotatividade.\n\n"
    "Sugestão: manter o **Comercial** como o número reportado oficialmente, e usar o do **D.O.** "
    "como métrica complementar de controle interno."
)

st.write("")
st.html('<span class="table-title">Mês a mês</span>')
display = period[["Mês", "Ativos", "Admissões", "Desligamentos", "Turnover real (%)", "Turnover D.O. (%)"]].rename(
    columns={"Turnover real (%)": "Turnover Comercial (%)"}
)
display["Diferença (p.p.)"] = (display["Turnover D.O. (%)"] - display["Turnover Comercial (%)"]).round(2)
st.dataframe(display, width="stretch", hide_index=True)
