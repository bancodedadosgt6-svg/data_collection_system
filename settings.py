from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv


# =========================================================
# CARREGAMENTO DE AMBIENTE
# =========================================================

load_dotenv()


# =========================================================
# CAMINHOS DO PROJETO
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
STYLE_FILE = BASE_DIR / "style.css"


# =========================================================
# IDENTIDADE DO SISTEMA
# =========================================================

APP_TITLE = "Sistema de Submissão de Dados em Saúde Alimentar"
APP_SUBTITLE = "Tome bastante cuidado na submissão dos dados referênte a sua UBS!"


# =========================================================
# SUPABASE
# =========================================================

SUPABASE_URL = ""
SUPABASE_ANON_KEY = ""


# =========================================================
# UBS OFICIAIS DO SISTEMA
# =========================================================

UBS_OPTIONS = [
    "Gama",
    "Santa Maria",
    "Jardins Mangueiral",
]

UBS_SLUGS = {
    "Gama": "gama",
    "Santa Maria": "santa_maria",
    "Santa-Maria": "santa_maria",
    "Jardins Mangueiral": "jardins_mangueiral",
    "Jardins-Mangueiral": "jardins_mangueiral",
    "Jardins-Mangueral": "jardins_mangueiral",
}

UBS_DISPLAY_NAMES = {
    "gama": "Gama",
    "santa_maria": "Santa Maria",
    "jardins_mangueiral": "Jardins Mangueiral",
}


# =========================================================
# FUNÇÕES DE CONFIGURAÇÃO
# =========================================================

def get_secret_or_env(key: str, default: Any = None) -> Any:
    """
    Busca primeiro no Streamlit Secrets e depois no .env.

    Ordem:
    1. st.secrets
    2. variável de ambiente / .env
    3. valor padrão
    """
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    return os.getenv(key, default)


def get_bool_secret_or_env(key: str, default: bool = False) -> bool:
    """
    Lê variável booleana de secrets/env.
    Aceita: true, 1, yes, sim, on.
    """
    value = get_secret_or_env(key, str(default).lower())

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "sim",
        "on",
    }


def configure_supabase_settings() -> None:
    """
    Carrega as configurações do Supabase em variáveis globais.

    Necessário no .env local ou no Streamlit Secrets:
    SUPABASE_URL
    SUPABASE_ANON_KEY
    """
    global SUPABASE_URL
    global SUPABASE_ANON_KEY

    SUPABASE_URL = str(get_secret_or_env("SUPABASE_URL", "")).strip()
    SUPABASE_ANON_KEY = str(get_secret_or_env("SUPABASE_ANON_KEY", "")).strip()


def validate_supabase_settings() -> None:
    """
    Valida se as configurações mínimas do Supabase foram informadas.
    """
    configure_supabase_settings()

    missing = []

    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")

    if not SUPABASE_ANON_KEY:
        missing.append("SUPABASE_ANON_KEY")

    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(
            f"Configuração Supabase incompleta. Variáveis ausentes: {missing_text}. "
            "Configure no arquivo .env local ou no Streamlit Secrets."
        )


def get_supabase_url() -> str:
    """
    Retorna a URL do projeto Supabase.
    """
    configure_supabase_settings()
    return SUPABASE_URL


def get_supabase_anon_key() -> str:
    """
    Retorna a anon public key do Supabase.
    """
    configure_supabase_settings()
    return SUPABASE_ANON_KEY


# Carrega as variáveis ao importar o arquivo.
configure_supabase_settings()


# =========================================================
# UBS / NORMALIZAÇÃO
# =========================================================

def normalize_ubs_slug(value: str | None) -> str:
    """
    Normaliza o nome da UBS para o slug usado no banco.

    Exemplos:
    - Gama -> gama
    - Santa Maria -> santa_maria
    - Santa-Maria -> santa_maria
    - Jardins-Mangueral -> jardins_mangueiral
    """
    if value is None:
        return ""

    text = str(value).strip()

    if not text:
        return ""

    if text in UBS_SLUGS:
        return UBS_SLUGS[text]

    normalized = (
        text.lower()
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
        .replace("-", " ")
    )

    normalized = "_".join(normalized.split())

    aliases = {
        "gama": "gama",
        "santa_maria": "santa_maria",
        "jardins_mangueiral": "jardins_mangueiral",
        "jardins_mangueral": "jardins_mangueiral",
    }

    return aliases.get(normalized, normalized)


def get_ubs_display_name(value: str | None) -> str:
    """
    Retorna o nome oficial da UBS para exibição.
    """
    slug = normalize_ubs_slug(value)

    if not slug:
        return ""

    return UBS_DISPLAY_NAMES.get(slug, str(value).strip())


def is_valid_ubs(value: str | None) -> bool:
    """
    Verifica se a UBS informada está entre as UBSs oficiais.
    """
    slug = normalize_ubs_slug(value)
    return slug in UBS_DISPLAY_NAMES


# =========================================================
# CSS
# =========================================================

def load_css(css_file: str | Path = STYLE_FILE) -> None:
    """
    Carrega um arquivo CSS local e injeta no Streamlit.
    """
    css_path = Path(css_file)

    if not css_path.is_absolute():
        css_path = BASE_DIR / css_path

    if not css_path.exists():
        return

    css = css_path.read_text(encoding="utf-8")

    st.markdown(
        f"<style>{css}</style>",
        unsafe_allow_html=True,
    )


# =========================================================
# DEBUG / STATUS
# =========================================================

def get_environment_status() -> dict:
    """
    Retorna status básico do ambiente sem expor chaves sensíveis.
    Útil para diagnóstico controlado.
    """
    configure_supabase_settings()

    return {
        "supabase_url_configurada": bool(SUPABASE_URL),
        "supabase_anon_key_configurada": bool(SUPABASE_ANON_KEY),
        "base_dir": str(BASE_DIR),
        "style_file_existe": STYLE_FILE.exists(),
        "ubs_disponiveis": UBS_OPTIONS,
    }