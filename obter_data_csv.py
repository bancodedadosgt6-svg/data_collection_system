from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path
from typing import Any

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

FINAL_COLUMNS = [
    "UBS",
    "Categoria",
    "Tipo",
    "Competência",
    "Valor",
    "Identificados",
    "Não identificados",
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

METADATA_COLUMN_NAMES = {
    "ubs",
    "unidade",
    "unidade_basica",
    "unidade_basica_de_saude",
    "categoria",
    "categoria_profissional",
    "profissional",
    "tipo",
    "tipo_relatorio",
    "grupo",
    "descricao",
    "descrição",
    "indicador",
    "atividade",
    "procedimento",
    "competencia",
    "competência",
    "mes",
    "mês",
    "periodo",
    "período",
    "valor",
    "registro",
    "registros",
    "quantidade",
    "qtd",
    "identificados",
    "identificado",
    "nao_identificados",
    "não_identificados",
    "nao_identificado",
    "não_identificado",
}

DESCRIPTION_COLUMN_CANDIDATES = [
    "descricao",
    "descrição",
    "indicador",
    "atividade",
    "procedimento",
    "tipo",
]

SUMMARY_COLUMN_NAMES = {
    "total",
    "totais",
    "soma",
    "somatorio",
    "somatório",
}


# =========================================================
# NORMALIZAÇÃO GERAL
# =========================================================

def normalize_text(value: Any) -> str:
    """
    Normaliza texto para comparação interna:
    - minúsculo;
    - sem acento;
    - sem excesso de espaços;
    - com separadores convertidos para "_".
    """
    if value is None:
        return ""

    text = str(value).strip().lower()

    if not text or text in {"nan", "none", "null"}:
        return ""

    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))

    replacements = {
        "\n": " ",
        "\r": " ",
        "\t": " ",
        "-": " ",
        "/": " ",
        "\\": " ",
        ".": "",
        ",": "",
        ";": "",
        ":": "",
        "(": "",
        ")": "",
        "[": "",
        "]": "",
        "{": "",
        "}": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = "_".join(text.split())

    while "__" in text:
        text = text.replace("__", "_")

    return text.strip("_")


def clean_display_text(value: Any) -> str:
    """
    Limpa texto para exibição/gravação, preservando acentos.
    """
    if value is None:
        return ""

    text = str(value).replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = " ".join(text.split())

    if text.strip().lower() in {"nan", "none", "null"}:
        return ""

    return text.strip()


def parse_numeric_value(value: Any) -> float | None:
    """
    Converte números vindos de PDF/CSV/XLSX para float.
    Aceita:
    - 123
    - 1.234
    - 1.234,56
    - 123,45
    - strings com espaços
    """
    if value is None:
        return None

    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)

    text = clean_display_text(value)

    if not text:
        return None

    text = text.replace("\xa0", " ").strip()

    if text in {"-", "—", "–"}:
        return None

    text = re.sub(r"[^\d,.\-]", "", text)

    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def format_numeric_for_dataframe(value: Any) -> int | float | None:
    """
    Retorna inteiro quando possível, senão float.
    Isso deixa a prévia visual mais limpa no Streamlit.
    """
    number = parse_numeric_value(value)

    if number is None:
        return None

    if float(number).is_integer():
        return int(number)

    return number


def make_unique_columns(columns: list[Any]) -> list[str]:
    """
    Evita colunas duplicadas depois da extração do PDF.
    """
    seen: dict[str, int] = {}
    final_columns: list[str] = []

    for idx, col in enumerate(columns):
        base = clean_display_text(col) or f"Coluna_{idx + 1}"

        if base not in seen:
            seen[base] = 0
            final_columns.append(base)
            continue

        seen[base] += 1
        final_columns.append(f"{base}_{seen[base] + 1}")

    return final_columns


def dataframe_is_final_schema(df: pd.DataFrame) -> bool:
    """
    Verifica se o dataframe já está no formato esperado pelo Supabase.
    """
    if df is None or df.empty:
        return False

    normalized_columns = {normalize_text(col) for col in df.columns}

    required = {
        "ubs",
        "categoria",
        "tipo",
        "competencia",
        "valor",
    }

    return required.issubset(normalized_columns)


