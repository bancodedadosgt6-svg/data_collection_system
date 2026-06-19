from __future__ import annotations

from typing import Optional

import streamlit as st

from supabase_client import (
    clear_auth_session,
    get_current_user_email,
    get_session_profile,
    is_authenticated,
    sign_in_with_email_password,
    sign_out,
    user_is_active,
)


# =========================================================
# CONFIGURAÇÕES DE SESSÃO
# =========================================================

SESSION_AUTHENTICATED = "authenticated"
SESSION_USERNAME = "username"


# =========================================================
# HELPERS VISUAIS
# =========================================================

def _render_login_header() -> None:
    """
    Renderiza o cabeçalho da área de login.
    """
    st.markdown(
        """
        <div style="
            background: rgba(235, 255, 242, 0.96);
            border: 1px solid rgba(34, 197, 94, 0.18);
            border-radius: 18px;
            padding: 1.4rem 1.5rem;
            box-shadow: 0 14px 32px rgba(15, 23, 42, 0.10);
            margin-bottom: 1.2rem;
        ">
            <h2 style="
                margin: 0;
                color: #0f172a;
                font-weight: 900;
                font-size: 1.55rem;
            ">
                🔐 Acesso do gestor
            </h2>
            <p style="
                margin: 0.45rem 0 0 0;
                color: #334155;
                font-size: 0.95rem;
                line-height: 1.35rem;
            ">
                Entre com sua conta cadastrada pela equipe do GT6.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_login_help() -> None:
    """
    Ajuda curta para o usuário final.
    """
    with st.expander("Problemas para acessar?"):
        st.markdown(
            """
            Verifique se:

            - o e-mail foi cadastrado pela equipe;
            - a senha está correta;
            - o usuário possui um perfil ativo;
            - o usuário foi autorizado pela gestão do sistema.
            """
        )


def _get_display_user() -> Optional[str]:
    """
    Retorna o nome/e-mail que será exibido na barra autenticada.
    """
    profile = get_session_profile()

    if profile:
        nome = profile.get("nome")
        email = profile.get("email")

        if nome:
            return str(nome)

        if email:
            return str(email)

    email = get_current_user_email()

    if email:
        return str(email)

    return st.session_state.get(SESSION_USERNAME)


def _sync_legacy_session_state() -> None:
    """
    Mantém compatibilidade com o app.py atual.

    O app.py espera:
    - st.session_state["authenticated"]
    - st.session_state["username"]
    """
    display_user = _get_display_user()

    st.session_state[SESSION_AUTHENTICATED] = True
    st.session_state[SESSION_USERNAME] = display_user or "gestor"


# =========================================================
# AUTENTICAÇÃO
# =========================================================

def check_login() -> tuple[bool, str | None]:
    """
    Renderiza o formulário de login e controla a sessão autenticada.

    Retorna:
    - (True, usuario) se autenticado
    - (False, None) se não autenticado

    Esta função substitui a autenticação antiga por APP_USERS/.env
    e passa a usar Supabase Auth.
    """
    if is_authenticated():
        if not user_is_active():
            st.error(
                "Seu usuário está inativo no sistema. "
                "Entre em contato com a gestão responsável."
            )
            clear_auth_session()
            st.session_state[SESSION_AUTHENTICATED] = False
            st.session_state[SESSION_USERNAME] = None
            return False, None

        _sync_legacy_session_state()
        return True, st.session_state.get(SESSION_USERNAME)

    st.session_state[SESSION_AUTHENTICATED] = False
    st.session_state[SESSION_USERNAME] = None

    _render_login_header()

    with st.form("login_form_supabase", clear_on_submit=False):
        email = st.text_input(
            "E-mail",
            placeholder="seuemail@exemplo.com",
            key="login_email",
        )

        password = st.text_input(
            "Senha",
            type="password",
            placeholder="Digite sua senha",
            key="login_password",
        )

        submitted = st.form_submit_button(
            "Entrar",
            width="stretch",
        )

    if submitted:
        result = sign_in_with_email_password(
            email=email,
            password=password,
        )

        if result.get("success"):
            if not user_is_active():
                clear_auth_session()
                st.session_state[SESSION_AUTHENTICATED] = False
                st.session_state[SESSION_USERNAME] = None
                st.error(
                    "Login realizado, mas seu perfil está inativo no sistema. "
                    "Entre em contato com a gestão responsável."
                )
                return False, None

            _sync_legacy_session_state()
            st.success("Login realizado com sucesso.")
            st.rerun()

        else:
            st.error(result.get("error") or "E-mail ou senha inválidos.")

    _render_login_help()

    return False, None


def logout() -> None:
    """
    Encerra a sessão do usuário no Supabase e limpa a sessão local.
    """
    sign_out()

    st.session_state[SESSION_AUTHENTICATED] = False
    st.session_state[SESSION_USERNAME] = None


# =========================================================
# COMPATIBILIDADE / UTILITÁRIOS
# =========================================================

def get_logged_user() -> str | None:
    """
    Retorna o usuário logado para uso em outras partes do sistema.
    """
    if not is_authenticated():
        return None

    return _get_display_user()


def require_login() -> bool:
    """
    Função auxiliar para páginas futuras.

    Retorna True se o usuário estiver autenticado.
    Caso contrário, renderiza login e interrompe o fluxo.
    """
    authenticated, _ = check_login()

    if not authenticated:
        st.stop()

    return True