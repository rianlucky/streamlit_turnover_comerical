"""CSS injection that mirrors the visual identity of the original HTML panel."""

from __future__ import annotations

import streamlit as st

# Paleta idêntica às custom properties do painel HTML original
COLORS = {
    "white": "#ffffff",
    "off": "#f7f7f5",
    "ink": "#111110",
    "mid": "#6b6b68",
    "light": "#e4e4e0",
    "teal": "#0d9488",
    "red": "#dc2626",
    "blue": "#2563eb",
    "amber": "#d97706",
    "green": "#16a34a",
    "slate": "#64748b",
}

_CSS = f"""
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&display=swap" rel="stylesheet">
<style>
:root {{
  --white:{COLORS['white']}; --off:{COLORS['off']}; --ink:{COLORS['ink']}; --mid:{COLORS['mid']};
  --light:{COLORS['light']}; --teal:{COLORS['teal']}; --red:{COLORS['red']}; --blue:{COLORS['blue']};
  --amber:{COLORS['amber']}; --green:{COLORS['green']}; --slate:{COLORS['slate']};
}}

html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
  font-family:'DM Sans',system-ui,sans-serif;
}}
[data-testid="stAppViewContainer"] > .main {{ background:var(--off); }}
.block-container {{ max-width:1200px; padding-top:4.5rem; padding-bottom:3rem; }}

/* ── Header ── */
.page-title h1 {{ font-size:21px; font-weight:600; letter-spacing:-.02em; color:var(--ink); margin:0; }}
.page-title p {{ font-size:12.5px; color:var(--mid); margin-top:3px; }}

/* ── Reskin dos widgets nativos para lembrar a filter-bar original ── */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background:var(--white); border:1.5px solid var(--light) !important; border-radius:6px;
}}
label[data-testid="stWidgetLabel"] p {{
  font-size:10px !important; font-weight:600 !important; letter-spacing:.09em; text-transform:uppercase; color:var(--mid) !important;
}}
[data-baseweb="select"] > div, div[data-testid="stTextInput"] input, div[data-testid="stDateInput"] input {{
  background:var(--off) !important; border:1.5px solid var(--light) !important; border-radius:4px !important;
  font-size:13.5px !important; font-weight:500 !important; color:var(--ink) !important;
}}
[data-baseweb="select"] > div:focus-within {{ border-color:var(--blue) !important; }}

/* ── KPI cards ── */
.kpi-row {{ display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:4px; }}
.kpi {{
  background:var(--white); border-radius:6px; padding:15px 18px;
  border:1.5px solid var(--light); border-top:3px solid transparent;
}}
.kpi .kv {{ font-size:30px; font-weight:700; letter-spacing:-.03em; line-height:1; margin-bottom:4px; }}
.kpi .kl {{ font-size:11px; color:var(--mid); line-height:1.4; }}
.kpi.blue  {{ border-top-color:var(--blue); }}  .kpi.blue  .kv {{ color:var(--blue); }}
.kpi.teal  {{ border-top-color:var(--teal); }}  .kpi.teal  .kv {{ color:var(--teal); }}
.kpi.red   {{ border-top-color:var(--red); }}   .kpi.red   .kv {{ color:var(--red); }}
.kpi.amber {{ border-top-color:var(--amber); }} .kpi.amber .kv {{ color:var(--amber); }}
.kpi.slate {{ border-top-color:var(--slate); }} .kpi.slate .kv {{ color:var(--slate); }}
.kpi.green {{ border-top-color:var(--green); }} .kpi.green .kv {{ color:var(--green); }}

/* ── Chart cards ── */
.chart-card {{
  background:var(--white); border:1.5px solid var(--light); border-radius:6px;
  padding:18px 20px 6px; margin-bottom:14px;
}}
.chart-card .ct {{ font-size:10.5px; font-weight:600; letter-spacing:.09em; text-transform:uppercase; color:var(--mid); margin-bottom:2px; }}
.chart-card .cd {{ font-size:11.5px; color:#b9b9b3; margin-bottom:4px; }}
.leg {{ display:flex; gap:14px; margin:6px 0 10px; flex-wrap:wrap; }}
.leg-item {{ display:flex; align-items:center; gap:5px; font-size:11px; color:var(--mid); }}
.leg-dot {{ width:10px; height:10px; border-radius:2px; display:inline-block; }}

/* Números de apoio dentro de um chart-card (ex.: Permanência Média) — cartões
   centralizados como grupo, com fundo levemente colorido e um "dot" de destaque em
   vez do topo colorido simples dos 6 KPIs principais (esses ficam mais "vivos" por
   estarem sozinhos, sem gráfico do lado, num espaço menor). */
.kpi-row-centered {{ display:flex; justify-content:center; align-items:stretch; gap:14px; flex-wrap:wrap; margin:6px 0 4px; }}
.kpi-row-centered .kpi {{
  flex:1 1 160px; max-width:220px; border:none; border-radius:10px;
  display:flex; align-items:center; gap:12px; padding:14px 18px;
}}
.kpi-row-centered .kpi::before {{ content:''; width:10px; height:10px; border-radius:50%; flex-shrink:0; }}
.kpi-row-centered .kpi.blue {{ background:#eff6ff; }} .kpi-row-centered .kpi.blue::before {{ background:var(--blue); }}
.kpi-row-centered .kpi.red  {{ background:#fef2f2; }} .kpi-row-centered .kpi.red::before  {{ background:var(--red); }}
.kpi-row-centered .kpi .kv {{ white-space:nowrap; font-size:20px; }}

.stat-insight {{ text-align:center; font-size:12px; color:var(--mid); margin:2px 0 18px; }}
.stat-insight strong {{ color:var(--ink); font-weight:600; }}

/* ── Tabela analítica ── */
.table-title {{ font-size:13px; font-weight:600; color:var(--ink); }}
.table-count {{ font-size:11px; font-weight:600; padding:3px 10px; border-radius:99px; background:#eff6ff; color:var(--blue); margin-left:10px; }}
.tbl-wrap {{ background:var(--white); border:1.5px solid var(--light); border-radius:6px; overflow:hidden; }}
.tbl {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
.tbl thead tr {{ background:var(--off); border-bottom:2px solid var(--light); }}
.tbl th {{ padding:10px 14px; text-align:left; font-size:10px; font-weight:600; letter-spacing:.09em; text-transform:uppercase; color:var(--mid); white-space:nowrap; }}
.tbl tbody tr {{ border-bottom:1px solid var(--light); }}
.tbl tbody tr:last-child {{ border-bottom:none; }}
.tbl tbody tr:hover {{ background:#fafaf8; }}
.tbl td {{ padding:9px 14px; color:var(--ink); vertical-align:middle; }}
.tbl td.num {{ font-variant-numeric:tabular-nums; }}
.tbl .dim {{ color:var(--light); }}

.badge {{ display:inline-flex; align-items:center; gap:5px; font-size:10.5px; font-weight:600; padding:3px 9px; border-radius:99px; white-space:nowrap; }}
.badge.ativo     {{ background:#f0fdf4; color:var(--green); }}
.badge.desligado {{ background:#fef2f2; color:var(--red); }}
.badge.cargo     {{ background:#eff6ff; color:var(--blue); }}

/* Especificidade acima de ".tbl td" (que também define color), para a cor prevalecer. */
.tbl td.perm-low {{ color:var(--red); font-weight:600; }}
.tbl td.perm-mid {{ color:var(--amber); font-weight:500; }}
.tbl td.perm-ok  {{ color:var(--green); font-weight:500; }}

.pag-info {{ font-size:12px; color:var(--mid); }}

/* ── Tela de login (cartão dividido: marca à esquerda, formulário à direita) ── */
.st-key-login_page {{ margin-top:10vh; }}
[data-testid="stVerticalBlockBorderWrapper"].st-key-login_card {{
  border:none !important; border-radius:16px; overflow:hidden; padding:0 !important;
  box-shadow:0 14px 40px rgba(17,17,16,.12);
}}
.st-key-login_card [data-testid="stHorizontalBlock"] {{ gap:0 !important; }}
.st-key-login_left {{
  background:linear-gradient(160deg, var(--teal) 0%, var(--blue) 100%);
  min-height:460px; height:100%; padding:48px 30px;
  display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center;
}}
.login-logo-pill {{
  background:var(--white); border-radius:12px; padding:16px 22px;
  display:inline-flex; align-items:center; justify-content:center; margin-bottom:22px;
  box-shadow:0 6px 18px rgba(0,0,0,.18);
}}
.login-logo-pill img {{ width:190px; height:auto; display:block; }}
.login-brand-sub {{ color:rgba(255,255,255,.85); font-size:12px; line-height:1.65; max-width:200px; margin:0; }}
.st-key-login_right {{ padding:48px 44px; min-height:460px; height:100%; display:flex; flex-direction:column; justify-content:center; }}
.login-form-title {{ font-size:18px; font-weight:600; color:var(--ink); margin:0 0 4px; line-height:1.4; }}
.login-form-sub {{ font-size:12.5px; color:var(--mid); margin:0 0 22px; line-height:1.5; }}
.st-key-login_right div[data-testid="stButton"] button {{
  background:linear-gradient(160deg, var(--teal) 0%, var(--blue) 100%) !important; border:none !important;
  font-weight:600 !important; border-radius:8px !important; padding:10px 0 !important;
}}
.st-key-login_right div[data-testid="stButton"] button p {{ color:var(--white) !important; }}
.st-key-login_right div[data-testid="stButton"] button:hover {{ filter:brightness(1.08); }}
</style>
"""


def inject_css() -> None:
    # st.markdown's HTML sanitizer strips <style>/<link> even with unsafe_allow_html=True;
    # st.html() inserts raw markup untouched, which is required for global CSS to apply.
    st.html(_CSS)
