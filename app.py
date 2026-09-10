"""Ponto de entrada: autenticação + navegação entre páginas."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.auth import init_db
from src.auth_ui import render_sidebar_account, require_login
from src.components import render_sidebar_status
from src.styles import inject_css

ICON_DIR = Path(__file__).parent / "assets" / "icons"
ICON = ICON_DIR / "icone-turnover-comercial-transparente.png"
LOGO = ICON_DIR / "logo_sidebar.png"

st.set_page_config(page_title="Turnover Comercial", page_icon=str(ICON), layout="wide")
inject_css()

init_db()
require_login()

st.logo(str(LOGO), icon_image=str(ICON))
render_sidebar_account()
render_sidebar_status()

pages = [
    st.Page("app_pages/dashboard.py", title="Movimentação de Pessoas", icon=":material/groups:", default=True),
    st.Page("app_pages/ranking.py", title="Ranking", icon=":material/leaderboard:"),
    st.Page("app_pages/comparativo_turnover.py", title="Comparativo Turnover", icon=":material/balance:"),
]
st.navigation(pages).run()
