from __future__ import annotations

import base64
from pathlib import Path

import pandas as pd
import streamlit as st

from acess import check_login, logout
from drive_database import alimentar_banco_xlsx_drive
from obter_data_csv import render_obter_data
from settings import APP_TITLE, APP_SUBTITLE, load_css


BASE_DIR = Path(__file__).resolve().parent
FUNDO_PATH = BASE_DIR / "assets" / "fundo.png"
LOGO_PATH = BASE_DIR / "assets" / "logo.png"


st.set_page_config(
    page_title=APP_TITLE,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def aplicar_fundo_sistema() -> None:
    """
    Aplica assets/fundo.png como fundo global do sistema.

    A imagem é convertida para base64 para funcionar corretamente
    no Streamlit local e no deploy, sem depender de caminho relativo.
    """
    if not FUNDO_PATH.exists():
        st.warning("Imagem de fundo não encontrada em: assets/fundo.png")
        return

    fundo_base64 = base64.b64encode(FUNDO_PATH.read_bytes()).decode("utf-8")

    st.markdown(
        f"""
        <style>
            .stApp {{
                background-image: url("data:image/png;base64,{fundo_base64}") !important;
                background-size: cover !important;
                background-position: center center !important;
                background-repeat: no-repeat !important;
                background-attachment: fixed !important;
            }}

            .block-container {{
                background: transparent !important;
            }}

            [data-testid="stHeader"] {{
                background: transparent !important;
            }}

            [data-testid="stToolbar"] {{
                background: transparent !important;
            }}

            [data-testid="stDecoration"] {{
                background: transparent !important;
            }}

            section.main > div {{
                background: transparent !important;
            }}

            main {{
                background: transparent !important;
            }}

            /*
               Mantém os blocos principais legíveis em cima da imagem,
               sem aplicar opacidade na imagem de fundo.
            */
            div[data-testid="stForm"] {{
                background: rgba(185, 248, 207, 0.96) !important;
                backdrop-filter: blur(2px);
            }}

            [data-testid="stMetric"] {{
                background: rgba(185, 248, 207, 0.96) !important;
                backdrop-filter: blur(2px);
            }}

            [data-testid="stDataFrame"] {{
                background: rgba(255, 255, 255, 0.96) !important;
                backdrop-filter: blur(2px);
            }}

            [data-testid="stFileUploader"] {{
                background: rgba(255, 255, 255, 0.92) !important;
                backdrop-filter: blur(2px);
            }}

            [data-testid="stAlert"] {{
                background: rgba(235, 255, 242, 0.94) !important;
                backdrop-filter: blur(2px);
            }}

            /*
               Inputs mais sólidos para leitura sobre o fundo.
            */
            .stTextInput > div > div > input,
            .stSelectbox > div > div,
            .stTextArea textarea,
            [data-baseweb="select"] > div {{
                background: rgba(255, 255, 255, 0.96) !important;
            }}

            /*
               Área principal com respiro visual.
            */
            .main .block-container {{
                padding-top: 4.5rem !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def obter_ubs_destino(df_result: pd.DataFrame) -> str:
    """
    Identifica a UBS no dataframe tratado.
    Aceita tanto a coluna 'UBS' quanto 'ubs'.
    """
    if df_result is None or df_result.empty:
        raise ValueError("DataFrame vazio. Não foi possível identificar a UBS.")

    if "UBS" in df_result.columns:
        ubs = df_result["UBS"].iloc[0]
    elif "ubs" in df_result.columns:
        ubs = df_result["ubs"].iloc[0]
    else:
        raise ValueError(
            "Não foi possível identificar a coluna da UBS no dataframe tratado. "
            "Era esperado encontrar a coluna 'UBS' ou 'ubs'."
        )

    ubs = str(ubs).strip()

    if not ubs:
        raise ValueError("A UBS identificada está vazia.")

    return ubs


def render_area_envio_drive(
    df_result: pd.DataFrame,
    file_name: str | None = None,
) -> None:
    """
    Renderiza a área final de submissão dos dados tratados.
    Interface limpa para o usuário final.
    """
    st.markdown("### Alimentação do banco da UBS")

    if file_name:
        st.caption(f"Arquivo tratado: {file_name}")

    if st.button(
        "Submeter dados",
        type="primary",
        use_container_width=True,
    ):
        try:
            ubs_destino = obter_ubs_destino(df_result)

            with st.spinner("Submetendo dados..."):
                resultado = alimentar_banco_xlsx_drive(
                    df_novo=df_result,
                    ubs=ubs_destino,
                )

            st.success(f"Dados da UBS {resultado['ubs']} submetidos com sucesso!")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Linhas anteriores", resultado["linhas_anteriores"])

            with col2:
                st.metric("Linhas novas", resultado["linhas_novas"])

            with col3:
                st.metric("Total atual", resultado["linhas_totais"])

        except Exception as e:
            st.error(f"Erro ao submeter dados: {e}")


def render_app_header() -> None:
    """
    Renderiza o cabeçalho principal do sistema.
    """
    st.title(APP_TITLE)
    st.markdown(
        f'<p class="app-subtitle">{APP_SUBTITLE}</p>',
        unsafe_allow_html=True,
    )


def render_authenticated_bar(current_user: str | None) -> None:
    """
    Renderiza a barra superior após autenticação.
    """
    top_col1, top_col2 = st.columns([8, 2])

    with top_col1:
        st.success(f"✔ Acesso liberado para: **{current_user}**")

    with top_col2:
        if st.button("Sair", type="secondary", use_container_width=True):
            logout()
            st.rerun()


def main() -> None:
    load_css("style.css")
    aplicar_fundo_sistema()

    render_app_header()

    authenticated, current_user = check_login()

    if not authenticated:
        st.stop()

    render_authenticated_bar(current_user)

    st.markdown("---")

    df_result, file_name = render_obter_data()

    if df_result is not None and not df_result.empty:
        render_area_envio_drive(
            df_result=df_result,
            file_name=file_name,
        )


if __name__ == "__main__":
    main()