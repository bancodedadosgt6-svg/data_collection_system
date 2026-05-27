from __future__ import annotations

import io
import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv


load_dotenv()


APP_TITLE = "Sistema de Submissão de Dados em Saúde Alimentar"
APP_SUBTITLE = "Aplicação de upload, tratamento e envio de dados para o Google Drive"

GOOGLE_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
]


def get_secret_or_env(key: str, default=None):
    """
    Busca primeiro no Streamlit Secrets e depois no .env.
    Funciona localmente e no deploy.
    """
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    return os.getenv(key, default)


GOOGLE_DRIVE_ENABLED = str(
    get_secret_or_env("GOOGLE_DRIVE_ENABLED", "false")
).lower() == "true"

GOOGLE_OAUTH_CREDENTIALS_FILE = get_secret_or_env(
    "GOOGLE_OAUTH_CREDENTIALS_FILE",
    "credentials.json",
)

GOOGLE_OAUTH_TOKEN_FILE = get_secret_or_env(
    "GOOGLE_OAUTH_TOKEN_FILE",
    "token.json",
)


def load_css(css_file: str) -> None:
    if not os.path.exists(css_file):
        return

    with open(css_file, "r", encoding="utf-8") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True,
        )


def get_secret_json(key: str) -> dict | None:
    """
    Lê JSON armazenado no secrets.toml como string multilinha.

    Exemplo esperado:
    GOOGLE_OAUTH_TOKEN_JSON = \"\"\"
    { ... }
    \"\"\"
    """
    try:
        value = st.secrets.get(key)
    except Exception:
        return None

    if not value:
        return None

    if isinstance(value, dict):
        return dict(value)

    try:
        return json.loads(str(value))
    except json.JSONDecodeError as e:
        raise ValueError(
            f"O segredo {key} não contém um JSON válido. "
            f"Revise aspas, vírgulas e chaves no secrets.toml. Erro: {e}"
        ) from e


def load_json_file(file_path: str) -> dict | None:
    """
    Lê um arquivo JSON local, se existir.
    """
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_token_json_to_file(token_data: str) -> None:
    """
    Salva token.json localmente.
    No deploy, normalmente o token vem de st.secrets.
    """
    with open(GOOGLE_OAUTH_TOKEN_FILE, "w", encoding="utf-8") as token_file:
        token_file.write(token_data)


@st.cache_resource(show_spinner=False)
def get_google_drive_service():
    """
    Cria o serviço do Google Drive.

    Prioridade:
    1. Usa GOOGLE_OAUTH_TOKEN_JSON do Streamlit Secrets.
    2. Usa token.json local, se existir.
    3. Se não houver token válido, usa credentials.json local ou
       GOOGLE_OAUTH_CREDENTIALS_JSON para abrir OAuth local.

    No deploy, o ideal é já existir GOOGLE_OAUTH_TOKEN_JSON.
    """
    if not GOOGLE_DRIVE_ENABLED:
        raise RuntimeError(
            "Google Drive desabilitado. Configure GOOGLE_DRIVE_ENABLED=true."
        )

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None

    token_from_secrets = get_secret_json("GOOGLE_OAUTH_TOKEN_JSON")
    credentials_from_secrets = get_secret_json("GOOGLE_OAUTH_CREDENTIALS_JSON")

    if token_from_secrets:
        creds = Credentials.from_authorized_user_info(
            token_from_secrets,
            GOOGLE_DRIVE_SCOPES,
        )

    elif os.path.exists(GOOGLE_OAUTH_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            GOOGLE_OAUTH_TOKEN_FILE,
            GOOGLE_DRIVE_SCOPES,
        )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if credentials_from_secrets:
            flow = InstalledAppFlow.from_client_config(
                credentials_from_secrets,
                GOOGLE_DRIVE_SCOPES,
            )

        else:
            if not os.path.exists(GOOGLE_OAUTH_CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Arquivo de credenciais OAuth não encontrado: {GOOGLE_OAUTH_CREDENTIALS_FILE}. "
                    "No local, coloque credentials.json na raiz. "
                    "No deploy, configure GOOGLE_OAUTH_CREDENTIALS_JSON e "
                    "GOOGLE_OAUTH_TOKEN_JSON nos secrets do Streamlit."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_OAUTH_CREDENTIALS_FILE,
                GOOGLE_DRIVE_SCOPES,
            )

        creds = flow.run_local_server(
            port=0,
            prompt="consent",
        )

        save_token_json_to_file(creds.to_json())

    service = build(
        "drive",
        "v3",
        credentials=creds,
    )

    return service


def upload_dataframe_to_drive(df: pd.DataFrame, file_name: str) -> str:
    """
    Função antiga mantida por compatibilidade.

    O fluxo principal atual usa:
    drive_database.alimentar_banco_xlsx_drive()
    """
    if df is None or df.empty:
        raise ValueError("DataFrame vazio. Não há dados para enviar.")

    service = get_google_drive_service()

    from googleapiclient.http import MediaIoBaseUpload

    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    file_stream = io.BytesIO(csv_bytes)

    file_metadata = {
        "name": file_name,
    }

    media = MediaIoBaseUpload(
        file_stream,
        mimetype="text/csv",
        resumable=False,
    )

    uploaded_file = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id,name",
            supportsAllDrives=True,
        )
        .execute()
    )

    return uploaded_file["name"]