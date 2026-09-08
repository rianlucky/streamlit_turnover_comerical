"""Fluxo de login em duas telas, no mesmo estilo visual do painel.

Tela 1: e-mail.
Tela 2, conforme o e-mail informado:
  - sem acesso cadastrado -> mensagem pedindo para solicitar acesso ao DO;
  - acesso cadastrado, primeiro login (sem senha ainda) -> criar senha;
  - acesso cadastrado, já com senha -> digitar a senha.
"""

from __future__ import annotations

import streamlit as st

from src.auth import SUPPORT_EMAIL, get_user, needs_password_setup, normalize_email, set_initial_password, verify_login


def _centered():
    _, mid, _ = st.columns([1, 1.2, 1])
    return mid


def _header(subtitle: str) -> None:
    st.html(f'<div class="page-title"><h1>Turnover Comercial</h1><p>{subtitle}</p></div>')


def _screen_email() -> None:
    _header("Entre com seu e-mail corporativo para acessar o painel")
    with _centered():
        with st.container(border=True):
            email = st.text_input("E-mail")
            if st.button("Continuar", width="stretch"):
                email = normalize_email(email)
                if not email or "@" not in email:
                    st.error("Informe um e-mail válido.")
                else:
                    st.session_state["auth_email"] = email
                    st.rerun()


def _screen_no_access(email: str) -> None:
    _header("Acesso não encontrado")
    with _centered():
        with st.container(border=True):
            st.warning(f"O e-mail **{email}** ainda não tem acesso a este painel. Solicite a inclusão para **{SUPPORT_EMAIL}**.")
            if st.button("Tentar outro e-mail", width="stretch"):
                st.session_state["auth_email"] = None
                st.rerun()


def _screen_set_password(user: dict) -> None:
    _header(f"Olá, {user.get('name') or user['email']} — este é seu primeiro acesso. Crie uma senha")
    with _centered():
        with st.container(border=True):
            password = st.text_input("Senha", type="password")
            confirm = st.text_input("Confirmar senha", type="password")
            if st.button("Criar senha e entrar", width="stretch"):
                if len(password) < 8:
                    st.error("A senha precisa ter pelo menos 8 caracteres.")
                elif password != confirm:
                    st.error("As senhas não coincidem.")
                else:
                    st.session_state["auth_user"] = set_initial_password(user["email"], password)
                    st.rerun()


def _screen_login(user: dict) -> None:
    _header(f"Olá, {user.get('name') or user['email']} — digite sua senha")
    with _centered():
        with st.container(border=True):
            password = st.text_input("Senha", type="password")
            if st.button("Entrar", width="stretch"):
                verified = verify_login(user["email"], password)
                if verified:
                    st.session_state["auth_user"] = verified
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
            if st.button("Usar outro e-mail", key="switch_email"):
                st.session_state["auth_email"] = None
                st.rerun()


def require_login() -> None:
    """Bloqueia o restante do script até o usuário estar autenticado."""
    if st.session_state.get("auth_user") is not None:
        return

    email = st.session_state.get("auth_email")
    if not email:
        _screen_email()
        st.stop()

    user = get_user(email)
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
