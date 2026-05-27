from __future__ import annotations

import io
import unicodedata

import pandas as pd
import pdfplumber
import streamlit as st


UBS_OPTIONS = [" ", "Gama", "Santa Maria", "Jardins Mangueiral"]

TIPO_RELATORIO_OPTIONS = [
    "Produção individual (padrão)",
    "Série histórica (relatório geral)",
]

PROFISSIONAL_OPTIONS = [
    " ",
    "ACS",
    "Auxiliar Técnico",
    "Dentista",
    "Enfermeiro",
    "Médico",
    "Outro profissional",
    "Técnico Saúde Bucal",
]

DESCRICOES_PRODUCAO = [
    "Atendimento domiciliar",
    "Atendimento individual",
    "Atendimento odontológico individual",
    "Atividade coletiva",
    "Avaliação de elegibilidade e admissão",
    "Marcadores de consumo alimentar",
    "Procedimentos individualizados",
    "Síndrome neurológica por Zika / Microcefalia",
    "Vacinação",
    "Visita domiciliar e territorial",
    "Total",
]

DESCRICOES_CADASTRO = [
    "Cadastro domiciliar e territorial",
    "Cadastro individual",
    "Total",
]


def tratar_tabela_pdf(table) -> pd.DataFrame:
    """
    Trata uma tabela extraída do PDF pelo pdfplumber.
    Remove linhas vazias, substitui None por string vazia
    e usa a primeira linha como cabeçalho.
    """
    if not table:
        return pd.DataFrame()

    table = [row for row in table if any(cell is not None for cell in row)]
    table = [[cell if cell is not None else "" for cell in row] for row in table]

    if not table:
        return pd.DataFrame()

    df = pd.DataFrame(table)

    if df.empty or len(df) < 2:
        return pd.DataFrame()

    df.columns = df.iloc[0]
    df = df.iloc[1:].copy()
    df = df.reset_index(drop=True)

    df.columns = [
        str(col).strip() if col is not None and str(col).strip() else f"Coluna_{i + 1}"
        for i, col in enumerate(df.columns)
    ]

    return df


def aplicar_mensagem_ubs(ubs: str) -> None:
    if ubs and ubs.strip():
        st.success(f"Você selecionou a UBS: {ubs}")


def aplicar_mensagem_profissional(profissional: str | None) -> None:
    if profissional and profissional.strip():
        st.success(f"Você selecionou a categoria: {profissional}")


def validar_selecao_basica(
    ubs: str,
    tipo_relatorio: str,
    profissional: str | None = None,
) -> bool:
    """
    Valida UBS e categoria profissional antes de processar.
    """
    if not ubs or not ubs.strip():
        st.warning("Selecione uma UBS antes de carregar o arquivo.")
        return False

    if tipo_relatorio != "Série histórica (relatório geral)":
        if not profissional or not profissional.strip():
            st.warning("Selecione a categoria do profissional antes de carregar o arquivo.")
            return False

    return True


def processar_pdf_serie_historica(df_final: pd.DataFrame, ubs: str) -> pd.DataFrame:
    """
    Processa PDF no modo série histórica.
    Não inclui categoria profissional.
    """
    df_final = df_final.copy()
    df_final["UBS"] = ubs

    colunas = ["UBS"] + [c for c in df_final.columns if c != "UBS"]
    df_final = df_final[colunas]

    return df_final


