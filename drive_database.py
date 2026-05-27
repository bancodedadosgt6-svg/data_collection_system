from __future__ import annotations

import io
import unicodedata
from typing import Any

import pandas as pd
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from settings import get_google_drive_service


BANCO_COLUNAS = [
    "ubs",
    "categoria",
    "tipo",
    "competencia",
    "valor",
    "identificados",
    "nao_identificados",
]

ABA_DADOS = "dados"

MIMETYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

UBS_FOLDER_NAMES = {
    "Gama": "Gama",
    "Jardins Mangueiral": "Jardins-Mangueral",
    "Jardins-Mangueral": "Jardins-Mangueral",
    "Santa Maria": "Santa-Maria",
    "Santa-Maria": "Santa-Maria",
}

UBS_BANCO_FILES = {
    "Gama": "banco_gama.xlsx",
    "Jardins Mangueiral": "banco_jardins_mangueral.xlsx",
    "Jardins-Mangueral": "banco_jardins_mangueral.xlsx",
    "Santa Maria": "banco_santa_maria.xlsx",
    "Santa-Maria": "banco_santa_maria.xlsx",
}


def normalizar_texto(valor: Any) -> str:
    """
    Normaliza textos para comparação de nomes de colunas e UBS.
    Remove acentos, espaços extras e caracteres especiais comuns.
    """
    if valor is None:
        return ""

    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(char for char in texto if not unicodedata.combining(char))

    replacements = {
        " ": "_",
        "-": "_",
        "/": "_",
        "\\": "_",
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
        "\n": "_",
        "\r": "_",
        "\t": "_",
    }

    for old, new in replacements.items():
        texto = texto.replace(old, new)

    while "__" in texto:
        texto = texto.replace("__", "_")

    return texto.strip("_")


def normalizar_nome_ubs(ubs: str) -> str:
    """
    Valida e normaliza o nome da UBS para os nomes mapeados no Drive.
    """
    if not ubs or not str(ubs).strip():
        raise ValueError("UBS não informada.")

    ubs = str(ubs).strip()

    if ubs in UBS_FOLDER_NAMES:
        return ubs

    ubs_norm = normalizar_texto(ubs)

    aliases = {
        "gama": "Gama",
        "santa_maria": "Santa Maria",
        "santa_maria_": "Santa Maria",
        "jardins_mangueiral": "Jardins Mangueiral",
        "jardins_mangueral": "Jardins Mangueiral",
    }

    if ubs_norm in aliases:
        return aliases[ubs_norm]

    raise ValueError(f"UBS não mapeada para pasta do Drive: {ubs}")


def escapar_query_drive(valor: str) -> str:
    """
    Escapa aspas simples para uso seguro na query da API do Google Drive.
    """
    return str(valor).replace("'", "\\'")


def buscar_pasta_por_nome(service, folder_name: str) -> str | None:
    """
    Busca uma pasta no Google Drive pelo nome.
    A pasta precisa estar acessível para a Service Account.
    """
    folder_name = escapar_query_drive(folder_name)

    query = (
        "mimeType='application/vnd.google-apps.folder' "
        f"and name='{folder_name}' "
        "and trashed=false"
    )

    response = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )

    files = response.get("files", [])

    if not files:
        return None

    return files[0]["id"]


def buscar_arquivo_na_pasta(service, folder_id: str, file_name: str) -> str | None:
    """
    Busca o arquivo XLSX do banco dentro da pasta da UBS.
    """
    file_name = escapar_query_drive(file_name)

    query = (
        f"'{folder_id}' in parents "
        f"and name='{file_name}' "
        "and trashed=false"
    )

    response = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id, name, mimeType)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )

    files = response.get("files", [])

    if not files:
        return None

    return files[0]["id"]


def dataframe_para_xlsx_stream(df: pd.DataFrame) -> io.BytesIO:
    """
    Converte DataFrame para um arquivo XLSX em memória.
    """
    file_stream = io.BytesIO()

    with pd.ExcelWriter(file_stream, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=ABA_DADOS, index=False)

    file_stream.seek(0)
    return file_stream


def criar_xlsx_vazio_na_pasta(service, folder_id: str, file_name: str) -> str:
    """
    Cria um banco XLSX vazio na pasta da UBS, caso ainda não exista.
    """
    df_vazio = pd.DataFrame(columns=BANCO_COLUNAS)
    file_stream = dataframe_para_xlsx_stream(df_vazio)

    file_metadata = {
        "name": file_name,
        "parents": [folder_id],
    }

    media = MediaIoBaseUpload(
        file_stream,
        mimetype=MIMETYPE_XLSX,
        resumable=False,
    )

    uploaded_file = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, name",
            supportsAllDrives=True,
        )
        .execute()
    )

    return uploaded_file["id"]


