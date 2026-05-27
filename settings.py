from __future__ import annotations

import io
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv


load_dotenv()


APP_TITLE = "Sistema de Submissão de Dados em Saúde Alimentar"
APP_SUBTITLE = "Aplicação de upload, tratamento e envio de dados para o Google Drive"

GOOGLE_DRIVE_ENABLED = os.getenv("GOOGLE_DRIVE_ENABLED", "false").lower() == "true"

# OAuth local
GOOGLE_OAUTH_CREDENTIALS_FILE = os.getenv(
    "GOOGLE_OAUTH_CREDENTIALS_FILE",
    "credentials.json",
)

GOOGLE_OAUTH_TOKEN_FILE = os.getenv(
    "GOOGLE_OAUTH_TOKEN_FILE",
    "token.json",
)

# Escopo completo do Drive para localizar pastas, criar XLSX e atualizar arquivos existentes.
GOOGLE_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
]


def load_css(css_file: str) -> None:
    if not os.path.exists(css_file):
        return

    with open(css_file, "r", encoding="utf-8") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True,
        )


@st.cache_resource(show_spinner=False)
def get_google_drive_service():
    """
    Cria o serviço do Google Drive usando OAuth de usuário.

    Fluxo:
    - Usa credentials.json baixado do Google Cloud.
    - Na primeira execução, abre o navegador para login/autorização.
    - Salva token.json.
    - Nas próximas execuções, reutiliza token.json.
    """
    if not GOOGLE_DRIVE_ENABLED:
        raise RuntimeError(
            "Google Drive desabilitado. Configure GOOGLE_DRIVE_ENABLED=true no .env"
        )

    if not os.path.exists(GOOGLE_OAUTH_CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"Arquivo de credenciais OAuth não encontrado: {GOOGLE_OAUTH_CREDENTIALS_FILE}. "
            "Baixe o JSON do cliente OAuth e renomeie para credentials.json."
        )

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None

    if os.path.exists(GOOGLE_OAUTH_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            GOOGLE_OAUTH_TOKEN_FILE,
            GOOGLE_DRIVE_SCOPES,
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_OAUTH_CREDENTIALS_FILE,
                GOOGLE_DRIVE_SCOPES,
            )

            creds = flow.run_local_server(
                port=0,
                prompt="consent",
            )

        with open(GOOGLE_OAUTH_TOKEN_FILE, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    service = build(
        "drive",
        "v3",
        credentials=creds,
    )

    return service


def upload_dataframe_to_drive(df: pd.DataFrame, file_name: str) -> str:
    """
    Função antiga mantida apenas por compatibilidade.

    O fluxo principal atual do sistema deve usar:
    drive_database.alimentar_banco_xlsx_drive()

    Esta função envia um novo CSV avulso para o Drive e não é usada
    no fluxo atual de banco XLSX por UBS.
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