def processar_pdf_individual(
    df_final: pd.DataFrame,
    ubs: str,
    profissional: str,
) -> pd.DataFrame:
    """
    Processa PDF no modo produção individual.
    Separa as três primeiras linhas como cadastro e o restante como produção.
    """
    df_final = df_final.copy().reset_index(drop=True)

    if len(df_final) < 4:
        raise ValueError(
            "A tabela extraída do PDF não possui linhas suficientes para separar cadastro e produção."
        )

    df_cadastro = df_final.iloc[:3].copy().reset_index(drop=True)
    df_cadastro["Tipo"] = "Cadastro"

    for i in range(len(df_cadastro)):
        if i < len(DESCRICOES_CADASTRO):
            df_cadastro.loc[i, "Descrição"] = DESCRICOES_CADASTRO[i]

    df_producao = df_final.iloc[3:].copy().reset_index(drop=True)
    df_producao["Tipo"] = "Producao"

    for i in range(len(df_producao)):
        if i < len(DESCRICOES_PRODUCAO):
            df_producao.loc[i, "Descrição"] = DESCRICOES_PRODUCAO[i]
        else:
            df_producao.loc[i, "Descrição"] = "Total"

    df_processado = pd.concat([df_cadastro, df_producao], ignore_index=True)

    df_processado["UBS"] = ubs
    df_processado["Categoria"] = profissional

    colunas = ["UBS", "Categoria", "Tipo"] + [
        c for c in df_processado.columns if c not in ["UBS", "Categoria", "Tipo"]
    ]

    df_processado = df_processado[colunas]

    return df_processado


def render_upload_pdf():
    """
    Renderiza a página de carregamento de PDF.
    Retorna:
    - DataFrame tratado
    - nome sugerido do arquivo
    """
    st.title("Carregar PDF")

    ubs = st.selectbox(
        "Selecione a UBS:",
        options=UBS_OPTIONS,
        key="pdf_ubs",
    )

    tipo_relatorio = st.selectbox(
        "Tipo de relatório:",
        options=TIPO_RELATORIO_OPTIONS,
        key="pdf_tipo_relatorio",
    )

    aplicar_mensagem_ubs(ubs)

    profissional = None

    if tipo_relatorio != "Série histórica (relatório geral)":
        profissional = st.selectbox(
            "Selecione a categoria do profissional:",
            options=PROFISSIONAL_OPTIONS,
            key="pdf_profissional",
        )
        aplicar_mensagem_profissional(profissional)

    is_serie_historica = tipo_relatorio == "Série histórica (relatório geral)"

    upload_pdf = st.file_uploader(
        "Faça o upload do arquivo PDF",
        type="pdf",
        key="pdf_upload",
    )

    if upload_pdf is None:
        return None, None

    if not validar_selecao_basica(
        ubs=ubs,
        tipo_relatorio=tipo_relatorio,
        profissional=profissional,
    ):
        return None, None

    try:
        st.success("PDF carregado com sucesso!")

        with pdfplumber.open(upload_pdf) as pdf:
            if not pdf.pages:
                st.error("O PDF enviado não possui páginas.")
                return None, None

            page = pdf.pages[0]

            st.markdown("## 📊 Tabela extraída")

            tables = page.extract_tables()

            if not tables:
                st.warning("Nenhuma tabela encontrada no PDF.")
                return None, None

            dfs = []

            for i, table in enumerate(tables):
                try:
                    df_temp = tratar_tabela_pdf(table)

                    if not df_temp.empty:
                        dfs.append(df_temp)

                except Exception as e:
                    st.warning(f"Erro ao tratar a tabela {i + 1}: {e}")

            if not dfs:
                st.error("Nenhuma tabela válida foi extraída do PDF.")
                return None, None

            df_final = pd.concat(dfs, ignore_index=True)
            df_final = df_final.reset_index(drop=True)

            if is_serie_historica:
                df_final = processar_pdf_serie_historica(
                    df_final=df_final,
                    ubs=ubs,
                )

                st.success("Série histórica carregada com sucesso!")

                file_name = build_output_filename(
                    ubs=ubs,
                    profissional="serie_historica_pdf",
                )

            else:
                df_final = processar_pdf_individual(
                    df_final=df_final,
                    ubs=ubs,
                    profissional=profissional or "profissional_nao_informado",
                )

                st.success("Relatório individual carregado com sucesso!")

                file_name = build_output_filename(
                    ubs=ubs,
                    profissional=f"{profissional}_pdf",
                )

            st.dataframe(df_final, use_container_width=True)

            # st.markdown("### Nome do arquivo tratado")
            # st.code(file_name)

            return df_final, file_name

    except Exception as e:
        st.error(f"Erro ao processar o PDF: {e}")
        return None, None