def padronizar_schema_final(
    df: pd.DataFrame,
    ubs: str | None = None,
    categoria: str | None = None,
) -> pd.DataFrame:
    """
    Garante que o dataframe saia no formato oficial:
    UBS | Categoria | Tipo | Competência | Valor | Identificados | Não identificados
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=FINAL_COLUMNS)

    rename_by_normalized = {
        "ubs": "UBS",
        "unidade": "UBS",
        "unidade_basica": "UBS",
        "unidade_basica_de_saude": "UBS",

        "categoria": "Categoria",
        "categoria_profissional": "Categoria",
        "profissional": "Categoria",

        "tipo": "Tipo",
        "tipo_relatorio": "Tipo",
        "indicador": "Tipo",
        "descricao": "Tipo",
        "descrição": "Tipo",

        "competencia": "Competência",
        "competência": "Competência",
        "mes": "Competência",
        "mês": "Competência",
        "periodo": "Competência",
        "período": "Competência",

        "valor": "Valor",
        "registro": "Valor",
        "registros": "Valor",
        "quantidade": "Valor",
        "qtd": "Valor",

        "identificados": "Identificados",
        "identificado": "Identificados",

        "nao_identificados": "Não identificados",
        "não_identificados": "Não identificados",
        "nao_identificado": "Não identificados",
        "não_identificado": "Não identificados",
    }

    out = df.copy()

    rename_map = {}
    used_targets: set[str] = set()

    for col in out.columns:
        target = rename_by_normalized.get(normalize_text(col))

        if target and target not in used_targets:
            rename_map[col] = target
            used_targets.add(target)

    out = out.rename(columns=rename_map)

    for col in FINAL_COLUMNS:
        if col not in out.columns:
            out[col] = None

    if ubs:
        out["UBS"] = ubs

    if categoria:
        out["Categoria"] = out["Categoria"].fillna("")
        out.loc[out["Categoria"].astype(str).str.strip() == "", "Categoria"] = categoria

    out = out[FINAL_COLUMNS].copy()

    out["UBS"] = out["UBS"].apply(clean_display_text)
    out["Categoria"] = out["Categoria"].apply(clean_display_text)
    out["Tipo"] = out["Tipo"].apply(clean_display_text)
    out["Competência"] = out["Competência"].apply(clean_display_text)
    out["Valor"] = out["Valor"].apply(format_numeric_for_dataframe)
    out["Identificados"] = out["Identificados"].apply(format_numeric_for_dataframe)
    out["Não identificados"] = out["Não identificados"].apply(format_numeric_for_dataframe)

    out = out[
        out[["Tipo", "Competência", "Valor", "Identificados", "Não identificados"]]
        .notna()
        .any(axis=1)
    ].copy()

    out = out.reset_index(drop=True)

    return out


# =========================================================
# PDF
# =========================================================

def tratar_tabela_pdf(table: list[list[Any]]) -> pd.DataFrame:
    """
    Trata uma tabela extraída do PDF pelo pdfplumber.

    A função é defensiva porque PDF costuma vir com:
    - células None;
    - cabeçalho quebrado;
    - colunas duplicadas;
    - linhas vazias.
    """
    if not table:
        return pd.DataFrame()

    cleaned_rows: list[list[str]] = []

    for row in table:
        if row is None:
            continue

        cleaned_row = [clean_display_text(cell) for cell in row]

        if any(cell for cell in cleaned_row):
            cleaned_rows.append(cleaned_row)

    if len(cleaned_rows) < 2:
        return pd.DataFrame()

    max_len = max(len(row) for row in cleaned_rows)
    normalized_rows = [row + [""] * (max_len - len(row)) for row in cleaned_rows]

    header = normalized_rows[0]
    body = normalized_rows[1:]

    df = pd.DataFrame(body, columns=make_unique_columns(header))
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, [str(col).strip() != "" for col in df.columns]]
    df = df.replace(r"^\s*$", pd.NA, regex=True)
    df = df.dropna(how="all")
    df = df.fillna("")
    df = df.reset_index(drop=True)

    return df


def extrair_tabelas_pdf(upload_pdf) -> pd.DataFrame:
    """
    Extrai tabelas de todas as páginas do PDF.
    """
    dfs: list[pd.DataFrame] = []

    with pdfplumber.open(upload_pdf) as pdf:
        if not pdf.pages:
            raise ValueError("O PDF enviado não possui páginas.")

        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()

            if not tables:
                continue

            for table_number, table in enumerate(tables, start=1):
                df_temp = tratar_tabela_pdf(table)

                if df_temp.empty:
                    continue

                df_temp["_pagina_pdf"] = page_number
                df_temp["_tabela_pdf"] = table_number
                dfs.append(df_temp)

    if not dfs:
        return pd.DataFrame()

    df_final = pd.concat(dfs, ignore_index=True, sort=False)
    df_final = df_final.fillna("")
    df_final = df_final.reset_index(drop=True)

    return df_final


def coluna_tem_numero(series: pd.Series) -> bool:
    """
    Verifica se a coluna tem pelo menos um valor numérico.
    """
    for value in series:
        if parse_numeric_value(value) is not None:
            return True

    return False


def encontrar_coluna_descricao(df: pd.DataFrame) -> str | None:
    """
    Localiza a coluna que contém o nome do indicador/procedimento.
    """
    if df is None or df.empty:
        return None

    for candidate in DESCRIPTION_COLUMN_CANDIDATES:
        for col in df.columns:
            if normalize_text(col) == candidate:
                return col

    ignored = {"_pagina_pdf", "_tabela_pdf"}

    for col in df.columns:
        if str(col) in ignored:
            continue

        col_norm = normalize_text(col)

        if col_norm in METADATA_COLUMN_NAMES:
            continue

        values = [clean_display_text(v) for v in df[col].tolist()]
        non_empty_values = [v for v in values if v]

        if not non_empty_values:
            continue

        numeric_count = sum(parse_numeric_value(v) is not None for v in non_empty_values)
        text_count = len(non_empty_values) - numeric_count

        if text_count >= numeric_count:
            return col

    return None


def competencia_coluna_eh_resumo(col: Any) -> bool:
    """
    Identifica colunas de resumo, como Total.
    """
    return normalize_text(col) in SUMMARY_COLUMN_NAMES


def identificar_colunas_competencia(
    df: pd.DataFrame,
    descricao_col: str | None = None,
) -> list[str]:
    """
    Identifica colunas de competência/mês/período no PDF.

    Regra:
    - colunas com valores numéricos são candidatas;
    - ignora metadados, descrição, página e tabela;
    - se existirem colunas mensais e coluna Total, remove Total para evitar duplicidade analítica.
    """
    if df is None or df.empty:
        return []

    ignored = {
        "_pagina_pdf",
        "_tabela_pdf",
    }

    if descricao_col:
        ignored.add(str(descricao_col))

    candidates: list[str] = []

    for col in df.columns:
        col_name = str(col)
        col_norm = normalize_text(col)

        if col_name in ignored:
            continue

        if col_norm in METADATA_COLUMN_NAMES and col_norm not in {
            "valor",
            "registro",
            "registros",
            "quantidade",
            "qtd",
            "total",
        }:
            continue

        if coluna_tem_numero(df[col]):
            candidates.append(col)

    non_summary = [col for col in candidates if not competencia_coluna_eh_resumo(col)]

    if non_summary:
        return non_summary

    return candidates


def descricao_padrao_por_indice(row_index: int) -> str:
    """
    Infere a descrição do relatório individual a partir da posição da linha.
    Mantém a lógica do seu sistema:
    - 3 primeiras linhas são cadastro;
    - demais linhas são produção.
    """
    if row_index < len(DESCRICOES_CADASTRO):
        return DESCRICOES_CADASTRO[row_index]

    prod_index = row_index - len(DESCRICOES_CADASTRO)

    if prod_index < len(DESCRICOES_PRODUCAO):
        return DESCRICOES_PRODUCAO[prod_index]

    return f"Indicador {row_index + 1}"


def obter_indicador_linha(
    row: pd.Series,
    row_index: int,
    descricao_col: str | None,
    usar_descricao_padrao: bool,
) -> str:
    """
    Define qual texto será gravado na coluna Tipo do banco.
    """
    if descricao_col:
        descricao = clean_display_text(row.get(descricao_col))

        if descricao and normalize_text(descricao) not in {"cadastro", "producao", "produção"}:
            return descricao

    if usar_descricao_padrao:
        return descricao_padrao_por_indice(row_index)

    for col in row.index:
        col_norm = normalize_text(col)

        if col_norm in {"_pagina_pdf", "_tabela_pdf"}:
            continue

        value = clean_display_text(row.get(col))

        if not value:
            continue

        if parse_numeric_value(value) is None:
            return value

    return f"Indicador {row_index + 1}"


def converter_pdf_largo_para_formato_banco(
    df_pdf: pd.DataFrame,
    *,
    ubs: str,
    categoria: str,
    usar_descricao_padrao: bool,
) -> pd.DataFrame:
    """
    Converte tabela larga extraída do PDF para o schema do Supabase.

    Entrada comum vinda do PDF:
    UBS | Categoria | Tipo/Descrição | Jan | Fev | Mar | ...

    Saída oficial:
    UBS | Categoria | Tipo | Competência | Valor | Identificados | Não identificados
    """
    if df_pdf is None or df_pdf.empty:
        return pd.DataFrame(columns=FINAL_COLUMNS)

    df_work = df_pdf.copy()
    df_work = df_work.drop(
        columns=[c for c in ["_pagina_pdf", "_tabela_pdf"] if c in df_work.columns],
        errors="ignore",
    )
    df_work = df_work.dropna(how="all")
    df_work = df_work.fillna("")
    df_work = df_work.reset_index(drop=True)

    if dataframe_is_final_schema(df_work):
        return padronizar_schema_final(
            df_work,
            ubs=ubs,
            categoria=categoria,
        )

    descricao_col = encontrar_coluna_descricao(df_work)
    competencia_cols = identificar_colunas_competencia(
        df=df_work,
        descricao_col=descricao_col,
    )

    if not competencia_cols:
        raise ValueError(
            "Não foi possível identificar colunas numéricas de competência no PDF. "
            "Verifique se o PDF foi gerado com tabela selecionável, e não como imagem."
        )

    registros: list[dict[str, Any]] = []

    for row_index, row in df_work.iterrows():
        indicador = obter_indicador_linha(
            row=row,
            row_index=row_index,
            descricao_col=descricao_col,
            usar_descricao_padrao=usar_descricao_padrao,
        )

        indicador_norm = normalize_text(indicador)

        if not indicador_norm:
            continue

        if indicador_norm in {
            "tipo",
            "descricao",
            "descrição",
            "indicador",
            "atividade",
            "procedimento",
        }:
            continue

        for competencia_col in competencia_cols:
            competencia = clean_display_text(competencia_col)
            valor = format_numeric_for_dataframe(row.get(competencia_col))

            if valor is None:
                continue

            registros.append(
                {
                    "UBS": ubs,
                    "Categoria": categoria,
                    "Tipo": indicador,
                    "Competência": competencia,
                    "Valor": valor,
                    "Identificados": None,
                    "Não identificados": None,
                }
            )

    df_long = pd.DataFrame(registros, columns=FINAL_COLUMNS)

    if df_long.empty:
        raise ValueError(
            "O PDF foi lido, mas nenhuma linha válida foi convertida para o formato do banco."
        )

    return padronizar_schema_final(df_long, ubs=ubs, categoria=categoria)


def processar_pdf_serie_historica(df_final: pd.DataFrame, ubs: str) -> pd.DataFrame:
    """
    Processa PDF no modo série histórica.

    Mesmo sem categoria profissional selecionada, o banco precisa de uma categoria
    para o dado não ficar solto no painel.
    """
    return converter_pdf_largo_para_formato_banco(
        df_pdf=df_final,
        ubs=ubs,
        categoria="Série histórica",
        usar_descricao_padrao=False,
    )


def processar_pdf_individual(
    df_final: pd.DataFrame,
    ubs: str,
    profissional: str,
) -> pd.DataFrame:
    """
    Processa PDF no modo produção individual.

    Correção principal:
    - não retorna mais a tabela larga do PDF;
    - transforma meses/competências em linhas;
    - coloca o indicador real na coluna Tipo;
    - entrega exatamente o schema esperado pelo Supabase.
    """
    return converter_pdf_largo_para_formato_banco(
        df_pdf=df_final,
        ubs=ubs,
        categoria=profissional,
        usar_descricao_padrao=True,
    )


def render_upload_pdf():
    """
    Renderiza a página de carregamento de PDF.

    Retorna:
    - DataFrame tratado no schema final;
    - nome sugerido do arquivo.
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

        upload_pdf.seek(0)
        df_extraido = extrair_tabelas_pdf(upload_pdf)

        if df_extraido.empty:
            st.warning("Nenhuma tabela válida foi encontrada no PDF.")
            return None, None

        with st.expander("Prévia técnica da tabela extraída do PDF", expanded=False):
            st.caption(
                f"Tabela bruta extraída: {len(df_extraido)} linhas e {len(df_extraido.columns)} colunas."
            )
            st.dataframe(df_extraido, use_container_width=True)

        if is_serie_historica:
            df_final = processar_pdf_serie_historica(
                df_final=df_extraido,
                ubs=ubs,
            )

            file_name = build_output_filename(
                ubs=ubs,
                profissional="serie_historica_pdf",
            )

            st.success("Série histórica em PDF tratada com sucesso!")

        else:
            df_final = processar_pdf_individual(
                df_final=df_extraido,
                ubs=ubs,
                profissional=profissional or "profissional_nao_informado",
            )

            file_name = build_output_filename(
                ubs=ubs,
                profissional=f"{profissional}_pdf",
            )

            st.success("Relatório individual em PDF tratado com sucesso!")

        st.markdown("### Dados prontos para submissão")
        st.caption(
            "Formato final: UBS | Categoria | Tipo | Competência | Valor | Identificados | Não identificados"
        )
        st.dataframe(df_final, use_container_width=True)

        return df_final, file_name

    except Exception as e:
        st.error(f"Erro ao processar o PDF: {e}")
        return None, None


