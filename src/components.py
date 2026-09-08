"""Reusable UI building blocks that recreate the look of the original HTML panel."""

from __future__ import annotations

from html import escape
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data_logic import tenure_class

KPI_SPEC = [
    # (key, css_class, label)
    ("ativos", "blue", "Ativos ao final<br>do período"),
    ("admissoes", "teal", "Total admissões<br>no período"),
    ("desligamentos", "red", "Total desligamentos<br>no período"),
    ("turnover", "amber", "Turnover real médio<br>mensal (rotatividade)"),
    ("legado", "slate", "Desligamento médio vs.<br>mês anterior (legado)"),
    ("saldo", "dyn", "Saldo líquido<br>no período"),
]


def kpi_row(values: dict[str, str], saldo_positive: bool) -> None:
    """Render the six KPI cards in a single row, matching the original palette."""
    cards = []
    for key, css_class, label in KPI_SPEC:
        if css_class == "dyn":
            css_class = "green" if saldo_positive else "red"
        cards.append(f'<div class="kpi {css_class}"><div class="kv">{values[key]}</div><div class="kl">{label}</div></div>')
    st.html(f'<div class="kpi-row">{"".join(cards)}</div>')


def chart_card(fig: go.Figure, title: str, subtitle: str, legend: Iterable[tuple[str, str, float]]) -> None:
    """Render a chart inside a bordered card with title, subtitle and a colored dot legend."""
    legend_html = "".join(f'<div class="leg-item"><span class="leg-dot" style="background:{color};opacity:{opacity}"></span>{escape(label)}</div>' for color, label, opacity in legend)
    st.html(f'<div class="chart-card"><div class="ct">{escape(title)}</div><div class="cd">{escape(subtitle)}</div>')
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.html(f'<div class="leg">{legend_html}</div></div>')


def card_open(title: str, subtitle: str) -> None:
    """Opening half of a .chart-card, for sections that need custom content between title and chart."""
    st.html(f'<div class="chart-card"><div class="ct">{escape(title)}</div><div class="cd">{escape(subtitle)}</div>')


def card_close(legend: Iterable[tuple[str, str, float]] = ()) -> None:
    legend_html = "".join(f'<div class="leg-item"><span class="leg-dot" style="background:{color};opacity:{opacity}"></span>{escape(label)}</div>' for color, label, opacity in legend)
    st.html(f'<div class="leg">{legend_html}</div></div>')


def stat_pair(items: list[tuple[str, str, str]]) -> None:
    """Small comparison cards reusing the .kpi look (for indicators outside the main 6 KPIs)."""
    cards = "".join(f'<div class="kpi {css_class}"><div class="kv">{escape(value)}</div><div class="kl">{escape(label)}</div></div>' for css_class, value, label in items)
    st.html(f'<div class="kpi-row" style="grid-template-columns:repeat({len(items)},1fr);max-width:640px;margin-bottom:14px">{cards}</div>')


def _format_date(value: str) -> str:
    if not value:
        return '<span class="dim">—</span>'
    year, month, day = value[:10].split("-")
    return f"{day}/{month}/{year}"


def render_table(page_rows: pd.DataFrame) -> str:
    """Build the HTML table body (badges, colored tenure, dashes) for a page of rows.

    Expects "TenureText"/"TenureDays" columns already computed (see data_logic.humanize_tenure),
    so tenure is derived once per filtered set rather than once per rendered page.
    """
    body_rows = []
    for _, row in page_rows.iterrows():
        status_class = "ativo" if row["Status"] == "Ativo" else "desligado"
        body_rows.append(
            "<tr>"
            f'<td class="num">{escape(str(row["Registro"]))}</td>'
            f'<td>{escape(str(row["Nome"]))}</td>'
            f'<td><span class="badge cargo">{escape(str(row["Cargo Atual2"]))}</span></td>'
            f'<td>{escape(str(row["Cidade"]))}</td>'
            f'<td class="num">{_format_date(row["Admissão"])}</td>'
            f'<td class="num">{_format_date(row["Demissão"])}</td>'
            f'<td class="num {tenure_class(row["TenureDays"])}">{escape(row["TenureText"])}</td>'
            f'<td><span class="badge {status_class}">{escape(str(row["Status"]))}</span></td>'
            "</tr>"
        )
    header = (
        "<thead><tr>"
        "<th>ID</th><th>Nome</th><th>Cargo</th><th>Cidade</th>"
        "<th>Admissão</th><th>Demissão</th><th>Permanência</th><th>Status</th>"
        "</tr></thead>"
    )
    return f'<div class="tbl-wrap"><table class="tbl">{header}<tbody>{"".join(body_rows)}</tbody></table></div>'
