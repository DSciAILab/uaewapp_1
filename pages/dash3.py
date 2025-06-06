# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
from streamlit_autorefresh import st_autorefresh 

# --- Constantes (sem alterações) ---
MAIN_SHEET_NAME = "UAEW_App" 
CONFIG_TAB_NAME = "Config"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
ATTENDANCE_TAB_NAME = "Attendance"
ATTENDANCE_ATHLETE_ID_COL = "Athlete ID"
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"

FC_EVENT_COL = "Event"
FC_FIGHTER_COL = "Fighter"
FC_ATHLETE_ID_COL = "AthleteID"
FC_CORNER_COL = "Corner"
FC_ORDER_COL = "FightOrder"
FC_PICTURE_COL = "Picture"
FC_DIVISION_COL = "Division"

STATUS_INFO = {
    "Done": {"class": "status-done", "text": "Done"},
    "Requested": {"class": "status-requested", "text": "Requested"},
    "---": {"class": "status-neutral", "text": "---"},
    "Pendente": {"class": "status-pending", "text": "Pendente"},
    "Não Registrado": {"class": "status-pending", "text": "Pendente"},
    "Não Solicitado": {"class": "status-neutral", "text": "---"},
}
DEFAULT_STATUS_CLASS = "status-pending"

# --- Funções de Conexão e Carregamento (sem alterações) ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets: st.error("CRÍTICO: `gcp_service_account` não nos segredos.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e: st.error(f"CRÍTICO: Erro gspread client: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    if not gspread_client: st.error("CRÍTICO: Cliente gspread não inicializado.", icon="🚨"); st.stop()
    try: return gspread_client.open(sheet_name).worksheet(tab_name)
    except Exception as e: st.error(f"CRÍTICO: Erro ao conectar {sheet_name}/{tab_name}: {e}", icon="🚨"); st.stop()

