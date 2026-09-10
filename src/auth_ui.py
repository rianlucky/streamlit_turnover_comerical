"""Fluxo de login em duas telas, num cartão dividido (marca à esquerda, formulário
à direita — mesmo padrão visual comum em telas de login de mercado).

Tela 1: e-mail.
Tela 2, conforme o e-mail informado:
  - sem acesso cadastrado -> mensagem pedindo para solicitar acesso ao DO;
  - acesso cadastrado, primeiro login (sem senha ainda) -> criar senha;
  - acesso cadastrado, já com senha -> digitar a senha.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Callable

import streamlit as st

from src.auth import (
    SUPPORT_EMAIL,
    get_user,
    is_locked,
    lock_remaining_minutes,
    needs_password_setup,
    normalize_email,
    set_initial_password,
    verify_login,
)

_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "icons" / "logo_sidebar.png"


@st.cache_data
def _logo_b64() -> str:
    return base64.b64encode(_LOGO_PATH.read_bytes()).decode()


def _login_shell(title: str, subtitle: str, render_form: Callable[[], None]) -> None:
    """Cartão de login: painel de marca fixo à esquerda (logo + nome do projeto),
    título/subtítulo da tela atual + formulário à direita. Envolto num container
    alto (login_page) que centraliza o cartão verticalmente na tela."""
    with st.container(key="login_page"):
        _, mid, _ = st.columns([1, 2.3, 1])
        with mid:
            with st.container(border=True, key="login_card"):
                left, right = st.columns([1, 1.25])
                with left:
                    with st.container(key="login_left"):
                        st.html(
                            f'<div class="login-logo-pill"><img src="data:image/png;base64,{_logo_b64()}" /></div>'
                            '<p class="login-brand-sub">Movimentação de pessoas, turnover e headcount da área comercial</p>'
                        )
                with right:
                    with st.container(key="login_right"):
                        st.html(f'<div class="login-form-title">{title}</div><p class="login-form-sub">{subtitle}</p>')
                        render_form()


def _screen_email() -> None:
    def form() -> None:
        email = st.text_input("E-mail", label_visibility="collapsed", placeholder="seu.email@pacaembu.com")
        if st.button("Continuar", width="stretch"):
            normalized = normalize_email(email)
            if not normalized or "@" not in normalized:
                st.error("Informe um e-mail válido.")
            else:
                st.session_state["auth_email"] = normalized
                st.rerun()

    _login_shell("Entrar", "Digite seu e-mail corporativo para acessar o painel.", form)


def _screen_connection_error() -> None:
    def form() -> None:
        st.error("Não foi possível conectar ao banco de dados agora. Isso costuma ser passageiro — tente novamente em alguns segundos.")
        if st.button("Tentar novamente", width="stretch"):
            st.rerun()

    _login_shell("Erro temporário de conexão", "Não conseguimos falar com o banco de dados agora.", form)


def _screen_no_access(email: str) -> None:
    def form() -> None:
        st.warning(f"O e-mail **{email}** ainda não tem acesso a este painel. Solicite a inclusão para **{SUPPORT_EMAIL}**.")
        if st.button("Tentar outro e-mail", width="stretch"):
            st.session_state["auth_email"] = None
            st.rerun()

    _login_shell("Acesso não encontrado", "Esse e-mail ainda não está liberado.", form)


def _screen_set_password(user: dict) -> None:
    def form() -> None:
        password = st.text_input("Senha", type="password", placeholder="Crie uma senha (mín. 8 caracteres)")
        confirm = st.text_input("Confirmar senha", type="password", placeholder="Digite a senha de novo")
        if st.button("Criar senha e entrar", width="stretch"):
            if len(password) < 8:
                st.error("A senha precisa ter pelo menos 8 caracteres.")
            elif password != confirm:
                st.error("As senhas não coincidem.")
            else:
                st.session_state["auth_user"] = set_initial_password(user["email"], password)
                st.rerun()

    name = user.get("name") or user["email"]
    _login_shell(f"Olá, {name}", "Este é seu primeiro acesso — crie uma senha.", form)


def _screen_login(user: dict) -> None:
    def form() -> None:
        if is_locked(user):
            minutos = lock_remaining_minutes(user)
            st.warning(f"Conta temporariamente bloqueada por tentativas de senha incorreta. Tente novamente em ~{minutos} minuto(s).")
            if st.button("Usar outro e-mail", key="switch_email"):
                st.session_state["auth_email"] = None
                st.rerun()
            return

        password = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Digite sua senha")
        if st.button("Entrar", width="stretch"):
            verified = verify_login(user["email"], password)
            if verified:
                st.session_state["auth_user"] = verified
                st.rerun()
            else:
                refreshed = get_user(user["email"])
                if refreshed and is_locked(refreshed):
                    st.error(f"Muitas tentativas erradas — conta bloqueada por ~{lock_remaining_minutes(refreshed)} minuto(s).")
                else:
                    st.error("Senha incorreta.")
        if st.button("Usar outro e-mail", key="switch_email"):
            st.session_state["auth_email"] = None
            st.rerun()

    name = user.get("name") or user["email"]
    _login_shell(f"Olá, {name}", "Digite sua senha para entrar.", form)


def require_login() -> None:
    """Bloqueia o restante do script até o usuário estar autenticado."""
    if st.session_state.get("auth_user") is not None:
        return

    email = st.session_state.get("auth_email")
    if not email:
        _screen_email()
        st.stop()

    try:
        user = get_user(email)
    except Exception:
        _screen_connection_error()
        st.stop()

    if user is None:
        _screen_no_access(email)
    elif needs_password_setup(user):
        _screen_set_password(user)
    else:
        _screen_login(user)
    st.stop()


def render_logout_button() -> None:
    if st.button("Sair", key="logout_btn"):
        st.session_state["auth_user"] = None
        st.session_state["auth_email"] = None
        st.rerun()


def render_sidebar_account() -> None:
    """Saudação + botão Sair na barra lateral, logo abaixo da navegação entre páginas
    (o nome do projeto já vai embutido na imagem de ``st.logo``, no topo da barra)."""
    user = st.session_state.get("auth_user")
    if not user:
        return
    with st.sidebar:
        st.markdown(f"Olá, **{user.get('name') or user['email']}**")
        if st.button("Sair", key="sidebar_logout_btn", width="stretch"):
            st.session_state["auth_user"] = None
            st.session_state["auth_email"] = None
            st.rerun()
        st.divider()