# =========================================================
# MENSAGENS / VALIDAÇÃO UI
# =========================================================

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


# =========================================================
# CSV / XLSX
# =========================================================

def get_file_extension(uploaded_file) -> str:
    """
    Retorna a extensão do arquivo enviado.
    """
    if uploaded_file is None or not uploaded_file.name:
        return ""

    return uploaded_file.name.lower().split(".")[-1].strip()


def detectar_acs_csv(raw_bytes: bytes) -> bool:
    """
    Mantém a regra original do CSV:
    procura ACS na linha 12 do arquivo bruto.
    """
    linhas = raw_bytes.splitlines()

    if len(linhas) < 12:
        return False

    linha_12 = linhas[11].decode("latin-1", errors="ignore")
    return "ACS" in linha_12.upper()


def detectar_acs_excel(raw_bytes: bytes) -> bool:
    """
    Tenta detectar ACS nas primeiras linhas do XLSX/XLS.
    """
    try:
        df_preview = pd.read_excel(
            io.BytesIO(raw_bytes),
            header=None,
            nrows=15,
        )

        texto_preview = " ".join(
            df_preview.fillna("").astype(str).values.flatten().tolist()
        )

        return "ACS" in texto_preview.upper()

    except Exception:
        return False


def limpar_colunas_importadas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove colunas automáticas/vazias vindas de CSV/XLSX.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out.columns = make_unique_columns(list(out.columns))

    out = out.loc[:, ~pd.Index(out.columns).astype(str).str.contains("^Unnamed", case=False)]
    out = out.dropna(axis=1, how="all")
    out = out.fillna("")
    out = out.reset_index(drop=True)

    return out


