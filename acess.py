from __future__ import annotations

import hashlib
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Formato esperado no .env:
# APP_USERS=gestor1:hash1,gestor2:hash2
APP_USERS_RAW = os.getenv("APP_USERS", "")


def load_users() -> dict[str, str]:
    users: dict[str, str] = {}

    if not APP_USERS_RAW.strip():
        return users

    pairs = [item.strip() for item in APP_USERS_RAW.split(",") if item.strip()]
    for pair in pairs:
        if ":" not in pair:
            continue
        username, password_hash = pair.split(":", 1)
        users[username.strip()] = password_hash.strip()

    return users


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate(username: str, password: str) -> bool:
    users = load_users()

    if username not in users:
        return False

    return users[username] == hash_password(password)


def check_login() -> tuple[bool, str | None]:
    if st.session_state.get("authenticated", False):
        return True, st.session_state.get("username")

    st.markdown("## Acesso do gestor")

    with st.form("login_form"):
        username = st.text_input("Login")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar", use_container_width=True)

    if submitted:
        if authenticate(username, password):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.rerun()
        else:
            st.error("Login ou senha inválidos.")

    return False, None


def logout() -> None:
    st.session_state["authenticated"] = False
    st.session_state["username"] = None