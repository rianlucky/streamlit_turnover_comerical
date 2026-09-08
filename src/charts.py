"""Plotly figure builders that mirror the Chart.js visuals of the original panel.

Each function reproduces, trace by trace, the chart configuration found in
``assets/painel_cidade_CLT_media_turnover.html`` (colors, fills, dashed mean
lines and bar styling), so the Streamlit dashboard reads as the same chart set.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

GRID = "#f0f0ee"
FONT = {"family": "DM Sans, sans-serif", "size": 10, "color": "#6b6b68"}


def _base_layout(suffix: str = "", margin: dict | None = None) -> dict:
    return {
        "height": 260,
        "margin": margin or {"l": 6, "r": 6, "t": 6, "b": 6},
        "showlegend": False,
        "hovermode": "x unified",
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "font": FONT,
        "xaxis": {"showgrid": False, "tickfont": FONT},
        "yaxis": {"gridcolor": GRID, "tickfont": FONT, "ticksuffix": suffix, "zeroline": False},
    }


def _minmax_annotations(x: list, y: list, color: str, suffix: str = "", decimals: int = 0) -> list[dict]:
    """Data labels for only the highest and lowest point of a series (max above, min below)."""
    values = pd.Series(list(y))
    if values.empty or values.isna().all():
        return []
    max_idx, min_idx = int(values.idxmax()), int(values.idxmin())

    def fmt(value: float) -> str:
        return f"{value:.{decimals}f}{suffix}" if decimals else f"{int(round(value))}{suffix}"

    def label(idx: int, above: bool) -> dict:
        return {
            "x": x[idx], "y": y[idx], "text": fmt(y[idx]), "showarrow": False,
            "yshift": 16 if above else -16,
            "font": {"size": 10, "color": color, "family": "DM Sans, sans-serif"},
            "bgcolor": "rgba(255,255,255,.9)", "bordercolor": color, "borderwidth": 1, "borderpad": 2,
        }

    annotations = [label(max_idx, True)]
    if min_idx != max_idx:
        annotations.append(label(min_idx, False))
    return annotations


def admissoes_demissoes(period: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=period["Mês"], y=period["Admissões"], name="Admissões", marker_color="rgba(13,148,136,.75)", marker_cornerradius=4))
    fig.add_trace(go.Bar(x=period["Mês"], y=period["Desligamentos"], name="Demissões", marker_color="rgba(220,38,38,.65)", marker_cornerradius=4))
    fig.update_layout(**_base_layout(), barmode="group", bargap=0.3, bargroupgap=0.12)
    return fig


def turnover_real(period: pd.DataFrame, media: float) -> go.Figure:
    x, y = period["Mês"].tolist(), period["Turnover real (%)"].tolist()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[media] * len(period), name="Média", mode="lines", line={"color": "rgba(217,119,6,.4)", "width": 1.5, "dash": "dash"}, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=y, name="Turnover", mode="lines+markers", line={"color": "#d97706", "width": 2.5, "shape": "spline", "smoothing": 0.6}, marker={"size": 6, "color": "#d97706"}, fill="tozeroy", fillcolor="rgba(217,119,6,.08)"))
    fig.update_layout(**_base_layout("%", margin={"l": 6, "r": 6, "t": 24, "b": 22}), annotations=_minmax_annotations(x, y, "#d97706", "%", 1))
    return fig


def headcount_ativo(period: pd.DataFrame) -> go.Figure:
    x, y = period["Mês"].tolist(), period["Ativos"].tolist()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, name="Ativos", mode="lines+markers", line={"color": "#2563eb", "width": 2.5, "shape": "spline", "smoothing": 0.6}, marker={"size": 6, "color": "#2563eb"}, fill="tozeroy", fillcolor="rgba(37,99,235,.08)"))
    fig.update_layout(**_base_layout(margin={"l": 6, "r": 6, "t": 24, "b": 22}), annotations=_minmax_annotations(x, y, "#2563eb"))
    return fig


def saldo_liquido(period: pd.DataFrame) -> go.Figure:
    x = period["Mês"].tolist()
    saldo = (period["Admissões"] - period["Desligamentos"]).tolist()
    colors = ["rgba(22,163,74,.70)" if value >= 0 else "rgba(220,38,38,.65)" for value in saldo]
    fig = go.Figure(go.Bar(x=x, y=saldo, marker_color=colors, marker_cornerradius=4))
    fig.update_layout(**_base_layout(margin={"l": 6, "r": 6, "t": 24, "b": 22}), bargap=0.3, annotations=_minmax_annotations(x, saldo, "#16a34a"))
    return fig


def turnover_legado(period: pd.DataFrame, media: float) -> go.Figure:
    x, y = period["Mês"].tolist(), period["Legado (%)"].tolist()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[media] * len(period), name="Média", mode="lines", line={"color": "rgba(100,116,139,.4)", "width": 1.5, "dash": "dash"}, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=y, name="Indicador legado", mode="lines+markers", line={"color": "#64748b", "width": 2.5, "shape": "spline", "smoothing": 0.6}, marker={"size": 6, "color": "#64748b"}, fill="tozeroy", fillcolor="rgba(100,116,139,.08)"))
    fig.update_layout(**_base_layout("%", margin={"l": 6, "r": 6, "t": 24, "b": 22}), annotations=_minmax_annotations(x, y, "#64748b", "%", 1))
    return fig


def retention_curve(retention: pd.DataFrame, window: int = 18) -> go.Figure:
    """3 linhas (retenção após 3/6/12 meses) pelas últimas `window` coortes de admissão com dado."""
    recent = retention.tail(window)
    x = recent["Mês"].tolist()
    fig = go.Figure()
    for prefix, color, label in (("3m", "#2563eb", "3 meses"), ("6m", "#d97706", "6 meses"), ("12m", "#16a34a", "12 meses")):
        fig.add_trace(go.Scatter(x=x, y=recent[f"{prefix}_pct"].tolist(), name=label, mode="lines+markers", line={"color": color, "width": 2.2}, marker={"size": 5, "color": color}, connectgaps=False))
    fig.update_layout(**_base_layout("%"))
    return fig
