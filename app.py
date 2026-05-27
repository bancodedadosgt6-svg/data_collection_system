from __future__ import annotations

import pandas as pd
import streamlit as st

from acess import check_login, logout
from drive_database import alimentar_banco_xlsx_drive
from obter_data_csv import render_obter_data
from settings import APP_TITLE, APP_SUBTITLE, load_css


st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
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


def obter_categoria_preview(df_result: pd.DataFrame) -> str:
    """
    Identifica a categoria apenas para exibição na prévia técnica.
    """
    if df_result is None or df_result.empty:
        return "Não identificada"

    if "Categoria" in df_result.columns:
        categoria = df_result["Categoria"].iloc[0]
    elif "categoria" in df_result.columns:
        categoria = df_result["categoria"].iloc[0]
    else:
        return "Série histórica ou não informada"

    categoria = str(categoria).strip()

    return categoria if categoria else "Não informada"


def render_area_envio_drive(df_result: pd.DataFrame, file_name: str | None) -> None:
    """
    Renderiza a área de alimentação do banco XLSX no Google Drive.
    """
    st.markdown("### Alimentação do banco da UBS")

    st.info(
        "Depois de revisar os dados tratados, clique no botão abaixo para alimentar "
        "o banco XLSX da UBS no Google Drive. Os dados antigos serão preservados."
    )

    with st.expander("Prévia técnica do envio", expanded=False):
        try:
            ubs_preview = obter_ubs_destino(df_result)
            categoria_preview = obter_categoria_preview(df_result)

            st.write(
                {
                    "UBS de destino": ubs_preview,
                    "Categoria": categoria_preview,
                    "Arquivo tratado": file_name or "Arquivo tratado em memória",
                    "Linhas novas": len(df_result),
                    "Colunas recebidas": list(df_result.columns),
                }
            )

        except Exception as e:
            st.warning(f"Não foi possível montar a prévia técnica: {e}")

    if st.button(
        "Alimentar banco XLSX da UBS no Google Drive",
        type="primary",
        use_container_width=True,
    ):
        try:
            ubs_destino = obter_ubs_destino(df_result)

            with st.spinner("Conectando ao Google Drive e alimentando o banco XLSX..."):
                resultado = alimentar_banco_xlsx_drive(
                    df_novo=df_result,
                    ubs=ubs_destino,
                )

            st.success("Banco XLSX alimentado com sucesso!")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Linhas anteriores", resultado["linhas_anteriores"])

            with col2:
                st.metric("Linhas novas", resultado["linhas_novas"])

            with col3:
                st.metric("Total atual", resultado["linhas_totais"])

            st.write(
                {
                    "UBS": resultado["ubs"],
                    "Pasta": resultado["pasta"],
                    "Arquivo": resultado["arquivo"],
                    "Aba": resultado["aba"],
                    "Arquivo criado agora": "Sim"
                    if resultado["arquivo_criado"]
                    else "Não",
                }
            )

        except Exception as e:
            st.error(f"Erro ao alimentar banco XLSX no Google Drive: {e}")


def main() -> None:
    load_css("style.css")

    st.title(APP_TITLE)
    st.markdown(
        f'<p class="app-subtitle">{APP_SUBTITLE}</p>',
        unsafe_allow_html=True,
    )

    authenticated, current_user = check_login()

    if not authenticated:
        st.stop()

    top_col1, top_col2 = st.columns([8, 2])

    with top_col1:
        st.success(f"✔ Acesso liberado para: **{current_user}**")

    with top_col2:
        if st.button("Sair", type="secondary", use_container_width=True):
            logout()
            st.rerun()

    st.markdown("---")

    df_result, file_name = render_obter_data()

    if df_result is not None and not df_result.empty:
        render_area_envio_drive(
            df_result=df_result,
            file_name=file_name,
        )


if __name__ == "__main__":
    main()