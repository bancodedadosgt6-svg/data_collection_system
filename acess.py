from __future__ import annotations

import hashlib
import hmac
import os

import streamlit as st
from dotenv import load_dotenv


load_dotenv()


# Formato esperado no .env:
# APP_USERS=gestor1:hash1,gestor2:hash2
#
# Exemplo:
# APP_USERS=gestor_1:hash_da_senha,gestor_2:hash_da_senha
APP_USERS_RAW = os.getenv("APP_USERS", "")


def load_users() -> dict[str, str]:
    """
    Carrega os usuários configurados no .env.

    Formato esperado:
    APP_USERS=usuario1:hash1,usuario2:hash2
    """
    users: dict[str, str] = {}

    raw_users = APP_USERS_RAW.strip()

    if not raw_users:
        return users

    pairs = [item.strip() for item in raw_users.split(",") if item.strip()]

    for pair in pairs:
        if ":" not in pair:
            continue

        username, password_hash = pair.split(":", 1)

        username = username.strip()
        password_hash = password_hash.strip()

        if username and password_hash:
            users[username] = password_hash

    return users


def hash_password(password: str) -> str:
    """
    Gera hash SHA-256 da senha.

    Mantido assim para compatibilidade com o gerar_hash.py atual.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate(username: str, password: str) -> bool:
    """
    Autentica usuário com base no .env.
    """
    username = str(username).strip()
    password = str(password)

    if not username or not password:
        return False

    users = load_users()

    if username not in users:
        return False

    expected_hash = users[username]
    provided_hash = hash_password(password)

    return hmac.compare_digest(expected_hash, provided_hash)


def check_login() -> tuple[bool, str | None]:
    """
    Renderiza o formulário de login e controla a sessão autenticada.
    """
    if st.session_state.get("authenticated", False):
        return True, st.session_state.get("username")

    st.markdown(
        '<h2 class="login-title">🔐 Acesso do gestor</h2>',
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        username = st.text_input(
            "Login",
            placeholder="Usuário",
            key="login_username",
        )

        password = st.text_input(
            "Senha",
            type="password",
            placeholder="Digite sua senha",
            key="login_password",
        )

        submitted = st.form_submit_button(
            "Entrar",
            use_container_width=True,
        )

    if submitted:
        if authenticate(username, password):
            st.session_state["authenticated"] = True
            st.session_state["username"] = str(username).strip()
            st.rerun()
        else:
            st.error("Login ou senha inválidos.")

    return False, None


def logout() -> None:
    """
    Encerra a sessão do usuário.
    """
    st.session_state["authenticated"] = False
    st.session_state["username"] = None