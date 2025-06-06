# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
from streamlit_autorefresh import st_autorefresh 

# --- Constantes ---
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

# ATUALIZAÇÃO: Mapeamento de status para classes CSS e texto para tooltips
STATUS_INFO = {
    "Done": {"class": "status-done", "text": "Done"},
    "Requested": {"class": "status-requested", "text": "Requested"},
    "---": {"class": "status-neutral", "text": "---"},
    "Pendente": {"class": "status-pending", "text": "Pendente"},
    "Não Registrado": {"class": "status-pending", "text": "Pendente"},
    "Não Solicitado": {"class": "status-neutral", "text": "---"},
}
DEFAULT_STATUS_CLASS = "status-pending"

# --- Funções de Conexão e Carregamento de Dados (sem alterações) ---
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
        df = pd.read_csv(FIGHTCARD_SHEET_URL);
        if df.empty: return pd.DataFrame()
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
        df_att = pd.DataFrame(worksheet.get_all_records()); 
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
        data = worksheet.get_all_values();
        if not data or len(data) < 1: return [] 
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        return df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
    except Exception as e: st.error(f"Erro ao carregar TaskList da Config: {e}"); return []

def get_task_status(athlete_id, task_name, df_attendance):
    """Retorna a classe CSS e o texto do status para um atleta/tarefa."""
    if df_attendance.empty or pd.isna(athlete_id) or str(athlete_id).strip()=="" or not task_name:
        return STATUS_INFO.get("Pendente", {"class": DEFAULT_STATUS_CLASS, "text": "Pendente"})

    relevant_records = df_attendance[
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).str.strip() == str(athlete_id).strip()) &
        (df_attendance[ATTENDANCE_TASK_COL].astype(str).str.strip() == str(task_name).strip())
    ]
    if relevant_records.empty:
        return STATUS_INFO.get("Pendente", {"class": DEFAULT_STATUS_CLASS, "text": "Pendente"})
    
    latest_status_str = relevant_records.iloc[-1][ATTENDANCE_STATUS_COL]
    if ATTENDANCE_TIMESTAMP_COL in relevant_records.columns:
        try:
            rel_sorted = relevant_records.copy()
            rel_sorted["Timestamp_dt"]=pd.to_datetime(rel_sorted[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce')
            if rel_sorted["Timestamp_dt"].notna().any():
                latest_status_str = rel_sorted.sort_values(by="Timestamp_dt", ascending=False, na_position='last').iloc[0][ATTENDANCE_STATUS_COL]
        except: pass # Mantém o último status se a ordenação falhar
        
    return STATUS_INFO.get(str(latest_status_str).strip(), {"class": DEFAULT_STATUS_CLASS, "text": latest_status_str})

# --- NOVA FUNÇÃO PARA GERAR A TABELA HTML ---
def generate_html_dashboard(df_processed, task_list):
    """Gera uma tabela HTML customizada para o dashboard."""
    
    # Cabeçalho da tabela com agrupamentos
    header_html = "<thead><tr>"
    header_html += "<th rowspan=2>Luta #</th>"
    header_html += f"<th colspan='{len(task_list) + 2}' class='blue-corner-header'>Canto Azul</th>"
    header_html += "<th rowspan=2>Divisão</th>"
    header_html += f"<th colspan='{len(task_list) + 2}' class='red-corner-header'>Canto Vermelho</th>"
    header_html += "</tr><tr>"
    # Segunda linha do cabeçalho
    for _ in range(2): # Para Canto Azul e Vermelho
        header_html += "<th>Foto</th><th>Lutador</th>"
        for task in task_list:
            header_html += f"<th>{task}</th>"
        if _ == 0: # Adiciona a coluna de Divisão entre os cantos
            header_html += "<th></th>" # Placeholder para a coluna Divisão
    header_html += "</tr></thead>"
    
    # Corpo da tabela
    body_html = "<tbody>"
    for _, row in df_processed.iterrows():
        body_html += "<tr>"
        # Coluna Luta #
        body_html += f"<td>{row.get('Luta #', '')}</td>"
        
        # Colunas do Canto Azul
        body_html += f"<td><img class='fighter-img' src='{row.get('Foto Azul', '')}'/></td>"
        body_html += f"<td class='fighter-name'>{row.get('Lutador Azul', 'N/A')}</td>"
        for task in task_list:
            status = row[f'{task} (Azul)']
            body_html += f"<td class='status-cell {status['class']}' title='{status['text']}'></td>"

        # Coluna Divisão
        body_html += f"<td class='division-cell'>{row.get('Divisão', '')}</td>"
        
        # Colunas do Canto Vermelho
        body_html += f"<td><img class='fighter-img' src='{row.get('Foto Vermelho', '')}'/></td>"
        body_html += f"<td class='fighter-name'>{row.get('Lutador Vermelho', 'N/A')}</td>"
        for task in task_list:
            status = row[f'{task} (Vermelho)']
            body_html += f"<td class='status-cell {status['class']}' title='{status['text']}'></td>"
            
        body_html += "</tr>"
    body_html += "</tbody>"
    
    return f"<div class='dashboard-container'><table class='dashboard-table'>{header_html}{body_html}</table></div>"


# --- Início da Página Streamlit ---
st.set_page_config(layout="wide", page_title="Dashboard de Lutas")

# Injeção do CSS para a nova tabela
st.markdown("""
<style>
    .dashboard-container {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        padding: 10px;
    }
    .dashboard-table {
        width: 100%;
        border-collapse: collapse;
        background-color: #2a2a2e;
        color: #e1e1e1;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
        border-radius: 8px;
        overflow: hidden;
    }
    .dashboard-table th, .dashboard-table td {
        border: 1px solid #444;
        padding: 8px 10px;
        text-align: center;
        vertical-align: middle;
    }
    .dashboard-table thead th {
        background-color: #1c1c1f;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .blue-corner-header { background-color: #0d2e4e !important; }
    .red-corner-header { background-color: #5a1d1d !important; }
    .fighter-img {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        object-fit: cover;
        border: 2px solid #555;
    }
    .fighter-name {
        font-weight: 600;
        font-size: 1rem;
        text-align: left !important;
        min-width: 200px;
    }
    .division-cell {
        font-weight: bold;
        background-color: #333;
    }
    .status-cell {
        width: 30px;
        height: 30px;
        min-width: 30px;
        cursor: help; /* Indica que há um tooltip */
    }
    .status-done { background-color: #28a745; }
    .status-requested { background-color: #ffc107; }
    .status-pending { background-color: #dc3545; }
    .status-neutral { background-color: #6c757d; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>DASHBOARD DE ATLETAS E TAREFAS</h1>", unsafe_allow_html=True)
st_autorefresh(interval=60000, key="dash_auto_refresh_v3")

if st.button("🔄 Atualizar Agora", use_container_width=True):
    st.cache_data.clear()
    st.toast("Dados atualizados!", icon="🎉"); st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

df_fc, df_att, all_tsks = None, None, None
with st.spinner("Carregando dados..."):
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    all_tsks = get_task_list()

if df_fc is None or df_fc.empty or not all_tsks:
    st.warning("Não foi possível carregar os dados do Fightcard ou a lista de tarefas. Verifique as planilhas.")
else:
    avail_evs = sorted(df_fc[FC_EVENT_COL].dropna().unique().tolist(), reverse=True)
    if not avail_evs: st.warning("Nenhum evento no Fightcard."); st.stop()
    
    sel_ev_opt = st.selectbox("Selecione o Evento:", options=["Todos os Eventos"] + avail_evs)
    
    df_fc_disp = df_fc.copy()
    if sel_ev_opt != "Todos os Eventos":
        df_fc_disp = df_fc[df_fc[FC_EVENT_COL] == sel_ev_opt]

    if df_fc_disp.empty: st.info(f"Nenhuma luta para '{sel_ev_opt}'."); st.stop()

    # Processamento dos dados para a estrutura final
    dash_data_list = []
    for order, group in df_fc_disp.sort_values(by=[FC_EVENT_COL, FC_ORDER_COL]).groupby([FC_EVENT_COL, FC_ORDER_COL]):
        ev, f_ord = order
        bl_s = group[group[FC_CORNER_COL] == "blue"].squeeze(axis=0)
        rd_s = group[group[FC_CORNER_COL] == "red"].squeeze(axis=0)
        
        row_d = {"Luta #": int(f_ord) if pd.notna(f_ord) else ""}
        
        # Processa ambos os cantos
        for corner_prefix, series_data in [("Azul", bl_s), ("Vermelho", rd_s)]:
            if isinstance(series_data, pd.Series) and not series_data.empty:
                fighter_name = str(series_data.get(FC_FIGHTER_COL, "N/A")).strip()
                athlete_id = str(series_data.get(FC_ATHLETE_ID_COL, "")).strip()
                pic_url = series_data.get(FC_PICTURE_COL, "")
                
                row_d[f"Foto {corner_prefix}"] = pic_url if isinstance(pic_url, str) and pic_url.startswith("http") else ""
                row_d[f"Lutador {corner_prefix}"] = f"{athlete_id} - {fighter_name}" if fighter_name != "N/A" else "N/A"
                
                for task in all_tsks:
                    row_d[f"{task} ({corner_prefix})"] = get_task_status(athlete_id, task, df_att)
            else: # Caso o canto esteja vazio
                row_d[f"Foto {corner_prefix}"] = ""
                row_d[f"Lutador {corner_prefix}"] = "N/A"
                for task in all_tsks:
                    row_d[f"{task} ({corner_prefix})"] = get_task_status(None, task, df_att)

        row_d["Divisão"] = bl_s.get(FC_DIVISION_COL, rd_s.get(FC_DIVISION_COL, "N/A")) if isinstance(bl_s, pd.Series) else (rd_s.get(FC_DIVISION_COL, "N/A") if isinstance(rd_s, pd.Series) else "N/A")
        dash_data_list.append(row_d)

    if dash_data_list:
        df_dash_processed = pd.DataFrame(dash_data_list)
        
        st.subheader(f"Detalhes das Lutas e Tarefas: {sel_ev_opt}")
        
        # Gera e exibe a nova tabela HTML
        html_table = generate_html_dashboard(df_dash_processed, all_tsks)
        st.markdown(html_table, unsafe_allow_html=True)
        
    else:
        st.info(f"Nenhuma luta processada para '{sel_ev_opt}'.")

    # (A seção de estatísticas pode ser mantida ou adaptada conforme necessário)
    st.markdown("---")
    st.markdown(f"*Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