def ler_csv_tratado(
    raw_bytes: bytes,
    tipo_relatorio: str,
    ubs: str,
    profissional: str | None,
) -> tuple[pd.DataFrame | None, str | None]:
    """
    Lê e trata arquivo CSV mantendo a lógica original.

    A correção do PDF não altera essa regra porque ela já estava integrada
    ao fluxo existente do sistema.
    """
    linhas = raw_bytes.splitlines()

    if len(linhas) < 12:
        st.error("O arquivo enviado não possui a estrutura mínima esperada.")
        return None, None

    is_acs = detectar_acs_csv(raw_bytes)
    upload_buffer = io.BytesIO(raw_bytes)

    if tipo_relatorio == "Série histórica (relatório geral)":
        df = pd.read_csv(
            upload_buffer,
            encoding="latin-1",
            sep=";",
            skiprows=19,
        )

        df = limpar_colunas_importadas(df)
        df["UBS"] = ubs

        colunas = ["UBS"] + [c for c in df.columns if c != "UBS"]
        df = df[colunas]

        file_name = build_output_filename(
            ubs=ubs,
            profissional="serie_historica",
        )

        return df, file_name

    df = pd.read_csv(
        upload_buffer,
        encoding="latin-1",
        sep=";",
        skiprows=18,
    )

    df = limpar_colunas_importadas(df)

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

    return df, file_name


