# pages/DashboardNovo.py (ou como você nomeou o arquivo que está adaptando para mobile)

import streamlit as st
import pandas as pd
import gspread
# from google.oauth2.service_account import Credentials # Removido, usando gspread.service_account_from_dict
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- Constantes ---
MAIN_SHEET_NAME = "UAEW_App"
CONFIG_TAB_NAME = "Config"
ANNOUNCEMENTS_TAB_NAME = "Announcements" # Nova constante para a aba de avisos
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
FC_DIVISION_COL = "Division" # Mantida para carregamento, mas não usada na UI mobile

STATUS_TO_EMOJI = {
    "Done": "🟩", "Requested": "🟨", "---": "➖", "Não Solicitado": "➖", # Confirmado 🟨
    "Pendente": "🟥", "Não Registrado": "🟥"
}
DEFAULT_EMOJI = "🟥"
EMOJI_LEGEND = {
    "🟩": "Done", "🟨": "Requested", "➖": "---", "🟥": "Pendente" # Confirmado 🟨
}
CORNER_EMOJI_MAP = {"blue": "🔵", "red": "🔴", "n/a": ""}
HIGHLIGHT_COL_NAME = "_HIGHLIGHT_"

# Colunas esperadas na aba "Announcements" (ajuste conforme sua planilha)
ANNOUNCEMENT_MESSAGE_COL = "Mensagem"
ANNOUNCEMENT_TYPE_COL = "Tipo" # Opcional: Info, Alerta, Erro, Sucesso
ANNOUNCEMENT_ACTIVE_COL = "Ativo" # Opcional: SIM/NAO

# --- Funções de Conexão e Carregamento de Dados ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("CRÍTICO: `gcp_service_account` não nos segredos.", icon="🚨")
            st.stop()
        creds_info = st.secrets["gcp_service_account"]
        return gspread.service_account_from_dict(creds_info, scopes=scope)
    except Exception as e:
        st.error(f"CRÍTICO: Erro gspread client: {e}", icon="🚨")
        st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    if not gspread_client: st.error("CRÍTICO: Cliente gspread não inicializado.", icon="🚨"); st.stop()
    try: return gspread_client.open(sheet_name).worksheet(tab_name)
    except gspread.exceptions.APIError as e:
        st.error(f"CRÍTICO: Erro de API do Google ao conectar {sheet_name}/{tab_name}: {e}", icon="🚨")
        if hasattr(e, 'response') and hasattr(e.response, 'json'):
             st.error(f"Detalhes: {e.response.json()}")
        st.info("Verifique se a conta de serviço tem permissão para acessar esta planilha e se as APIs Google Sheets/Drive estão habilitadas.")
        st.stop()
    except Exception as e:
        st.error(f"CRÍTICO: Erro genérico ao conectar {sheet_name}/{tab_name}: {e}", icon="🚨")
        st.stop()

@st.cache_data(ttl=300) # Cache mais curto para anúncios, se desejar que atualizem mais rápido
def load_announcements_data(sheet_name=MAIN_SHEET_NAME, announcements_tab=ANNOUNCEMENTS_TAB_NAME):
    gspread_client = get_gspread_client()
    try:
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, announcements_tab)
        df_ann = pd.DataFrame(worksheet.get_all_records())
        if df_ann.empty:
            return pd.DataFrame()

        # Padroniza as colunas esperadas
        if ANNOUNCEMENT_MESSAGE_COL not in df_ann.columns:
            st.warning(f"Aba '{announcements_tab}' não contém a coluna obrigatória '{ANNOUNCEMENT_MESSAGE_COL}'.")
            return pd.DataFrame() # Retorna DF vazio se coluna obrigatória falta

        if ANNOUNCEMENT_TYPE_COL not in df_ann.columns:
            df_ann[ANNOUNCEMENT_TYPE_COL] = "Info" # Padrão para Info se não existir
        else:
            df_ann[ANNOUNCEMENT_TYPE_COL] = df_ann[ANNOUNCEMENT_TYPE_COL].astype(str).str.strip().fillna("Info")

        if ANNOUNCEMENT_ACTIVE_COL not in df_ann.columns:
            df_ann[ANNOUNCEMENT_ACTIVE_COL] = "SIM" # Padrão para Ativo se não existir
        else:
            df_ann[ANNOUNCEMENT_ACTIVE_COL] = df_ann[ANNOUNCEMENT_ACTIVE_COL].astype(str).str.strip().str.upper().fillna("NAO")

        # Filtrar apenas anúncios ativos
        df_ann_active = df_ann[df_ann[ANNOUNCEMENT_ACTIVE_COL] == "SIM"]
        return df_ann_active[[ANNOUNCEMENT_MESSAGE_COL, ANNOUNCEMENT_TYPE_COL]].reset_index(drop=True)

    except Exception as e:
        st.error(f"Erro ao carregar Avisos da aba '{announcements_tab}': {e}")
        return pd.DataFrame()


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
            st.error(f"CRÍTICO: Coluna '{FC_ATHLETE_ID_COL}' não encontrada no Fightcard. Verifique a planilha.")
            df[FC_ATHLETE_ID_COL] = ""
        if FC_DIVISION_COL not in df.columns: # Apenas para garantir que não dê erro se a coluna não existir no CSV
            df[FC_DIVISION_COL] = "N/A"
        else:
            df[FC_DIVISION_COL] = df[FC_DIVISION_COL].astype(str).str.strip().fillna("N/A")

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
            else: df_att[col] = pd.NA
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

