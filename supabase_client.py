from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st
from supabase import Client, create_client

from settings import (
    get_supabase_anon_key,
    get_supabase_url,
    validate_supabase_settings,
)


# =========================================================
# CHAVES DE SESSÃO STREAMLIT
# =========================================================

SESSION_SUPABASE_USER = "supabase_user"
SESSION_SUPABASE_SESSION = "supabase_session"
SESSION_SUPABASE_ACCESS_TOKEN = "supabase_access_token"
SESSION_SUPABASE_REFRESH_TOKEN = "supabase_refresh_token"
SESSION_SUPABASE_PROFILE = "supabase_profile"
SESSION_AUTHENTICATED = "authenticated"


# =========================================================
# CLIENTE SUPABASE
# =========================================================

@st.cache_resource(show_spinner=False)
def get_supabase_client() -> Client:
    """
    Cria o cliente Supabase base usando SUPABASE_URL e SUPABASE_ANON_KEY.

    Esse cliente é usado para:
    - autenticação;
    - consultas públicas permitidas por RLS;
    - criação de clientes autenticados.
    """
    validate_supabase_settings()

    supabase_url = get_supabase_url()
    supabase_anon_key = get_supabase_anon_key()

    return create_client(
        supabase_url,
        supabase_anon_key,
    )


def get_authenticated_supabase_client() -> Client:
    """
    Retorna um cliente Supabase com a sessão do usuário autenticado.

    Importante:
    - Para inserts/selects em tabelas com RLS, precisamos que o cliente esteja
      com access_token e refresh_token do usuário logado.
    """
    validate_supabase_settings()

    access_token = st.session_state.get(SESSION_SUPABASE_ACCESS_TOKEN)
    refresh_token = st.session_state.get(SESSION_SUPABASE_REFRESH_TOKEN)

    client = create_client(
        get_supabase_url(),
        get_supabase_anon_key(),
    )

    if access_token and refresh_token:
        try:
            client.auth.set_session(
                access_token=access_token,
                refresh_token=refresh_token,
            )
        except Exception:
            # Se a sessão estiver inválida/expirada, mantém cliente anônimo.
            # O fluxo de autenticação vai pedir login novamente quando necessário.
            pass

    return client


# =========================================================
# HELPERS DE RESPOSTA SUPABASE
# =========================================================

def _safe_get_attr(obj: Any, attr: str, default: Any = None) -> Any:
    """
    Busca atributo de forma segura em objetos ou dicionários.
    """
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(attr, default)

    return getattr(obj, attr, default)


def _serialize_user(user: Any) -> Dict[str, Any]:
    """
    Converte o usuário do Supabase em dict seguro para guardar no session_state.
    """
    if user is None:
        return {}

    metadata = _safe_get_attr(user, "user_metadata", {}) or {}
    app_metadata = _safe_get_attr(user, "app_metadata", {}) or {}

    return {
        "id": _safe_get_attr(user, "id"),
        "email": _safe_get_attr(user, "email"),
        "created_at": str(_safe_get_attr(user, "created_at", "")),
        "user_metadata": metadata,
        "app_metadata": app_metadata,
    }


def _serialize_session(session: Any) -> Dict[str, Any]:
    """
    Converte a sessão do Supabase em dict seguro.
    """
    if session is None:
        return {}

    return {
        "access_token": _safe_get_attr(session, "access_token"),
        "refresh_token": _safe_get_attr(session, "refresh_token"),
        "token_type": _safe_get_attr(session, "token_type"),
        "expires_in": _safe_get_attr(session, "expires_in"),
        "expires_at": _safe_get_attr(session, "expires_at"),
    }


def _store_auth_session(user: Any, session: Any) -> None:
    """
    Armazena usuário e sessão no st.session_state.
    """
    user_data = _serialize_user(user)
    session_data = _serialize_session(session)

    st.session_state[SESSION_SUPABASE_USER] = user_data
    st.session_state[SESSION_SUPABASE_SESSION] = session_data
    st.session_state[SESSION_SUPABASE_ACCESS_TOKEN] = session_data.get("access_token")
    st.session_state[SESSION_SUPABASE_REFRESH_TOKEN] = session_data.get("refresh_token")
    st.session_state[SESSION_AUTHENTICATED] = bool(user_data.get("id"))


def clear_auth_session() -> None:
    """
    Limpa a sessão local do Streamlit.
    """
    for key in [
        SESSION_SUPABASE_USER,
        SESSION_SUPABASE_SESSION,
        SESSION_SUPABASE_ACCESS_TOKEN,
        SESSION_SUPABASE_REFRESH_TOKEN,
        SESSION_SUPABASE_PROFILE,
        SESSION_AUTHENTICATED,
    ]:
        st.session_state.pop(key, None)


# =========================================================
# AUTENTICAÇÃO
# =========================================================

