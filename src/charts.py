"""Plotly figure builders that mirror the Chart.js visuals of the original panel.

Each function reproduces, trace by trace, the chart configuration found in the
original HTML panel (colors, fills, dashed mean lines and bar styling), so the
Streamlit dashboard reads as the same chart set.
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


def desligamentos_por_tipo(period: pd.DataFrame) -> go.Figure:
    """Barras empilhadas: desligamentos voluntários x involuntários por mês."""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=period["Mês"], y=period["Desligamentos Voluntários"], name="Voluntário", marker_color="rgba(220,38,38,.65)", marker_cornerradius=4))
    fig.add_trace(go.Bar(x=period["Mês"], y=period["Desligamentos Involuntários"], name="Involuntário", marker_color="rgba(100,116,139,.65)", marker_cornerradius=4))
    fig.update_layout(**_base_layout(), barmode="stack", bargap=0.3)
    return fig


def turnover_voluntario(period: pd.DataFrame, media: float) -> go.Figure:
    x, y = period["Mês"].tolist(), period["Turnover Voluntário (%)"].tolist()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[media] * len(period), name="Média", mode="lines", line={"color": "rgba(147,51,234,.4)", "width": 1.5, "dash": "dash"}, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=y, name="Turnover voluntário", mode="lines+markers", line={"color": "#9333ea", "width": 2.5, "shape": "spline", "smoothing": 0.6}, marker={"size": 6, "color": "#9333ea"}, fill="tozeroy", fillcolor="rgba(147,51,234,.08)"))
    fig.update_layout(**_base_layout("%", margin={"l": 6, "r": 6, "t": 24, "b": 22}), annotations=_minmax_annotations(x, y, "#9333ea", "%", 1))
    return fig


def permanencia_comparativo(dias_ativos: float, dias_desligados: float, label_ativos: str, label_desligados: str) -> go.Figure:
    """Barra horizontal Ativos × Desligados — reforça visualmente a comparação de
    permanência média (o mesmo padrão usado em benchmarks de RH de mercado, tempo
    de casa médio por status), em vez de só os dois números soltos."""
    fig = go.Figure(go.Bar(
        x=[dias_ativos, dias_desligados], y=["Ativos", "Desligados"], orientation="h",
        marker_color=["#2563eb", "#dc2626"], marker_cornerradius=6,
        text=[label_ativos, label_desligados], textposition="outside", textfont=FONT, cliponaxis=False,
    ))
    fig.update_layout(
        height=130, margin={"l": 6, "r": 60, "t": 6, "b": 6}, showlegend=False,
        paper_bgcolor="white", plot_bgcolor="white", font=FONT,
        xaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
        yaxis={"showgrid": False, "tickfont": FONT},
    )
    return fig


def ranking_bar(df: pd.DataFrame, label_col: str, value_col: str, color: str, suffix: str = "", decimals: int = 0) -> go.Figure:
    """Barra horizontal — maior valor no topo (Top N já deve vir pronto em `df`)."""
    ordered = df.sort_values(value_col, ascending=True)
    labels, values = ordered[label_col].tolist(), ordered[value_col].tolist()

    def fmt(value: float) -> str:
        return f"{value:.{decimals}f}{suffix}" if decimals else f"{int(round(value))}{suffix}"

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=color, marker_cornerradius=4,
        text=[fmt(v) for v in values], textposition="outside", textfont=FONT, cliponaxis=False,
    ))
    fig.update_layout(
        height=220, margin={"l": 6, "r": 40, "t": 6, "b": 6}, showlegend=False,
        paper_bgcolor="white", plot_bgcolor="white", font=FONT,
        xaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
        yaxis={"showgrid": False, "tickfont": FONT},
    )
    return fig


def concentracao_mapa(data: pd.DataFrame) -> go.Figure:
    """Bolhas por cidade — tamanho proporcional ao headcount ativo (só ativos, ver
    data_logic.city_concentration). `data` precisa ter Cidade/Ativos/Lat/Lon.

    `fitbounds="locations"` sozinho deixava faixas brancas nas laterais do card: o
    Plotly preserva a proporção real lat/lon do bounding box (mais alto que largo,
    pelas cidades irem do MT ao PR), então sobrava fundo branco nas bordas de um
    card mais largo que alto. Em vez disso, define um range manual com mais folga
    em longitude do que em latitude, pra usar melhor a largura do card."""
    if data.empty:
        fig = go.Figure()
        fig.update_geos(scope="south america", center={"lat": -15, "lon": -55}, projection_scale=3)
    else:
        max_ativos = data["Ativos"].max()
        sizeref = 2 * max_ativos / (42 ** 2) if max_ativos else 1
        fig = go.Figure(go.Scattergeo(
            lon=data["Lon"], lat=data["Lat"],
            text=[f"{cidade}: {ativos} ativo(s)" for cidade, ativos in zip(data["Cidade"], data["Ativos"])],
            hoverinfo="text",
            marker={
                "size": data["Ativos"], "sizemode": "area", "sizeref": sizeref, "sizemin": 4,
                "color": "#2563eb", "opacity": 0.75, "line": {"width": 1, "color": "white"},
            },
        ))
        lon_min, lon_max = data["Lon"].min(), data["Lon"].max()
        lat_min, lat_max = data["Lat"].min(), data["Lat"].max()
        lon_pad = max((lon_max - lon_min) * 0.4, 3)
        lat_pad = max((lat_max - lat_min) * 0.12, 1.5)
        fig.update_geos(
            scope="south america", visible=False,
            lonaxis_range=[lon_min - lon_pad, lon_max + lon_pad],
            lataxis_range=[lat_min - lat_pad, lat_max + lat_pad],
        )
    fig.update_geos(
        showland=True, landcolor="#f4f4f2", showcountries=True, countrycolor="#c9c9c4",
        showsubunits=True, subunitcolor="#dcdcd8", showocean=True, oceancolor="#eef4fb",
    )
    fig.update_layout(height=420, margin={"l": 0, "r": 0, "t": 0, "b": 0}, paper_bgcolor="white", showlegend=False)
    return fig


def comparativo_turnover(period: pd.DataFrame) -> go.Figure:
    """Duas linhas: turnover real (fórmula do Comercial, efetivo médio do mês) vs. a
    variante do D.O. (efetivo do último dia do mês anterior) — mesmo numerador."""
    x = period["Mês"].tolist()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=period["Turnover real (%)"].tolist(), name="Comercial", mode="lines+markers", line={"color": "#d97706", "width": 2.5, "shape": "spline", "smoothing": 0.6}, marker={"size": 6, "color": "#d97706"}))
    fig.add_trace(go.Scatter(x=x, y=period["Turnover D.O. (%)"].tolist(), name="D.O.", mode="lines+markers", line={"color": "#2563eb", "width": 2.5, "shape": "spline", "smoothing": 0.6}, marker={"size": 6, "color": "#2563eb"}))
    fig.update_layout(**_base_layout("%", margin={"l": 6, "r": 6, "t": 6, "b": 22}))
    return fig
