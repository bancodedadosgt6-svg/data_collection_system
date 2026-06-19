from __future__ import annotations

import hashlib
import math
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from settings import (
    get_ubs_display_name,
    normalize_ubs_slug,
)
from supabase_client import (
    get_authenticated_supabase_client,
    get_current_user_id,
    get_ubs_by_slug,
    is_authenticated,
)


# =========================================================
# CONFIGURAÇÕES
# =========================================================

REGISTROS_TABLE = "registros_saude_alimentar"
SUBMISSOES_TABLE = "submissoes"

INSERT_CHUNK_SIZE = 500
HASH_SELECT_CHUNK_SIZE = 300


# =========================================================
# HELPERS GERAIS
# =========================================================

def chunk_list(items: list[Any], size: int) -> Iterable[list[Any]]:
    """
    Divide uma lista em blocos menores.
    """
    for i in range(0, len(items), size):
        yield items[i:i + size]


def normalize_column_name(value: Any) -> str:
    """
    Normaliza nome de coluna para comparação interna.
    """
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))

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
        text = text.replace(old, new)

    while "__" in text:
        text = text.replace("__", "_")

    return text.strip("_")


def clean_value(value: Any) -> Any:
    """
    Converte valores pandas/numpy para tipos compatíveis com JSON/PostgREST.
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def clean_text(value: Any) -> Optional[str]:
    """
    Limpa campo textual.
    """
    value = clean_value(value)

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if text.lower() in {"none", "nan", "null"}:
        return None

    return text


def clean_numeric(value: Any) -> Optional[float]:
    """
    Converte valor para número compatível com numeric no Supabase.
    """
    value = clean_value(value)

    if value is None:
        return None

    if isinstance(value, str):
        text = value.strip()

        if not text:
            return None

        text = text.replace(".", "").replace(",", ".") if "," in text else text

        try:
            return float(text)
        except Exception:
            return None

    try:
        return float(value)
    except Exception:
        return None


def canonical_hash_value(value: Any) -> str:
    """
    Padroniza valor antes de compor o hash.
    """
    value = clean_value(value)

    if value is None:
        return ""

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.10g}"

    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = " ".join(text.split())

    return text


def build_hash_registro(row: dict) -> str:
    """
    Gera hash único do registro.

    A ideia é impedir duplicidade caso o mesmo arquivo/dado seja enviado
    mais de uma vez.

    O hash considera o conteúdo lógico do registro, não o nome do arquivo.
    """
    fields = [
        "ubs",
        "categoria",
        "tipo",
        "competencia",
        "valor",
        "identificados",
        "nao_identificados",
    ]

    raw = "|".join(canonical_hash_value(row.get(field)) for field in fields)

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# =========================================================
# NORMALIZAÇÃO DO DATAFRAME
# =========================================================

def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza as colunas vindas do sistema de tratamento.

    Entrada aceita:
    - ubs / UBS
    - categoria / Categoria
    - tipo / Tipo
    - competencia / Competência
    - valor / Valor / Registro
    - identificados / Identificados
    - nao_identificados / Não identificados
    """
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    rename_by_normalized = {
        "ubs": "ubs",
        "unidade": "ubs",
        "unidade_basica": "ubs",
        "unidade_basica_de_saude": "ubs",

        "categoria": "categoria",
        "categoria_profissional": "categoria",
        "profissional": "categoria",

        "tipo": "tipo",
        "tipo_relatorio": "tipo",
        "indicador": "tipo",
        "descricao": "tipo",
        "descrição": "tipo",

        "competencia": "competencia",
        "mes": "competencia",
        "mês": "competencia",
        "periodo": "competencia",
        "período": "competencia",

        "valor": "valor",
        "registro": "valor",
        "registros": "valor",
        "quantidade": "valor",
        "qtd": "valor",
        "total": "valor",

        "identificados": "identificados",
        "identificado": "identificados",

        "nao_identificados": "nao_identificados",
        "nao_identificado": "nao_identificados",
        "não_identificados": "nao_identificados",
        "não_identificado": "nao_identificados",
    }

    rename_map = {}

    for col in out.columns:
        col_norm = normalize_column_name(col)

        if col_norm in rename_by_normalized:
            rename_map[col] = rename_by_normalized[col_norm]

    out = out.rename(columns=rename_map)

    expected_columns = [
        "ubs",
        "categoria",
        "tipo",
        "competencia",
        "valor",
        "identificados",
        "nao_identificados",
    ]

    for col in expected_columns:
        if col not in out.columns:
            out[col] = None

    out = out[expected_columns].copy()

    return out