def render_obter_data():
    """
    Renderiza a área principal de submissão.
    Retorna:
    - dataframe tratado
    - nome sugerido para o arquivo final
    """
    with st.sidebar:
        st.image("./assets/logo2.PNG", width=200)

        st.markdown("# MENU")

        pagina = st.radio(
            "Ir para:",
            ["Carregar CSV", "Carregar PDF"],
            key="menu_pagina",
        )

    if pagina == "Carregar PDF":
        return render_upload_pdf()

    st.title("Carregar CSV")

    ubs = st.selectbox(
        "Selecione a UBS:",
        options=UBS_OPTIONS,
        key="csv_ubs",
    )

    tipo_relatorio = st.selectbox(
        "Tipo de relatório:",
        options=TIPO_RELATORIO_OPTIONS,
        key="csv_tipo_relatorio",
    )

    aplicar_mensagem_ubs(ubs)

    profissional = None

    if tipo_relatorio != "Série histórica (relatório geral)":
        profissional = st.selectbox(
            "Selecione a categoria do profissional:",
            options=PROFISSIONAL_OPTIONS,
            key="csv_profissional",
        )
        aplicar_mensagem_profissional(profissional)

    upload = st.file_uploader(
        label="Faça o upload do arquivo CSV",
        type="csv",
        key="csv_upload",
    )

    if upload is None:
        return None, None

    if not validar_selecao_basica(
        ubs=ubs,
        tipo_relatorio=tipo_relatorio,
        profissional=profissional,
    ):
        return None, None

    try:
        upload.seek(0)
        raw_bytes = upload.read()

        linhas = raw_bytes.splitlines()

        if len(linhas) < 12:
            st.error("O arquivo enviado não possui a estrutura mínima esperada.")
            return None, None

        linha_12 = linhas[11].decode("latin-1", errors="ignore")
        is_acs = "ACS" in linha_12

        upload_buffer = io.BytesIO(raw_bytes)

        if tipo_relatorio == "Série histórica (relatório geral)":
            df = pd.read_csv(
                upload_buffer,
                encoding="latin-1",
                sep=";",
                skiprows=19,
            )

            df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
            df["UBS"] = ubs

            colunas = ["UBS"] + [c for c in df.columns if c != "UBS"]
            df = df[colunas]

            file_name = build_output_filename(
                ubs=ubs,
                profissional="serie_historica",
            )

        else:
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

            df_linha44 = df.iloc[26:].copy()

            if is_acs:
                if "Tipo" not in df.columns:
                    st.error("A coluna 'Tipo' não foi encontrada no arquivo.")
                    return None, None

                dfcadastro = df[df["Tipo"] == "Cadastro individual"].copy()
                df = pd.concat([dfcadastro, df_linha44], ignore_index=True)

            else:
                df = df_linha44.copy()

            df["UBS"] = ubs
            df["Categoria"] = profissional

            colunas = ["UBS", "Categoria"] + [
                c for c in df.columns if c not in ["UBS", "Categoria"]
            ]
            df = df[colunas]

            file_name = build_output_filename(
                ubs=ubs,
                profissional=profissional or "profissional_nao_informado",
            )

        st.success("Dados carregados com sucesso!")
        st.dataframe(df, use_container_width=True)

        # st.markdown("### Nome do arquivo tratado")
        # st.code(file_name)

        return df, file_name

    except Exception as e:
        st.error(f"Erro ao processar o arquivo CSV: {e}")
        return None, None


def build_output_filename(ubs: str, profissional: str) -> str:
    ubs_slug = normalize_text_for_filename(ubs) if ubs else "ubs_nao_informada"

    profissional_slug = (
        normalize_text_for_filename(profissional)
        if profissional
        else "profissional_nao_informado"
    )

    return f"{ubs_slug}_{profissional_slug}_tratado.csv"


def normalize_text_for_filename(text: str) -> str:
    if not text:
        return "sem_valor"

    value = str(text).strip().lower()

    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))

    replacements = {
        " ": "_",
        "/": "_",
        "\\": "_",
        "-": "_",
        "(": "",
        ")": "",
        ".": "",
        ",": "",
        ";": "",
        ":": "",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    while "__" in value:
        value = value.replace("__", "_")

    return value.strip("_")