def get_task_status_representation(athlete_id_to_check, task_name, df_attendance):
    if df_attendance.empty or pd.isna(athlete_id_to_check) or str(athlete_id_to_check).strip()=="" or not task_name:
        return STATUS_TO_EMOJI.get("Pendente",DEFAULT_EMOJI)
    if ATTENDANCE_ATHLETE_ID_COL not in df_attendance.columns or ATTENDANCE_TASK_COL not in df_attendance.columns or ATTENDANCE_STATUS_COL not in df_attendance.columns:
        return STATUS_TO_EMOJI.get("Pendente",DEFAULT_EMOJI)
    athlete_id_str=str(athlete_id_to_check).strip(); task_name_str=str(task_name).strip()
    relevant_records=df_attendance[
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).str.strip()==athlete_id_str) &
        (df_attendance[ATTENDANCE_TASK_COL].astype(str).str.strip()==task_name_str)
    ]
    if relevant_records.empty: return STATUS_TO_EMOJI.get("Pendente",DEFAULT_EMOJI)
    latest_status_str=relevant_records.iloc[-1][ATTENDANCE_STATUS_COL]
    if ATTENDANCE_TIMESTAMP_COL in relevant_records.columns and relevant_records[ATTENDANCE_TIMESTAMP_COL].notna().any():
        try:
            relevant_records_copy = relevant_records.copy()
            relevant_records_copy["Timestamp_dt"] = pd.to_datetime(relevant_records_copy[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce')
            valid_timestamps = relevant_records_copy.dropna(subset=["Timestamp_dt"])
            if not valid_timestamps.empty:
                latest_status_str = valid_timestamps.sort_values(by="Timestamp_dt", ascending=False).iloc[0][ATTENDANCE_STATUS_COL]
        except Exception: pass
    return STATUS_TO_EMOJI.get(str(latest_status_str).strip(),DEFAULT_EMOJI)

def extract_id_from_display_name(display_name_with_emoji):
    if not isinstance(display_name_with_emoji, str) or display_name_with_emoji == "N/A": return pd.NA
    parts = display_name_with_emoji.split(" ", 1)
    name_part = parts[1] if len(parts) > 1 else parts[0]
    id_name_parts = name_part.split(" - ", 1)
    if len(id_name_parts) > 0:
        potential_id = id_name_parts[0].strip()
        if potential_id and potential_id != "N/D": return potential_id
    return pd.NA

# --- Início da Página Streamlit ---
st.set_page_config(layout="wide")
st.markdown("<h1 style='text-align: center; font-size: 2em; margin-bottom: 5px;'>DASHBOARD DE ATLETAS</h1>",unsafe_allow_html=True)
refresh_count = st_autorefresh(interval=60000,limit=None,key="dash_auto_refresh_v7_mobile") # Nova key para autorefresh

# Controles: Botão de refresh, seletor de evento, busca
header_cols = st.columns([0.3, 0.4, 0.3])
with header_cols[0]:
    if st.button("🔄 Atualizar Dados",key="refresh_dash_manual_btn_mobile_v7",use_container_width=True): # Nova key
        st.cache_data.clear(); st.cache_resource.clear()
        if 'edited_athlete_df' in st.session_state: del st.session_state.edited_athlete_df
        if 'data_signature_for_highlights' in st.session_state: del st.session_state.data_signature_for_highlights
        st.toast("Dados atualizados!",icon="🎉");st.rerun()

# CSS (Sem opção de tamanho de fonte, apenas estilos da tabela e highlight)
HIGHLIGHT_COLOR = "#FFF3C4" # Amarelo claro para highlight
st.markdown(f"""
    <style>
        div[data-testid="stDataFrameResizable"] div[data-baseweb="table-cell"] > div {{
            margin: auto; white-space: normal !important; word-break: break-word !important;
        }}
        div[data-testid="stDataFrameResizable"] div[data-baseweb="table-cell"] {{
            text-align:center !important; vertical-align:middle !important; display:flex !important;
            align-items:center !important; justify-content:center !important;
            padding-top: 5px !important; padding-bottom: 5px !important;
        }}
        div[data-testid="stDataFrameResizable"] div[data-baseweb="table-header-cell"] {{
            font-weight:bold !important; text-transform:uppercase; text-align:center !important;
            white-space:normal !important; word-break:break-word !important; background-color: #f0f2f6;
        }}
        div[data-testid="stDataFrameResizable"] img {{
            max-height: 50px; object-fit: contain;
        }}
        div[data-testid="stDataFrameResizable"] tbody tr:has(td div[data-baseweb="checkbox"] input[type="checkbox"]:checked) {{
            background-color: {HIGHLIGHT_COLOR} !important;
        }}
    </style>
""", unsafe_allow_html=True)
# Removido o st.markdown("<hr>") daqui, será colocado após os avisos

# Carregamento de dados
df_fc_raw=None; df_att_raw=None; all_tsks_raw=None; df_announcements_raw=None; load_err=False; err_ph=st.empty()
with st.spinner("Carregando dados..."):
    try:
        df_fc_raw=load_fightcard_data()
        df_att_raw=load_attendance_data()
        all_tsks_raw=get_task_list()
        df_announcements_raw = load_announcements_data() # Carregar avisos

        if df_fc_raw.empty or not all_tsks_raw: # A ausência de anúncios não é um erro crítico
            load_err=True
    except Exception as e:
        err_ph.error(f"Erro crítico no carregamento inicial de dados: {e}")
        load_err=True
        st.stop()

if load_err:
    if df_fc_raw is not None and df_fc_raw.empty:err_ph.warning("Fightcard vazio.")
    if not all_tsks_raw:err_ph.error("Lista de Tarefas vazia.")
    st.stop()
elif df_fc_raw.empty:st.warning("Nenhum dado de Fightcard."); st.stop()
elif not all_tsks_raw:st.error("TaskList não carregada."); st.stop()
else:
    # Exibir Avisos ANTES do seletor de evento e da tabela
    if df_announcements_raw is not None and not df_announcements_raw.empty:
        st.markdown("---") # Linha separadora antes dos avisos
        st.subheader("📢 Avisos Importantes")
        for index, row in df_announcements_raw.iterrows():
            msg = row[ANNOUNCEMENT_MESSAGE_COL]
            msg_type = row[ANNOUNCEMENT_TYPE_COL].lower() # para case-insensitive match

            if msg_type == "alerta":
                st.warning(msg, icon="⚠️")
            elif msg_type == "erro":
                st.error(msg, icon="🚨")
            elif msg_type == "sucesso":
                st.success(msg, icon="✅")
            else: # Padrão para "info" ou qualquer outro tipo
                st.info(msg, icon="ℹ️")
        st.markdown("---") # Linha separadora após os avisos
    else:
        st.markdown("<hr style='margin-top:5px;margin-bottom:15px;'>",True) # Linha padrão se não houver avisos

    # Controles restantes (após avisos)
    avail_evs=sorted(df_fc_raw[FC_EVENT_COL].dropna().unique().tolist(),reverse=True)
    if not avail_evs:st.warning("Nenhum evento no Fightcard.");st.stop()
    ev_opts=["Todos os Eventos"]+avail_evs
    
    with header_cols[1]:
        sel_ev_opt=st.selectbox("Evento:",options=ev_opts,index=0,key="ev_sel_dn_mobile_v7", label_visibility="collapsed")
    with header_cols[2]:
        search_term = st.text_input("Buscar Lutador:", key="search_athlete_v7", placeholder="Nome ou ID...", label_visibility="collapsed")

    df_fc_filtered_by_event=df_fc_raw.copy()
    if sel_ev_opt!="Todos os Eventos":df_fc_filtered_by_event=df_fc_raw[df_fc_raw[FC_EVENT_COL]==sel_ev_opt].copy()
    
    num_lutas_evento_original = 0
    if not df_fc_filtered_by_event.empty:
        num_lutas_evento_original = df_fc_filtered_by_event.groupby([FC_EVENT_COL, FC_ORDER_COL], sort=False).ngroups

    if df_fc_filtered_by_event.empty and sel_ev_opt != "Todos os Eventos":
        st.info(f"Nenhuma luta para '{sel_ev_opt}'.");st.stop()
    elif df_fc_filtered_by_event.empty and sel_ev_opt == "Todos os Eventos":
         st.info(f"Nenhuma luta encontrada.");st.stop()

    dash_data_list=[]
    for (event, fight_order_original), group in df_fc_filtered_by_event.sort_values(by=[FC_EVENT_COL, FC_ORDER_COL]).groupby([FC_EVENT_COL, FC_ORDER_COL], sort=False):
        fighters_in_fight = []
        blue_fighter_series = group[group[FC_CORNER_COL] == "blue"].squeeze(axis=0)
        red_fighter_series = group[group[FC_CORNER_COL] == "red"].squeeze(axis=0)

        if isinstance(blue_fighter_series, pd.Series) and blue_fighter_series.get(FC_FIGHTER_COL, "N/A") != "N/A":
            fighters_in_fight.append(blue_fighter_series)
        if isinstance(red_fighter_series, pd.Series) and red_fighter_series.get(FC_FIGHTER_COL, "N/A") != "N/A":
            fighters_in_fight.append(red_fighter_series)
        
        if not fighters_in_fight: continue

        for fighter_data in fighters_in_fight:
            fighter_row = { "Evento": event }
            fighter_name_fc = str(fighter_data.get(FC_FIGHTER_COL, "N/A")).strip()
            athlete_id_fc = str(fighter_data.get(FC_ATHLETE_ID_COL, "")).strip()
            picture_url = fighter_data.get(FC_PICTURE_COL, "")
            corner_color = fighter_data.get(FC_CORNER_COL, "n/a").lower()

            fighter_row["Foto"] = picture_url if isinstance(picture_url, str) and picture_url.startswith("http") else None
            id_display = athlete_id_fc if athlete_id_fc else "N/D"
            name_display_text = f"{id_display} - {fighter_name_fc}" if fighter_name_fc != "N/A" else "N/A"
            corner_emoji = CORNER_EMOJI_MAP.get(corner_color, "")
            fighter_row["Lutador"] = f"{corner_emoji} {name_display_text}".strip()

            if fighter_name_fc != "N/A" and athlete_id_fc:
                for task in all_tsks_raw:
                    emoji_status = get_task_status_representation(athlete_id_fc, task, df_att_raw)
                    fighter_row[task] = emoji_status
            else:
                for task in all_tsks_raw:
                    fighter_row[task] = STATUS_TO_EMOJI.get("Pendente", DEFAULT_EMOJI)
            dash_data_list.append(fighter_row)

    if not dash_data_list:
        st.info(f"Nenhum lutador processado para '{sel_ev_opt}'.");st.stop()
    
    df_dashboard_processed = pd.DataFrame(dash_data_list)
    df_to_display_filtered_by_search = df_dashboard_processed.copy()
    if search_term:
        df_to_display_filtered_by_search = df_to_display_filtered_by_search[
            df_to_display_filtered_by_search["Lutador"].astype(str).str.contains(search_term, case=False, na=False)
        ]
    
    current_data_signature = f"{sel_ev_opt}_{search_term}"
    if 'data_signature_for_highlights' not in st.session_state or st.session_state.data_signature_for_highlights != current_data_signature:
        if 'edited_athlete_df' in st.session_state:
            del st.session_state.edited_athlete_df
        st.session_state.data_signature_for_highlights = current_data_signature

    df_to_display_filtered_by_search = df_to_display_filtered_by_search.reset_index(drop=True)

    if 'edited_athlete_df' in st.session_state and \
       len(st.session_state.edited_athlete_df) == len(df_to_display_filtered_by_search) and \
       list(st.session_state.edited_athlete_df.index) == list(df_to_display_filtered_by_search.index) and \
       HIGHLIGHT_COL_NAME in st.session_state.edited_athlete_df.columns:
        df_to_display_filtered_by_search[HIGHLIGHT_COL_NAME] = st.session_state.edited_athlete_df[HIGHLIGHT_COL_NAME]
    else:
        df_to_display_filtered_by_search[HIGHLIGHT_COL_NAME] = False


    if df_to_display_filtered_by_search.empty:
        if search_term:
            st.info(f"Nenhum lutador encontrado com o termo '{search_term}' no evento '{sel_ev_opt}'.")
        else:
            st.info(f"Nenhum lutador para exibir no evento '{sel_ev_opt}'.")
        st.stop()

    col_conf_edit = {
        HIGHLIGHT_COL_NAME: st.column_config.CheckboxColumn("HL", width="small", default=False),
        "Evento": st.column_config.TextColumn(width="small", disabled=True),
        "Foto": st.column_config.ImageColumn("Foto", width="small"), # Removido disabled=True
        "Lutador": st.column_config.TextColumn("Lutador (ID - Nome)", width="large", disabled=True),
    }
    col_ord_list = [HIGHLIGHT_COL_NAME, "Evento", "Foto", "Lutador"]
    for task_name_col in all_tsks_raw: col_ord_list.append(task_name_col)

    leg_parts=[f"{emo}: {dsc}"for emo,dsc in EMOJI_LEGEND.items()if emo.strip()!=""]
    help_txt_leg_disp=", ".join(leg_parts)

    for task_name_col in all_tsks_raw:
        col_conf_edit[task_name_col] = st.column_config.TextColumn(
            label=task_name_col, width="small", help=f"Status: {help_txt_leg_disp}", disabled=True
        )

    st.subheader(f"Detalhes dos Atletas: {sel_ev_opt}{f' (Busca: "{search_term}")' if search_term else ''}")
    st.markdown(f"**Legenda Status:** {help_txt_leg_disp}")
    
    num_rows_display = len(df_to_display_filtered_by_search)
    row_height_approx = 60
    header_height = 45
    table_height = min(max(300, (num_rows_display * row_height_approx) + header_height), 800)

    edited_df_output = st.data_editor(
        df_to_display_filtered_by_search,
        column_config=col_conf_edit, column_order=col_ord_list, hide_index=True,
        use_container_width=True, num_rows="fixed",
        disabled=False,
        height=int(table_height),
        key="athlete_editor_with_highlight" # Mantida a key para o editor
    )
    
    st.session_state.edited_athlete_df = edited_df_output.copy()

    st.markdown("---")
    st.subheader(f"Estatísticas: {sel_ev_opt}{f' (Busca: "{search_term}")' if search_term else ''}")
    
    df_stats_source = edited_df_output
    
    if not df_stats_source.empty:
        valid_athlete_ids_display = df_stats_source[df_stats_source["Lutador"] != "N/A"]["Lutador"].apply(
            extract_id_from_display_name
        ).dropna().unique()
        tot_ath_uniq_display = len(valid_athlete_ids_display)

        done_c, req_c, not_sol_c, pend_c, tot_tsk_slots = 0, 0, 0, 0, 0
        df_valid_fighters_tasks_display = df_stats_source[df_stats_source["Lutador"] != "N/A"]

        for tsk in all_tsks_raw:
            if tsk in df_valid_fighters_tasks_display.columns:
                task_emojis_series = df_valid_fighters_tasks_display[tsk]
                tot_tsk_slots += len(task_emojis_series)
                done_c += (task_emojis_series == STATUS_TO_EMOJI.get("Done")).sum()
                req_c += (task_emojis_series == STATUS_TO_EMOJI.get("Requested")).sum() # Usando o emoji correto de STATUS_TO_EMOJI
                not_sol_c += (task_emojis_series == STATUS_TO_EMOJI.get("---")).sum()
                pend_c += (task_emojis_series == STATUS_TO_EMOJI.get("Pendente")).sum()
        
        stat_cs = st.columns(3) # Mantido em 3 colunas para mobile
        
        stat_cs[0].metric("Lutas no Evento", num_lutas_evento_original)
        stat_cs[1].metric("Atletas Exibidos", tot_ath_uniq_display)
        
        if tot_tsk_slots > 0:
            # Exibe a contagem de "Done" e "Requested" se houver espaço
            # Ou pode usar um expander para mais detalhes
            metric_help_text = f"Das {tot_tsk_slots} tarefas para atletas exibidos."
            stat_cs[2].metric(f"Tarefas {STATUS_TO_EMOJI['Done']} / {STATUS_TO_EMOJI['Requested']}", 
                              f"{done_c} / {req_c}", 
                              help=metric_help_text)
        else:
            stat_cs[2].metric("Tarefas (Exib.)", "N/A")

    else:
        if search_term: st.info(f"Nenhum dado para estatísticas com o termo '{search_term}'.")
        else: st.info("Nenhum dado para estatísticas do evento.")

    st.markdown(f"--- \n *Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