def ler_excel_tratado(
    raw_bytes: bytes,
    tipo_relatorio: str,
    ubs: str,
    profissional: str | None,
) -> tuple[pd.DataFrame | None, str | None]:
    """
    Lê e trata arquivo XLSX/XLS usando a mesma regra estrutural do CSV.
    """
    is_acs = detectar_acs_excel(raw_bytes)

    if tipo_relatorio == "Série histórica (relatório geral)":
        df = pd.read_excel(
            io.BytesIO(raw_bytes),
            skiprows=19,
        )

        df = limpar_colunas_importadas(df)
        df["UBS"] = ubs

        colunas = ["UBS"] + [c for c in df.columns if c != "UBS"]
        df = df[colunas]

        file_name = build_output_filename(
            ubs=ubs,
            profissional="serie_historica",
        )

        return df, file_name

    df = pd.read_excel(
        io.BytesIO(raw_bytes),
        skiprows=18,
    )

    df = limpar_colunas_importadas(df)

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

    return df, file_name


# =========================================================
# RENDER PRINCIPAL
# =========================================================

def render_obter_data():
    """
    Renderiza a área principal de submissão.

    Retorna:
    - dataframe tratado;
    - nome sugerido para o arquivo final.
    """
    with st.sidebar:
        logo_path = Path("./assets/logo2.PNG")

        if logo_path.exists():
            st.image(str(logo_path), width=200)

        st.markdown("# MENU")

        pagina = st.radio(
            "Ir para:",
            ["Carregar CSV/XLSX", "Carregar PDF"],
            key="menu_pagina",
        )

    if pagina == "Carregar PDF":
        return render_upload_pdf()

    st.title("Carregar CSV/XLSX")

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
        label="Faça o upload do arquivo CSV ou XLSX",
        type=["csv", "xlsx", "xls"],
        key="csv_xlsx_upload",
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
        file_extension = get_file_extension(upload)

        if file_extension == "csv":
            df, file_name = ler_csv_tratado(
                raw_bytes=raw_bytes,
                tipo_relatorio=tipo_relatorio,
                ubs=ubs,
                profissional=profissional,
            )

        elif file_extension in ["xlsx", "xls"]:
            df, file_name = ler_excel_tratado(
                raw_bytes=raw_bytes,
                tipo_relatorio=tipo_relatorio,
                ubs=ubs,
                profissional=profissional,
            )

        else:
            st.error("Formato de arquivo não suportado. Envie CSV, XLSX ou XLS.")
            return None, None

        if df is None or df.empty:
            st.error("Nenhum dado válido foi encontrado no arquivo enviado.")
            return None, None

        st.success("Dados carregados com sucesso!")
        st.dataframe(df, use_container_width=True)

        return df, file_name

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        return None, None


# =========================================================
# NOMES DE ARQUIVO
# =========================================================

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