def baixar_xlsx_drive(service, file_id: str) -> pd.DataFrame:
    """
    Baixa o XLSX atual do Google Drive e lê a aba 'dados'.
    """
    request = service.files().get_media(fileId=file_id)

    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    file_stream.seek(0)

    try:
        df = pd.read_excel(file_stream, sheet_name=ABA_DADOS, engine="openpyxl")
    except ValueError:
        file_stream.seek(0)
        df = pd.read_excel(file_stream, engine="openpyxl")
    except Exception:
        df = pd.DataFrame(columns=BANCO_COLUNAS)

    if df is None:
        df = pd.DataFrame(columns=BANCO_COLUNAS)

    return df


def atualizar_xlsx_drive(service, file_id: str, df: pd.DataFrame) -> None:
    """
    Atualiza o mesmo arquivo XLSX no Google Drive.
    Não cria outro arquivo.
    """
    file_stream = dataframe_para_xlsx_stream(df)

    media = MediaIoBaseUpload(
        file_stream,
        mimetype=MIMETYPE_XLSX,
        resumable=False,
    )

    (
        service.files()
        .update(
            fileId=file_id,
            media_body=media,
            fields="id, name",
            supportsAllDrives=True,
        )
        .execute()
    )


def encontrar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
    """
    Encontra uma coluna no DataFrame por comparação normalizada.
    """
    mapa_colunas = {
        normalizar_texto(col): col
        for col in df.columns
    }

    for candidato in candidatos:
        candidato_norm = normalizar_texto(candidato)

        if candidato_norm in mapa_colunas:
            return mapa_colunas[candidato_norm]

    return None


def detectar_coluna_valor(df: pd.DataFrame) -> str | None:
    """
    Tenta detectar a coluna principal de valor/quantidade.
    """
    candidatos = [
        "valor",
        "Valor",
        "total",
        "Total",
        "quantidade",
        "Quantidade",
        "qtd",
        "Qtd",
        "produção",
        "Producao",
        "Produção",
    ]

    coluna = encontrar_coluna(df, candidatos)

    if coluna:
        return coluna

    # Fallback: pega a primeira coluna numérica que não seja identificados/não identificados.
    colunas_proibidas = {
        "identificados",
        "identificado",
        "nao_identificados",
        "nao_identificado",
        "não_identificados",
        "não_identificado",
    }

    for col in df.columns:
        col_norm = normalizar_texto(col)

        if col_norm in colunas_proibidas:
            continue

        serie_numerica = pd.to_numeric(df[col], errors="coerce")

        if serie_numerica.notna().sum() > 0:
            return col

    return None


def padronizar_dataframe_para_banco(df: pd.DataFrame, ubs: str) -> pd.DataFrame:
    """
    Converte o DataFrame tratado pelo sistema para o padrão oficial do banco:

    ubs, categoria, tipo, competencia, valor, identificados, nao_identificados
    """
    if df is None or df.empty:
        raise ValueError("DataFrame vazio. Não há dados para alimentar o banco.")

    df = df.copy()

    col_ubs = encontrar_coluna(df, ["ubs", "UBS"])
    col_categoria = encontrar_coluna(df, ["categoria", "Categoria"])
    col_tipo = encontrar_coluna(df, ["tipo", "Tipo"])

    col_competencia = encontrar_coluna(
        df,
        [
            "competencia",
            "Competência",
            "data",
            "Data",
            "periodo",
            "Período",
            "período",
            "mes",
            "Mês",
            "mês",
            "ano_mes",
            "Ano/Mês",
        ],
    )

    col_valor = detectar_coluna_valor(df)

    col_identificados = encontrar_coluna(
        df,
        [
            "identificados",
            "Identificados",
            "identificado",
            "Identificado",
        ],
    )

    col_nao_identificados = encontrar_coluna(
        df,
        [
            "nao_identificados",
            "não_identificados",
            "Não identificados",
            "Nao identificados",
            "nao identificado",
            "não identificado",
            "Não identificado",
            "Nao identificado",
            "nao_identificado",
            "não_identificado",
        ],
    )

    df_banco = pd.DataFrame(index=df.index)

    df_banco["ubs"] = df[col_ubs] if col_ubs else ubs
    df_banco["categoria"] = df[col_categoria] if col_categoria else ""
    df_banco["tipo"] = df[col_tipo] if col_tipo else ""
    df_banco["competencia"] = df[col_competencia] if col_competencia else ""
    df_banco["valor"] = df[col_valor] if col_valor else ""
    df_banco["identificados"] = df[col_identificados] if col_identificados else ""
    df_banco["nao_identificados"] = (
        df[col_nao_identificados] if col_nao_identificados else ""
    )

    df_banco = df_banco[BANCO_COLUNAS]

    for col in BANCO_COLUNAS:
        df_banco[col] = df_banco[col].fillna("")

    return df_banco


