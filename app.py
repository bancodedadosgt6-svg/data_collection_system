from __future__ import annotations

import streamlit as st

from acess import check_login, logout
from obter_data import render_obter_data
from settings import APP_TITLE, APP_SUBTITLE, load_css, upload_dataframe_to_drive

st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    load_css("style.css")

    st.title(APP_TITLE)
    st.markdown(f'<p class="app-subtitle">{APP_SUBTITLE}</p>', unsafe_allow_html=True)

    authenticated, current_user = check_login()

    if not authenticated:
        st.stop()

    top_col1, top_col2 = st.columns([8, 2])
    with top_col1:
        st.success(f"Acesso liberado para: **{current_user}**")
    with top_col2:
        if st.button("Sair", type="secondary", use_container_width=True):
            logout()
            st.rerun()

    st.markdown("---")

    df_result, file_name = render_obter_data()

    if df_result is not None and not df_result.empty:
        st.markdown("### Envio do arquivo tratado")
        st.info(
            "Depois de revisar os dados tratados, clique no botão abaixo para enviar "
            "o arquivo para a pasta configurada no Google Drive."
        )

        if st.button(
            "Enviar arquivo tratado para o Google Drive",
            type="primary",
            use_container_width=True,
        ):
            try:
                uploaded_name = upload_dataframe_to_drive(
                    df=df_result,
                    file_name=file_name,
                )
                st.success(f"Arquivo enviado com sucesso para o Google Drive: {uploaded_name}")
            except Exception as e:
                st.error(f"Erro ao enviar arquivo para o Google Drive: {e}")


if __name__ == "__main__":
    main()