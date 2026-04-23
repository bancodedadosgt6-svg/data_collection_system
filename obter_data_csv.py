from __future__ import annotations

import io

import pandas as pd
import pdfplumber
import streamlit as st

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
    "Visita domiciliar e territorial"
    "Total"
]

DESCRICOES_CADASTRO = [
    "Cadastro domiciliar e territorial",
    "Cadastro individual",
    "Total"
]

def tratar_tabela_pdf(table):
    table = [row for row in table if any(cell is not None for cell in row)]
    table = [[cell if cell is not None else "" for cell in row] for row in table]

    df = pd.DataFrame(table)
    if df.shape[1] > 1:
        df.rename(columns={1: "Descrição"}, inplace=True)
    df.columns = df.iloc[0]
    df = df[1:]

    return df

def render_upload_pdf(): 
    st.title("Upload de PDF")

    ubs = st.selectbox(
        "Selecione a UBS:",
        [" ", "Gama", "Santa Maria", "Jardins Mangueiral"]
    )
    tipo_relatorio = st.selectbox(
    "Tipo de relatório:",
    options=[
        "Produção individual (padrão)",
        "Série histórica (relatório geral)",
    ],
    )

    if ubs == "Gama":
        st.success("Você selecionou o Gama!")
    elif ubs == "Santa Maria":
        st.success("Você selecionou o Santa Maria!")
    elif ubs == "Jardins Mangueiral":
        st.success("Você selecionou o Jardins Mangueiral!")
    
    profissional = None  # valor padrão

    if tipo_relatorio != "Série histórica (relatório geral)":
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
    
    is_serie_historica = tipo_relatorio == "Série histórica (relatório geral)"

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
    
    upload_pdf = st.file_uploader(
        "Faça o upload do arquivo PDF",
        type="pdf"
    )
    
    if upload_pdf is not None:
        st.success("PDF carregado com sucesso!")

        with pdfplumber.open(upload_pdf) as pdf:

            page = pdf.pages[0]  

            # TABELAS
            st.markdown("## 📊 Tabela")
            tables = page.extract_tables()
            if tables:
                dfs = []
                for i, table in enumerate(tables):
                    try:
                        df_temp = tratar_tabela_pdf(table)                      
                        df_temp = df_temp.reset_index(drop=True)
                        dfs.append(df_temp)

                    except Exception as e:
                        st.warning(f"Erro na tabela {i+1}: {e}")
                
                df_final = pd.concat(dfs, ignore_index=True)               
                df_final = df_final.reset_index(drop=True)
                
                if is_serie_historica:
                    df_final["UBS"] = ubs
                    colunas = ["UBS"] + [c for c in df_final.columns if c != "UBS"]
                    df_final = df_final[colunas]
                    st.success("Série histórica carregada com sucesso!")
                else:
                    # Cadastro
                    df_cadastro = df_final.iloc[:3].copy()
                    df_cadastro["Tipo"] = "Cadastro"
                    df_cadastro["Descrição"] = DESCRICOES_CADASTRO

                    # Produção
                    df_producao = df_final.iloc[3:].copy()
                    df_producao["Tipo"] = "Producao"
                    df_producao = df_producao.reset_index(drop=True)

                    for i in range(len(df_producao)):
                        if i < len(DESCRICOES_PRODUCAO):
                            df_producao.loc[i, "Descrição"] = DESCRICOES_PRODUCAO[i]
                    df_final = pd.concat([df_cadastro, df_producao], ignore_index=True)
                    df_final["UBS"] = ubs
                    df_final["Categoria"] = profissional

                    colunas = ["UBS", "Categoria", "Tipo"] + [
                        c for c in df_final.columns if c not in ["UBS", "Categoria", "Tipo"]
                    ]
                    df_final = df_final[colunas]
                    st.success("Relatório individual carregado com sucesso!")

                # Cadastro 
                df_cadastro = df_final.iloc[:3].copy()
                df_cadastro["Tipo"] = "Cadastro"
                df_cadastro["Descrição"] = DESCRICOES_CADASTRO

                # Produção 
                df_producao = df_final.iloc[3:].copy()
                df_producao["Tipo"] = "Producao"     
                df_producao = df_producao.reset_index(drop=True)
                for i in range(len(df_producao)):
                    if i < len(DESCRICOES_PRODUCAO):
                        df_producao.at[i, "Descrição"] = DESCRICOES_PRODUCAO[i]
                    else:
                        df_producao.at[i, "Descrição"] = "Total"

                # Junta as duas partes
                df_final = pd.concat([df_cadastro, df_producao], ignore_index=True)

                # Adiciona UBS e Categoria
                df_final["UBS"] = ubs
                if is_serie_historica: # Se for serie histórica, não tem categoria
                    df_final["UBS"] = ubs
                    colunas = ["UBS"] + [c for c in df_final.columns if c != "UBS"]
                    df_final = df_final[colunas]
                else:
                    df_final["UBS"] = ubs # Caso contrário, tem categoria
                    df_final["Categoria"] = profissional  
                    colunas = ["UBS", "Categoria", "Tipo"] + [
                        c for c in df_final.columns if c not in ["UBS", "Categoria", "Tipo"]
                    ]
                    df_final = df_final[colunas]

                st.dataframe(df_final, use_container_width=True)

            else:
                st.warning("Nenhuma tabela encontrada.")


def render_obter_data():
    """
    Mantém a lógica original do obter_data.py e retorna:
    - dataframe tratado
    - nome sugerido para o arquivo final
    """
    st.sidebar.title("MENU")
    pagina = st.sidebar.radio(
        label="Ir para:",
        options=["Página Inicial", "Análise", "Upload PDF"]
    )
    
    if pagina == "Upload PDF":
        render_upload_pdf()

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

    tipo_relatorio = st.selectbox(
    "Tipo de relatório:",
    options=[
        "Produção individual (padrão)",
        "Série histórica (relatório geral)",
    ],
)

    if ubs == "Gama":
        st.success("Você selecionou o Gama!")
    elif ubs == "Santa Maria":
        st.success("Você selecionou o Santa Maria!")
    elif ubs == "Jardins Mangueiral":
        st.success("Você selecionou o Jardins Mangueiral!")

    profissional = None  # valor padrão

    if tipo_relatorio != "Série histórica (relatório geral)":
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
            
            # Lógica para série histórica (relatório geral) #
            if tipo_relatorio == "Série histórica (relatório geral)":
                df = pd.read_csv(
                    upload_buffer,
                    encoding="latin-1",
                    sep=";",
                    skiprows=19  
                )

                df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
                df["UBS"] = ubs
                
                colunas = ["UBS"] + [c for c in df.columns if c != "UBS"] 
                df = df[colunas]
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

            file_name = build_output_filename(
                ubs=ubs,
                profissional=profissional if profissional else "serie_historica"
            )

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