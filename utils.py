#utils.py

# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App" 
USERS_TAB_NAME = "Users"
CONFIG_TAB_NAME = "Config"

# --- 2. Google Sheets Connection ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except KeyError as e: 
        st.error(f"Erro config: Chave GCP ausente. Detalhes: {e}", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro API Google: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada em '{sheet_name}'.", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨"); st.stop()

@st.cache_data(ttl=30)  # Cache curto para multi-usuário
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, users_tab_name)
        return safe_get_all_records(worksheet)
    except Exception as e:
        st.error(f"Erro ao carregar usuários '{users_tab_name}': {e}", icon="🚨"); return []

def get_valid_user_info(user_input: str, sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    """
    Valida as credenciais do usuário contra a planilha de usuários.
    Retorna um dicionário com as informações do usuário se for válido, senão None.
    """
    if not user_input: return None
    all_users = load_users_data(sheet_name, users_tab_name)
    if not all_users: return None
    proc_input = user_input.strip().upper()
    val_id_input = proc_input[2:] if proc_input.startswith("PS") and len(proc_input) > 2 and proc_input[2:].isdigit() else proc_input
    for record in all_users:
        # Tenta pegar chaves de forma case-insensitive
        ps_sheet = str(record.get("PS", record.get("ps", ""))).strip()
        name_sheet = str(record.get("USER", record.get("user", ""))).strip().upper()
        
        # Logica de comparação robusta
        if ps_sheet == val_id_input or ("PS" + ps_sheet) == proc_input or name_sheet == proc_input or ps_sheet == proc_input: 
            return record
    return None

@st.cache_data(ttl=60)  # Cache curto para multi-usuário
def load_config_data(sheet_name: str = MAIN_SHEET_NAME, config_tab_name: str = CONFIG_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab_name)
        data = worksheet.get_all_values()
        if not data or len(data) < 1: 
            st.error(f"Aba '{config_tab_name}' vazia/sem cabeçalho.", icon="🚨")
            return [],[]
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().unique().tolist() if "TaskList" in df_conf.columns else []
        statuses = df_conf["TaskStatus"].dropna().unique().tolist() if "TaskStatus" in df_conf.columns else []
        if not tasks: 
            st.warning(f"'TaskList' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        if not statuses: 
            st.warning(f"'TaskStatus' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        return tasks, statuses
    except Exception as e: 
        st.error(f"Erro ao carregar config '{config_tab_name}': {e}", icon="🚨")
        return [], []

def safe_get_all_records(worksheet):
    """
    Robust replacement for gspread's get_all_records().
    Handles:
    - Empty sheets
    - Duplicate headers (suffixes with _1, _2, etc.)
    - Empty headers (names them 'col_X')
    Returns a list of dictionaries.
    """
    try:
        all_values = worksheet.get_all_values()
        if not all_values or len(all_values) < 2:
            return []
            
        headers = all_values[0]
        # Make headers unique
        unique_headers = []
        seen = {}
        for i, h in enumerate(headers):
            clean_h = str(h).strip()
            if not clean_h:
                clean_h = f"col_{i+1}"
            
            if clean_h in seen:
                seen[clean_h] += 1
                unique_headers.append(f"{clean_h}_{seen[clean_h]}")
            else:
                seen[clean_h] = 0
                unique_headers.append(clean_h)
        
        records = []
        for row in all_values[1:]:
            record = {}
            for i, header in enumerate(unique_headers):
                # Handle rows shorter than headers
                val = row[i] if i < len(row) else ""
                record[header] = val
            records.append(record)
            
        return records
    except Exception as e:
        # Fallback empty list on any error to prevent app crash
        print(f"Error in safe_get_all_records: {e}")
        return []