def preparar_dataframe_para_supabase(
    df: pd.DataFrame,
    ubs_nome: str | None = None,
) -> pd.DataFrame:
    """
    Prepara o dataframe final para gravação no Supabase.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    out = normalize_dataframe_columns(df)

    if ubs_nome:
        out["ubs"] = get_ubs_display_name(ubs_nome)

    if "ubs" not in out.columns or out["ubs"].isna().all():
        raise ValueError("Não foi possível identificar a UBS dos dados enviados.")

    out["ubs"] = out["ubs"].apply(get_ubs_display_name)

    out["categoria"] = out["categoria"].apply(clean_text)
    out["tipo"] = out["tipo"].apply(clean_text)
    out["competencia"] = out["competencia"].apply(clean_text)

    out["valor"] = out["valor"].apply(clean_numeric)
    out["identificados"] = out["identificados"].apply(clean_numeric)
    out["nao_identificados"] = out["nao_identificados"].apply(clean_numeric)

    # Remove linhas completamente vazias do ponto de vista analítico.
    out = out[
        out[["categoria", "tipo", "competencia", "valor", "identificados", "nao_identificados"]]
        .notna()
        .any(axis=1)
    ].copy()

    out = out.reset_index(drop=True)

    return out


# =========================================================
# CONSULTAS SUPABASE
# =========================================================

def get_ubs_id_by_name(ubs_nome: str) -> str:
    """
    Retorna o UUID da UBS no Supabase a partir do nome/slug.
    """
    slug = normalize_ubs_slug(ubs_nome)

    if not slug:
        raise ValueError("UBS inválida ou não informada.")

    ubs = get_ubs_by_slug(slug)

    if not ubs:
        raise ValueError(
            f"UBS '{ubs_nome}' não encontrada no Supabase. "
            "Verifique se ela está cadastrada e ativa na tabela public.ubs."
        )

    return str(ubs["id"])


def buscar_hashes_existentes(hashes: list[str]) -> set[str]:
    """
    Busca quais hashes já existem na tabela registros_saude_alimentar.
    """
    if not hashes:
        return set()

    client = get_authenticated_supabase_client()
    encontrados: set[str] = set()

    for batch in chunk_list(hashes, HASH_SELECT_CHUNK_SIZE):
        response = (
            client.table(REGISTROS_TABLE)
            .select("hash_registro")
            .in_("hash_registro", batch)
            .execute()
        )

        for item in response.data or []:
            hash_value = item.get("hash_registro")
            if hash_value:
                encontrados.add(str(hash_value))

    return encontrados


def criar_submissao(
    *,
    ubs_id: str,
    user_id: str,
    arquivo_nome: str | None,
    tipo_relatorio: str | None,
    categoria_profissional: str | None,
    linhas_recebidas: int,
    linhas_inseridas: int,
    linhas_duplicadas: int,
    status: str = "processado",
    mensagem: str | None = None,
) -> dict:
    """
    Cria o histórico da submissão.
    """
    client = get_authenticated_supabase_client()

    payload = {
        "ubs_id": ubs_id,
        "user_id": user_id,
        "arquivo_nome": clean_text(arquivo_nome),
        "tipo_relatorio": clean_text(tipo_relatorio),
        "categoria_profissional": clean_text(categoria_profissional),
        "linhas_recebidas": int(linhas_recebidas or 0),
        "linhas_inseridas": int(linhas_inseridas or 0),
        "linhas_duplicadas": int(linhas_duplicadas or 0),
        "status": status,
        "mensagem": clean_text(mensagem),
    }

    response = (
        client.table(SUBMISSOES_TABLE)
        .insert(payload)
        .execute()
    )

    data = response.data or []

    if not data:
        raise RuntimeError("Não foi possível registrar a submissão no Supabase.")

    return data[0]


def inserir_registros(registros: list[dict]) -> int:
    """
    Insere registros na tabela principal.
    """
    if not registros:
        return 0

    client = get_authenticated_supabase_client()
    total_inserted = 0

    for batch in chunk_list(registros, INSERT_CHUNK_SIZE):
        response = (
            client.table(REGISTROS_TABLE)
            .insert(batch)
            .execute()
        )

        total_inserted += len(response.data or [])

    return total_inserted


# =========================================================
# PREPARAÇÃO DE REGISTROS
# =========================================================

def dataframe_to_registros(
    *,
    df: pd.DataFrame,
    ubs_id: str,
    user_id: str,
    submissao_id: str | None = None,
    arquivo_origem: str | None = None,
) -> list[dict]:
    """
    Converte dataframe tratado em lista de registros para o Supabase.
    """
    registros: list[dict] = []

    for _, row in df.iterrows():
        base = {
            "ubs": clean_text(row.get("ubs")),
            "categoria": clean_text(row.get("categoria")),
            "tipo": clean_text(row.get("tipo")),
            "competencia": clean_text(row.get("competencia")),
            "valor": clean_numeric(row.get("valor")),
            "identificados": clean_numeric(row.get("identificados")),
            "nao_identificados": clean_numeric(row.get("nao_identificados")),
        }

        hash_registro = build_hash_registro(base)

        registro = {
            "ubs_id": ubs_id,
            "submissao_id": submissao_id,
            "user_id": user_id,

            "ubs": base["ubs"],
            "categoria": base["categoria"],
            "tipo": base["tipo"],
            "competencia": base["competencia"],

            "valor": base["valor"],
            "identificados": base["identificados"],
            "nao_identificados": base["nao_identificados"],

            "arquivo_origem": clean_text(arquivo_origem),
            "hash_registro": hash_registro,
        }

        registros.append(registro)

    return registros


# =========================================================
# FUNÇÃO PRINCIPAL DE ALIMENTAÇÃO DO BANCO
# =========================================================

def alimentar_banco_supabase(
    df: pd.DataFrame,
    ubs_nome: str | None = None,
    arquivo_nome: str | None = None,
    tipo_relatorio: str | None = None,
    categoria_profissional: str | None = None,
) -> Dict[str, Any]:
    """
    Alimenta o banco Supabase com os dados tratados.

    Substitui a antiga lógica:
    - alimentar_banco_xlsx_drive()

    Nova lógica:
    1. valida autenticação;
    2. identifica UBS;
    3. padroniza dataframe;
    4. gera hash por registro;
    5. remove duplicidades já existentes;
    6. cria registro em submissoes;
    7. insere registros novos em registros_saude_alimentar.
    """
    if df is None or df.empty:
        raise ValueError("DataFrame vazio. Não há dados para enviar.")

    if not is_authenticated():
        raise PermissionError(
            "Usuário não autenticado no Supabase. "
            "Faça login antes de submeter dados."
        )

    user_id = get_current_user_id()

    if not user_id:
        raise PermissionError("Não foi possível identificar o usuário autenticado.")

    df_preparado = preparar_dataframe_para_supabase(
        df=df,
        ubs_nome=ubs_nome,
    )

    if df_preparado.empty:
        raise ValueError("Após o tratamento, não restaram registros válidos para envio.")

    ubs_base = ubs_nome or df_preparado["ubs"].dropna().iloc[0]
    ubs_display = get_ubs_display_name(ubs_base)
    ubs_id = get_ubs_id_by_name(ubs_display)

    registros_sem_submissao = dataframe_to_registros(
        df=df_preparado,
        ubs_id=ubs_id,
        user_id=user_id,
        submissao_id=None,
        arquivo_origem=arquivo_nome,
    )

    hashes = [item["hash_registro"] for item in registros_sem_submissao]
    hashes_existentes = buscar_hashes_existentes(hashes)

    registros_novos_sem_submissao = [
        item for item in registros_sem_submissao
        if item["hash_registro"] not in hashes_existentes
    ]

    linhas_recebidas = len(registros_sem_submissao)
    linhas_duplicadas = linhas_recebidas - len(registros_novos_sem_submissao)
    linhas_planejadas_insercao = len(registros_novos_sem_submissao)

    submissao = criar_submissao(
        ubs_id=ubs_id,
        user_id=user_id,
        arquivo_nome=arquivo_nome,
        tipo_relatorio=tipo_relatorio,
        categoria_profissional=categoria_profissional,
        linhas_recebidas=linhas_recebidas,
        linhas_inseridas=linhas_planejadas_insercao,
        linhas_duplicadas=linhas_duplicadas,
        status="processado",
        mensagem=(
            "Submissão processada com sucesso."
            if linhas_planejadas_insercao > 0
            else "Todos os registros enviados já existiam no banco."
        ),
    )

    submissao_id = submissao.get("id")

    registros_novos = []

    for item in registros_novos_sem_submissao:
        novo = dict(item)
        novo["submissao_id"] = submissao_id
        registros_novos.append(novo)

    linhas_inseridas_reais = inserir_registros(registros_novos)

    return {
        "success": True,
        "message": (
            "Dados enviados ao Supabase com sucesso."
            if linhas_inseridas_reais > 0
            else "Nenhum dado novo foi inserido. Os registros já existiam no banco."
        ),
        "ubs": ubs_display,
        "ubs_id": ubs_id,
        "submissao_id": submissao_id,
        "arquivo_nome": arquivo_nome,
        "linhas_recebidas": linhas_recebidas,
        "linhas_inseridas": linhas_inseridas_reais,
        "linhas_duplicadas": linhas_duplicadas,
    }


# =========================================================
# CONSULTAS DE APOIO / DIAGNÓSTICO
# =========================================================

def contar_registros_por_ubs() -> list[dict]:
    """
    Consulta simples para diagnóstico.
    Retorna registros agrupados por UBS no lado do Python.
    """
    client = get_authenticated_supabase_client()

    response = (
        client.table(REGISTROS_TABLE)
        .select("ubs")
        .execute()
    )

    data = response.data or []

    if not data:
        return []

    df = pd.DataFrame(data)

    if df.empty or "ubs" not in df.columns:
        return []

    resumo = (
        df.groupby("ubs", dropna=False)
        .size()
        .reset_index(name="total_registros")
        .sort_values("ubs")
    )

    return resumo.to_dict(orient="records")


def buscar_ultimas_submissoes(limit: int = 10) -> list[dict]:
    """
    Busca as últimas submissões do usuário autenticado.
    """
    client = get_authenticated_supabase_client()

    response = (
        client.table(SUBMISSOES_TABLE)
        .select(
            "id,arquivo_nome,tipo_relatorio,categoria_profissional,"
            "linhas_recebidas,linhas_inseridas,linhas_duplicadas,"
            "status,mensagem,created_at"
        )
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return response.data or []