def preparar_banco_antigo(df_antigo: pd.DataFrame) -> pd.DataFrame:
    """
    Garante que o banco antigo esteja no padrão oficial.
    """
    if df_antigo is None or df_antigo.empty:
        return pd.DataFrame(columns=BANCO_COLUNAS)

    df_antigo = df_antigo.copy()

    rename_map = {}

    for coluna in df_antigo.columns:
        coluna_norm = normalizar_texto(coluna)

        for coluna_oficial in BANCO_COLUNAS:
            if coluna_norm == normalizar_texto(coluna_oficial):
                rename_map[coluna] = coluna_oficial

    df_antigo = df_antigo.rename(columns=rename_map)

    for col in BANCO_COLUNAS:
        if col not in df_antigo.columns:
            df_antigo[col] = ""

    df_antigo = df_antigo[BANCO_COLUNAS]

    for col in BANCO_COLUNAS:
        df_antigo[col] = df_antigo[col].fillna("")

    return df_antigo


def limpar_linhas_vazias(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove linhas completamente vazias do banco final.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=BANCO_COLUNAS)

    df = df.copy()

    for col in BANCO_COLUNAS:
        if col not in df.columns:
            df[col] = ""

    df = df[BANCO_COLUNAS]
    df = df.fillna("")

    mascara_vazia = df.apply(
        lambda row: all(str(valor).strip() == "" for valor in row),
        axis=1,
    )

    return df.loc[~mascara_vazia].reset_index(drop=True)


def alimentar_banco_xlsx_drive(df_novo: pd.DataFrame, ubs: str) -> dict:
    """
    Alimenta o banco XLSX único da UBS no Google Drive.

    Fluxo:
    1. localiza pasta da UBS;
    2. localiza ou cria banco_xxx.xlsx;
    3. baixa a aba 'dados';
    4. padroniza os dados novos;
    5. concatena dados antigos + novos;
    6. atualiza o mesmo XLSX no Drive.

    Importante:
    - não apaga dados antigos;
    - não remove duplicados automaticamente;
    - sempre mantém a aba 'dados';
    - sempre mantém as colunas oficiais.
    """
    ubs_normalizada = normalizar_nome_ubs(ubs)

    folder_name = UBS_FOLDER_NAMES[ubs_normalizada]
    banco_file_name = UBS_BANCO_FILES[ubs_normalizada]

    service = get_google_drive_service()

    folder_id = buscar_pasta_por_nome(
        service=service,
        folder_name=folder_name,
    )

    if not folder_id:
        raise FileNotFoundError(
            f"Pasta '{folder_name}' não encontrada no Google Drive. "
            "Verifique se a pasta existe e se foi compartilhada com a Service Account como Editor."
        )

    file_id = buscar_arquivo_na_pasta(
        service=service,
        folder_id=folder_id,
        file_name=banco_file_name,
    )

    arquivo_criado = False

    if not file_id:
        file_id = criar_xlsx_vazio_na_pasta(
            service=service,
            folder_id=folder_id,
            file_name=banco_file_name,
        )
        arquivo_criado = True

    df_antigo = baixar_xlsx_drive(
        service=service,
        file_id=file_id,
    )
    df_antigo = preparar_banco_antigo(df_antigo)

    df_novo_padronizado = padronizar_dataframe_para_banco(
        df=df_novo,
        ubs=ubs_normalizada,
    )

    df_final = pd.concat(
        [df_antigo, df_novo_padronizado],
        ignore_index=True,
    )

    df_final = limpar_linhas_vazias(df_final)
    df_final = df_final[BANCO_COLUNAS]

    atualizar_xlsx_drive(
        service=service,
        file_id=file_id,
        df=df_final,
    )

    return {
        "ubs": ubs_normalizada,
        "pasta": folder_name,
        "arquivo": banco_file_name,
        "aba": ABA_DADOS,
        "arquivo_criado": arquivo_criado,
        "linhas_anteriores": len(df_antigo),
        "linhas_novas": len(df_novo_padronizado),
        "linhas_totais": len(df_final),
    }