def sign_in_with_email_password(email: str, password: str) -> Dict[str, Any]:
    """
    Faz login no Supabase Auth com e-mail e senha.

    Retorna:
    {
        "success": bool,
        "user": dict,
        "profile": dict | None,
        "error": str | None
    }
    """
    email = str(email or "").strip().lower()
    password = str(password or "")

    if not email or not password:
        return {
            "success": False,
            "user": {},
            "profile": None,
            "error": "Informe e-mail e senha.",
        }

    try:
        client = get_supabase_client()

        response = client.auth.sign_in_with_password(
            {
                "email": email,
                "password": password,
            }
        )

        user = _safe_get_attr(response, "user")
        session = _safe_get_attr(response, "session")

        if not user or not session:
            clear_auth_session()
            return {
                "success": False,
                "user": {},
                "profile": None,
                "error": "Não foi possível autenticar o usuário.",
            }

        _store_auth_session(user, session)

        profile = get_current_user_profile()
        st.session_state[SESSION_SUPABASE_PROFILE] = profile

        return {
            "success": True,
            "user": st.session_state.get(SESSION_SUPABASE_USER, {}),
            "profile": profile,
            "error": None,
        }

    except Exception as e:
        clear_auth_session()

        return {
            "success": False,
            "user": {},
            "profile": None,
            "error": f"Falha no login: {e}",
        }


def sign_out() -> None:
    """
    Faz logout no Supabase e limpa a sessão local.
    """
    try:
        client = get_authenticated_supabase_client()
        client.auth.sign_out()
    except Exception:
        pass

    clear_auth_session()


def is_authenticated() -> bool:
    """
    Verifica se há usuário autenticado no Streamlit.
    """
    user = st.session_state.get(SESSION_SUPABASE_USER)
    access_token = st.session_state.get(SESSION_SUPABASE_ACCESS_TOKEN)

    return bool(user and user.get("id") and access_token)


def get_current_user() -> Dict[str, Any]:
    """
    Retorna o usuário atual salvo na sessão.
    """
    return st.session_state.get(SESSION_SUPABASE_USER, {}) or {}


def get_current_user_id() -> Optional[str]:
    """
    Retorna o ID do usuário atual.
    """
    user = get_current_user()
    user_id = user.get("id")

    if not user_id:
        return None

    return str(user_id)


def get_current_user_email() -> Optional[str]:
    """
    Retorna o e-mail do usuário atual.
    """
    user = get_current_user()
    email = user.get("email")

    if not email:
        return None

    return str(email)


# =========================================================
# PERFIL DO USUÁRIO
# =========================================================

def get_current_user_profile() -> Optional[Dict[str, Any]]:
    """
    Busca o perfil do usuário autenticado na tabela public.perfis.

    A tabela esperada é:
    public.perfis
    - id uuid references auth.users(id)
    - nome
    - email
    - papel
    - ubs_id
    - ativo
    """
    user_id = get_current_user_id()

    if not user_id:
        return None

    try:
        client = get_authenticated_supabase_client()

        response = (
            client.table("perfis")
            .select("id,nome,email,papel,ubs_id,ativo,created_at")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        data = response.data or []

        if not data:
            return None

        return data[0]

    except Exception:
        return None


def refresh_current_user_profile() -> Optional[Dict[str, Any]]:
    """
    Atualiza o perfil do usuário na sessão.
    """
    profile = get_current_user_profile()
    st.session_state[SESSION_SUPABASE_PROFILE] = profile
    return profile


def get_session_profile() -> Optional[Dict[str, Any]]:
    """
    Retorna o perfil salvo em sessão.
    Se não existir, tenta buscar no Supabase.
    """
    profile = st.session_state.get(SESSION_SUPABASE_PROFILE)

    if profile:
        return profile

    return refresh_current_user_profile()


def user_is_active() -> bool:
    """
    Verifica se o perfil do usuário está ativo.
    """
    profile = get_session_profile()

    if profile is None:
        return True

    return bool(profile.get("ativo", True))


def get_user_role() -> str:
    """
    Retorna o papel do usuário.
    Exemplo: admin, gestor, visualizador.
    """
    profile = get_session_profile()

    if not profile:
        return "gestor"

    return str(profile.get("papel") or "gestor")


def get_user_ubs_id() -> Optional[str]:
    """
    Retorna a UBS vinculada ao usuário, se existir.
    """
    profile = get_session_profile()

    if not profile:
        return None

    ubs_id = profile.get("ubs_id")

    if not ubs_id:
        return None

    return str(ubs_id)


# =========================================================
# CONSULTAS BÁSICAS
# =========================================================

def fetch_active_ubs() -> list[Dict[str, Any]]:
    """
    Busca UBSs ativas no Supabase.
    """
    try:
        client = get_authenticated_supabase_client()

        response = (
            client.table("ubs")
            .select("id,nome,slug,ativa")
            .eq("ativa", True)
            .order("nome")
            .execute()
        )

        return response.data or []

    except Exception:
        return []


def get_ubs_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """
    Busca uma UBS pelo slug.
    """
    slug = str(slug or "").strip()

    if not slug:
        return None

    try:
        client = get_authenticated_supabase_client()

        response = (
            client.table("ubs")
            .select("id,nome,slug,ativa")
            .eq("slug", slug)
            .eq("ativa", True)
            .limit(1)
            .execute()
        )

        data = response.data or []

        if not data:
            return None

        return data[0]

    except Exception:
        return None


# =========================================================
# DIAGNÓSTICO
# =========================================================

def test_supabase_connection() -> Dict[str, Any]:
    """
    Testa conexão básica com Supabase sem expor chaves.
    """
    try:
        validate_supabase_settings()

        client = get_supabase_client()

        response = (
            client.table("ubs")
            .select("id,nome,slug,ativa")
            .limit(3)
            .execute()
        )

        return {
            "success": True,
            "message": "Conexão com Supabase realizada com sucesso.",
            "ubs_count": len(response.data or []),
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Falha na conexão com Supabase: {e}",
            "ubs_count": 0,
        }