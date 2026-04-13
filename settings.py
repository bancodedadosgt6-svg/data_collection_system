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
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")


def load_css(css_file: str) -> None:
    if not os.path.exists(css_file):
        return

    with open(css_file, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def get_google_drive_service():
    if not GOOGLE_DRIVE_ENABLED:
        raise RuntimeError("Google Drive desabilitado. Configure GOOGLE_DRIVE_ENABLED=true no .env")

    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/drive.file"]

    credentials = Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=scopes,
    )

    service = build("drive", "v3", credentials=credentials)
    return service


def upload_dataframe_to_drive(df: pd.DataFrame, file_name: str) -> str:
    if df is None or df.empty:
        raise ValueError("DataFrame vazio. Não há dados para enviar.")

    if not GOOGLE_DRIVE_FOLDER_ID:
        raise ValueError("GOOGLE_DRIVE_FOLDER_ID não foi configurado.")

    service = get_google_drive_service()

    from googleapiclient.http import MediaIoBaseUpload

    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    file_stream = io.BytesIO(csv_bytes)

    file_metadata = {
        "name": file_name,
        "parents": [GOOGLE_DRIVE_FOLDER_ID],
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