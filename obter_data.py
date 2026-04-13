from __future__ import annotations

import io

import pandas as pd
import streamlit as st


def render_obter_data():
    """
    Mantém a lógica original do obter_data.py e retorna:
    - dataframe tratado
    - nome sugerido para o arquivo final
    """
    st.sidebar.title("MENU")
    pagina = st.sidebar.radio(
        label="Ir para:",
        options=["Página Inicial", "Análise"],
    )

    if pagina == "Página Inicial":
        st.markdown(
            """
            ## Submissão de dados em saúde alimentar

            Use este sistema para:
            - selecionar a UBS
            - selecionar a categoria do profissional
            - subir o CSV bruto
            - revisar o dado tratado
            - enviar o arquivo final para o Google Drive
            """
        )

    ubs = st.selectbox(
        "Selecione a UBS:",
        options=[" ", "Gama", "Santa Maria", "Jardins Mangueiral"],
    )

    if ubs == "Gama":
        st.success("Você selecionou o Gama!")
    elif ubs == "Santa Maria":
        st.success("Você selecionou o Santa Maria!")
    elif ubs == "Jardins Mangueiral":
        st.success("Você selecionou o Jardins Mangueiral!")

    profissional = st.selectbox(
        "Selecione a categoria do profissional:",
        options=[
            " ",
            "ACS",
            "Auxiliar Técnico",
            "Dentista",
            "Enfermeiro",
            "Médico",
            "Outro profissional",
            "Técnico Saúde Bucal",
        ],
    )

    if profissional == "ACS":
        st.success("Você selecionou a ACS!")
    elif profissional == "Auxiliar Técnico":
        st.success("Você selecionou o Auxiliar Técnico!")
    elif profissional == "Dentista":
        st.success("Você selecionou o Dentista!")
    elif profissional == "Enfermeiro":
        st.success("Você selecionou o Enfermeiro!")
    elif profissional == "Médico":
        st.success("Você selecionou o Médico!")
    elif profissional == "Outro profissional":
        st.success("Você selecionou o Outro profissional!")
    elif profissional == "Técnico Saúde Bucal":
        st.success("Você selecionou o Técnico Saúde Bucal!")

    upload = st.file_uploader(
        label="Faça o upload do arquivo CSV",
        type="csv",
    )

    if upload is not None:
        try:
            upload.seek(0)
            raw_bytes = upload.read()

            linhas = raw_bytes.splitlines()
            if len(linhas) < 12:
                st.error("O arquivo enviado não possui a estrutura mínima esperada.")
                return None, None

            linha_12 = linhas[11].decode("latin-1")
            is_acs = "ACS" in linha_12

            upload_buffer = io.BytesIO(raw_bytes)

            df = pd.read_csv(
                upload_buffer,
                encoding="latin-1",
                sep=";",
                skiprows=18,
            )

            df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

            if len(df) < 27:
                st.error("O arquivo não possui linhas suficientes após o cabeçalho esperado.")
                return None, None

            df_linha44 = df.iloc[26:]  # (44 - 18 = 26, mantendo sua regra original)

            if is_acs:
                if "Tipo" not in df.columns:
                    st.error("A coluna 'Tipo' não foi encontrada no arquivo.")
                    return None, None

                dfcadastro = df[df["Tipo"] == "Cadastro individual"]
                df = pd.concat([dfcadastro, df_linha44])
            else:
                df = df_linha44
                df["UBS"] = ubs
                df["Categoria"] = profissional

            df["UBS"] = ubs
            df["Categoria"] = profissional

            colunas = ["UBS", "Categoria"] + [c for c in df.columns if c not in ["UBS", "Categoria"]]
            df = df[colunas]

            st.success("Dados carregados com sucesso!")
            st.dataframe(df, use_container_width=True)

            file_name = build_output_filename(ubs=ubs, profissional=profissional)

            st.markdown("### Nome do arquivo tratado")
            st.code(file_name)

            return df, file_name

        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")
            return None, None

    return None, None


def build_output_filename(ubs: str, profissional: str) -> str:
    ubs_slug = normalize_text_for_filename(ubs) if ubs else "ubs_nao_informada"
    profissional_slug = (
        normalize_text_for_filename(profissional) if profissional else "profissional_nao_informado"
    )
    return f"{ubs_slug}_{profissional_slug}_tratado.csv"


def normalize_text_for_filename(text: str) -> str:
    if not text:
        return "sem_valor"

    replacements = {
        " ": "_",
        "á": "a",
        "à": "a",
        "â": "a",
        "ã": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
        "Á": "a",
        "À": "a",
        "Â": "a",
        "Ã": "a",
        "É": "e",
        "Ê": "e",
        "Í": "i",
        "Ó": "o",
        "Ô": "o",
        "Õ": "o",
        "Ú": "u",
        "Ç": "c",
    }

    value = text.strip()
    for old, new in replacements.items():
        value = value.replace(old, new)

    return value.lower()