# --- 0. Import Libraries ---
import json
import time
from typing import List, Tuple, Optional, Dict

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
USERS_TAB_NAME = "Users"
CONFIG_TAB_NAME = "Config"

# --- Helpers ---
def _parse_service_account_secret(obj) -> Dict:
    """
    Aceita st.secrets['gcp_service_account'] como dict ou JSON string.
    Retorna sempre um dict (lança exceção se inválido).
    """
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        return json.loads(obj)  # pode lançar ValueError
    raise ValueError("Formato de credencial inesperado (esperado dict ou JSON string).")


def _retry_google(callable_fn, *args, retries: int = 3, delay_base: float = 0.7, **kwargs):
    """
    Retry simples com backoff exponencial para chamadas do gspread.
    Captura exceções genéricas e re-tenta algumas vezes antes de propagar.
    """
    last_err = None
    for i in range(retries):
        try:
            return callable_fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if i < retries - 1:
                time.sleep(delay_base * (2 ** i))
            else:
                break
    raise last_err  # propaga após esgotar tentativas


# --- 2. Google Sheets Connection ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    """
    Cria e cacheia o cliente do gspread usando credenciais do Streamlit Secrets.
    """
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas no st.secrets.", icon="🚨")
            st.stop()

        raw = st.secrets["gcp_service_account"]
        sa_info = _parse_service_account_secret(raw)

        creds = Credentials.from_service_account_info(sa_info, scopes=scope)
        return gspread.authorize(creds)

    except json.JSONDecodeError as e:
        st.error(f"Erro nas credenciais GCP (JSON inválido): {e}", icon="🚨")
        st.stop()
    except KeyError as e:
        st.error(f"Erro config: chave ausente nas credenciais GCP. Detalhes: {e}", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao inicializar cliente Google Sheets: {e}", icon="🚨")
        st.stop()


def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    """
    Abre a planilha e retorna o worksheet (aba) solicitado.
    """
    try:
        spreadsheet = _retry_google(gspread_client.open, sheet_name)
        return _retry_google(spreadsheet.worksheet, tab_name)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨")
        st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada em '{sheet_name}'.", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨")
        st.stop()


@st.cache_data(ttl=300)
def load_users_data(
    sheet_name: str = MAIN_SHEET_NAME,
    users_tab_name: str = USERS_TAB_NAME
) -> List[Dict]:
    """
    Carrega lista de usuários da aba 'Users' como uma lista de dicts.
    """
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, users_tab_name)
        records = _retry_google(worksheet.get_all_records)
        return records or []
    except Exception as e:
        st.error(f"Erro ao carregar usuários da aba '{users_tab_name}': {e}", icon="🚨")
        return []


def get_valid_user_info(
    user_input: str,
    sheet_name: str = MAIN_SHEET_NAME,
    users_tab_name: str = USERS_TAB_NAME
) -> Optional[Dict]:
    """
    Valida as credenciais do usuário contra a planilha de usuários.
    Retorna um dicionário com as informações do usuário se for válido, senão None.

    Regras:
    - Aceita "PS123" ou "123"
    - Compara também por USER (nome), case-insensitive (upper())
    """
    if not user_input:
        return None

    all_users = load_users_data(sheet_name, users_tab_name)
    if not all_users:
        return None

    proc_input = user_input.strip().upper()

    # Normaliza entradas do tipo "PS123" -> "123"
    if proc_input.startswith("PS") and len(proc_input) > 2 and proc_input[2:].isdigit():
        val_id_input = proc_input[2:]
    else:
        val_id_input = proc_input

    for record in all_users:
        ps_sheet = str(record.get("PS", "")).strip()
        name_sheet = str(record.get("USER", "")).strip().upper()

        # match por PS sem prefixo, PS com prefixo, nome exato upper, ou match bruto
        if (
            ps_sheet == val_id_input
            or ("PS" + ps_sheet) == proc_input
            or name_sheet == proc_input
            or ps_sheet == proc_input
        ):
            return record

    return None


@st.cache_data(ttl=600)
def load_config_data(
    sheet_name: str = MAIN_SHEET_NAME,
    config_tab_name: str = CONFIG_TAB_NAME
) -> Tuple[List[str], List[str]]:
    """
    Carrega listas de configuração (TaskList, TaskStatus) da aba 'Config'.
    Retorna (tasks, statuses) como listas únicas preservando valores não nulos.
    """
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab_name)
        data = _retry_google(worksheet.get_all_values)

        if not data or len(data) < 1:
            st.error(f"Aba '{config_tab_name}' vazia/sem cabeçalho.", icon="🚨")
            return [], []

        df_conf = pd.DataFrame(data[1:], columns=data[0])

        tasks: List[str] = []
        statuses: List[str] = []

        if "TaskList" in df_conf.columns:
            tasks = (
                pd.Series(df_conf["TaskList"])
                .dropna()
                .astype(str)
                .str.strip()
                .replace("", pd.NA)
                .dropna()
                .unique()
                .tolist()
            )
            if not tasks:
                st.warning(f"Coluna 'TaskList' está vazia em '{config_tab_name}'.", icon="⚠️")
        else:
            st.warning(f"Coluna 'TaskList' não encontrada em '{config_tab_name}'.", icon="⚠️")

        if "TaskStatus" in df_conf.columns:
            statuses = (
                pd.Series(df_conf["TaskStatus"])
                .dropna()
                .astype(str)
                .str.strip()
                .replace("", pd.NA)
                .dropna()
                .unique()
                .tolist()
            )
            if not statuses:
                st.warning(f"Coluna 'TaskStatus' está vazia em '{config_tab_name}'.", icon="⚠️")
        else:
            st.warning(f"Coluna 'TaskStatus' não encontrada em '{config_tab_name}'.", icon="⚠️")

        return tasks, statuses

    except Exception as e:
        st.error(f"Erro ao carregar config da aba '{config_tab_name}': {e}", icon="🚨")
        return [], []