@st.cache_data
def load_fightcard_data(): 
    try:
        df = pd.read_csv(FIGHTCARD_SHEET_URL)
        df.columns = df.columns.str.strip()
        df[FC_ORDER_COL] = pd.to_numeric(df[FC_ORDER_COL], errors="coerce")
        df[FC_CORNER_COL] = df[FC_CORNER_COL].astype(str).str.strip().str.lower()
        df[FC_FIGHTER_COL] = df[FC_FIGHTER_COL].astype(str).str.strip() 
        df[FC_PICTURE_COL] = df[FC_PICTURE_COL].astype(str).str.strip().fillna("")
        if FC_ATHLETE_ID_COL in df.columns:
            df[FC_ATHLETE_ID_COL] = df[FC_ATHLETE_ID_COL].astype(str).str.strip().fillna("")
        else:
            st.error(f"CRÍTICO: Coluna '{FC_ATHLETE_ID_COL}' não encontrada no Fightcard.")
            df[FC_ATHLETE_ID_COL] = ""
        return df.dropna(subset=[FC_FIGHTER_COL, FC_ORDER_COL, FC_ATHLETE_ID_COL])
    except Exception as e: st.error(f"Erro ao carregar Fightcard: {e}"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records()) 
        if df_att.empty: return pd.DataFrame()
        cols_to_process = [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL]
        for col in cols_to_process:
            if col in df_att.columns: df_att[col] = df_att[col].astype(str).str.strip()
            else: df_att[col] = None 
        return df_att 
    except Exception as e: st.error(f"Erro ao carregar Attendance: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600)
def get_task_list(sheet_name=MAIN_SHEET_NAME, config_tab=CONFIG_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab)
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1: return [] 
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        return df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
    except Exception as e: st.error(f"Erro ao carregar TaskList da Config: {e}"); return []

def get_task_status(athlete_id, task_name, df_attendance):
    if df_attendance.empty or pd.isna(athlete_id) or str(athlete_id).strip()=="" or not task_name:
        return STATUS_INFO.get("Pendente", {"class": DEFAULT_STATUS_CLASS, "text": "Pendente"})
    relevant_records = df_attendance[
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).str.strip() == str(athlete_id).strip()) &
        (df_attendance[ATTENDANCE_TASK_COL].astype(str).str.strip() == str(task_name).strip())]
    if relevant_records.empty: return STATUS_INFO.get("Pendente", {"class": DEFAULT_STATUS_CLASS, "text": "Pendente"})
    latest_status_str = relevant_records.iloc[-1][ATTENDANCE_STATUS_COL]
    if ATTENDANCE_TIMESTAMP_COL in relevant_records.columns:
        try:
            rel_sorted = relevant_records.copy()
            rel_sorted["Timestamp_dt"]=pd.to_datetime(rel_sorted[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce')
            if rel_sorted["Timestamp_dt"].notna().any():
                latest_status_str = rel_sorted.sort_values(by="Timestamp_dt", ascending=False, na_position='last').iloc[0][ATTENDANCE_STATUS_COL]
        except: pass
    return STATUS_INFO.get(str(latest_status_str).strip(), {"class": DEFAULT_STATUS_CLASS, "text": latest_status_str})

def generate_mirrored_html_dashboard(df_processed, task_list):
    header_html = "<thead><tr>"
    header_html += f"<th class='blue-corner-header' colspan='{len(task_list) + 2}'>CANTO AZUL</th>"
    header_html += "<th class='center-col-header' rowspan=2>Luta #</th>"
    header_html += "<th class='center-col-header' rowspan=2>Divisão</th>"
    header_html += f"<th class='red-corner-header' colspan='{len(task_list) + 2}'>CANTO VERMELHO</th>"
    header_html += "</tr><tr>"
    for task in reversed(task_list): header_html += f"<th>{task}</th>"
    header_html += "<th>Lutador</th><th>Foto</th>"
    header_html += "<th>Foto</th><th>Lutador</th>"
    for task in task_list: header_html += f"<th>{task}</th>"
    header_html += "</tr></thead>"
    body_html = "<tbody>"
    for _, row in df_processed.iterrows():
        body_html += "<tr>"
        for task in reversed(task_list):
            status = row.get(f'{task} (Azul)', get_task_status(None, task, pd.DataFrame()))
            body_html += f"<td class='status-cell {status['class']}' title='{status['text']}'></td>"
        body_html += f"<td class='fighter-name fighter-name-blue'>{row.get('Lutador Azul', 'N/A')}</td>"
        body_html += f"<td><img class='fighter-img' src='{row.get('Foto Azul', 'https://via.placeholder.com/50?text=N/A')}'/></td>"
        body_html += f"<td class='fight-number-cell'>{row.get('Luta #', '')}</td>"
        body_html += f"<td class='division-cell'>{row.get('Divisão', '')}</td>"
        body_html += f"<td><img class='fighter-img' src='{row.get('Foto Vermelho', 'https://via.placeholder.com/50?text=N/A')}'/></td>"
        body_html += f"<td class='fighter-name fighter-name-red'>{row.get('Lutador Vermelho', 'N/A')}</td>"
        for task in task_list:
            status = row.get(f'{task} (Vermelho)', get_task_status(None, task, pd.DataFrame()))
            body_html += f"<td class='status-cell {status['class']}' title='{status['text']}'></td>"
        body_html += "</tr>"
    body_html += "</tbody>"
    return f"<div class='dashboard-container'><table class='dashboard-table'>{header_html}{body_html}</table></div>"

# --- Início da Página Streamlit ---
st.set_page_config(layout="wide", page_title="Dashboard de Lutas")

st.markdown("""<style> ... </style>""", unsafe_allow_html=True) # CSS Omitido por brevidade, permanece o mesmo

# --- Título Principal e Auto-Refresh ---
st.markdown("<h1 style='text-align: center;'>DASHBOARD DE ATLETAS E TAREFAS</h1>", unsafe_allow_html=True)
st_autorefresh(interval=60000, key="dash_auto_refresh_v5")

# --- Carregamento de Dados ---
df_fc, df_att, all_tsks = None, None, None
with st.spinner("Carregando dados..."):
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    all_tsks = get_task_list()

# --- ATUALIZAÇÃO: Controles movidos para a Sidebar ---
st.sidebar.title("Controles do Dashboard")

if st.sidebar.button("🔄 Atualizar Agora", use_container_width=True):
    st.cache_data.clear() # Limpa o cache de todas as funções @st.cache_data
    st.toast("Dados atualizados!", icon="🎉")
    st.rerun()

# --- Lógica Principal ---
if df_fc is None or df_fc.empty or not all_tsks:
    st.warning("Não foi possível carregar os dados do Fightcard ou a lista de tarefas. Verifique as planilhas.")
    st.stop() # Interrompe a execução se os dados essenciais não estiverem disponíveis

# Cria a lista de eventos disponíveis a partir dos dados carregados
avail_evs = sorted(df_fc[FC_EVENT_COL].dropna().unique().tolist(), reverse=True)
if not avail_evs:
    st.warning("Nenhum evento encontrado no Fightcard.")
    st.stop()

# ATUALIZAÇÃO: Selectbox do evento agora está na sidebar
sel_ev_opt = st.sidebar.selectbox(
    "Selecione o Evento:",
    options=["Todos os Eventos"] + avail_evs,
    key="event_selector"
)
st.sidebar.markdown("---") # Divisor na sidebar

# --- Filtragem e Processamento dos Dados ---
df_fc_disp = df_fc.copy()
if sel_ev_opt != "Todos os Eventos":
    df_fc_disp = df_fc[df_fc[FC_EVENT_COL] == sel_ev_opt]

if df_fc_disp.empty:
    st.info(f"Nenhuma luta encontrada para o evento '{sel_ev_opt}'.")
    st.stop()

# O resto do processamento dos dados permanece o mesmo
dash_data_list = []
for order, group in df_fc_disp.sort_values(by=[FC_EVENT_COL, FC_ORDER_COL]).groupby([FC_EVENT_COL, FC_ORDER_COL]):
    f_ord = order[1]
    bl_s = group[group[FC_CORNER_COL] == "blue"].squeeze(axis=0)
    rd_s = group[group[FC_CORNER_COL] == "red"].squeeze(axis=0)
    
    row_d = {"Luta #": int(f_ord) if pd.notna(f_ord) else ""}
    
    for prefix, series in [("Azul", bl_s), ("Vermelho", rd_s)]:
        if isinstance(series, pd.Series) and not series.empty:
            name, id, pic = series.get(FC_FIGHTER_COL, "N/A"), series.get(FC_ATHLETE_ID_COL, ""), series.get(FC_PICTURE_COL, "")
            row_d[f"Foto {prefix}"] = pic if isinstance(pic, str) and pic.startswith("http") else ""
            row_d[f"Lutador {prefix}"] = f"{id} - {name}" if name != "N/A" else "N/A"
            for task in all_tsks:
                row_d[f"{task} ({prefix})"] = get_task_status(id, task, df_att)
        else:
            row_d[f"Foto {prefix}"], row_d[f"Lutador {prefix}"] = "", "N/A"
            for task in all_tsks:
                row_d[f"{task} ({prefix})"] = get_task_status(None, task, df_att)

    row_d["Divisão"] = bl_s.get(FC_DIVISION_COL, rd_s.get(FC_DIVISION_COL, "N/A")) if isinstance(bl_s, pd.Series) else (rd_s.get(FC_DIVISION_COL, "N/A") if isinstance(rd_s, pd.Series) else "N/A")
    dash_data_list.append(row_d)

# --- Exibição do Dashboard ---
if dash_data_list:
    df_dash_processed = pd.DataFrame(dash_data_list)
    
    st.subheader(f"Status das Lutas: {sel_ev_opt}")
    
    html_table = generate_mirrored_html_dashboard(df_dash_processed, all_tsks)
    st.markdown(html_table, unsafe_allow_html=True)
    
else:
    st.info(f"Nenhuma luta processada para '{sel_ev_opt}'.")
    
st.markdown("---")
st.markdown(f"*Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*", help="A página atualiza automaticamente a cada 60 segundos.")
