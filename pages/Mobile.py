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

# Novas Constantes para Fightcard
FC_EVENT_COL = "Event"
FC_FIGHTER_COL = "Fighter"
FC_ATHLETE_ID_COL = "AthleteID"
FC_CORNER_COL = "Corner"
FC_ORDER_COL = "FightOrder"
FC_PICTURE_COL = "Picture"
FC_DIVISION_COL = "Division"

STATUS_TO_EMOJI = {
    "Done": "🟩", "Requested": "🟧", "---": "➖", "Não Solicitado": "➖",
    "Pendente": "🟥", "Não Registrado": "🟥"
}
DEFAULT_EMOJI = "🟥"
EMOJI_LEGEND = {
    "🟩": "Done", "🟧": "Requested", "➖": "---", "🟥": "Pendente"
}

# --- Funções de Conexão e Carregamento de Dados ---
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
            st.error(f"CRÍTICO: Coluna '{FC_ATHLETE_ID_COL}' não encontrada no Fightcard. Verifique a planilha.")
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
            else: df_att[col] = pd.NA # Usar pd.NA para consistência com outros NAs
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
            # Garantir que a coluna Timestamp seja convertida corretamente, tratando NaNs
            relevant_records_copy = relevant_records.copy()
            relevant_records_copy["Timestamp_dt"] = pd.to_datetime(relevant_records_copy[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce')
            
            # Filtrar NaT (Not a Time) antes de ordenar, se houver algum
            valid_timestamps = relevant_records_copy.dropna(subset=["Timestamp_dt"])
            if not valid_timestamps.empty:
                latest_status_str = valid_timestamps.sort_values(by="Timestamp_dt", ascending=False).iloc[0][ATTENDANCE_STATUS_COL]
        except Exception: # Captura qualquer exceção durante a conversão/ordenação
            pass # Mantém o latest_status_str original se a ordenação falhar
    return STATUS_TO_EMOJI.get(str(latest_status_str).strip(),DEFAULT_EMOJI)


# --- Início da Página Streamlit ---
st.set_page_config(layout="wide") # Usar layout amplo pode ajudar, mesmo em mobile
st.markdown("<h1 style='text-align: center; font-size: 2em; margin-bottom: 5px;'>DASHBOARD DE ATLETAS</h1>",unsafe_allow_html=True) # Título um pouco menor
refresh_count = st_autorefresh(interval=60000,limit=None,key="dash_auto_refresh_v3_mobile")

if 'font_size_pref_dn_mobile' not in st.session_state: st.session_state.font_size_pref_dn_mobile="Pequeno"
font_options_map={"Pequeno":"0.8rem", "Normal":"0.9rem","Médio":"1.0rem"} # Ajustado para mobile
ctrl_cols=st.columns([0.35,0.35,0.3]) # Ajuste para botões e seletor
with ctrl_cols[0]:
    if st.button("🔄 Atualizar",key="refresh_dash_manual_btn_mobile",use_container_width=True):
        st.cache_data.clear(); st.cache_resource.clear()
        st.toast("Dados atualizados!",icon="🎉");st.rerun()
with ctrl_cols[1]:
    font_sel=st.selectbox("Fonte:",options=list(font_options_map.keys()),index=list(font_options_map.keys()).index(st.session_state.font_size_pref_dn_mobile),key="font_sel_dn_mobile")
    if font_sel!=st.session_state.font_size_pref_dn_mobile:st.session_state.font_size_pref_dn_mobile=font_sel;st.rerun()
curr_font_css=font_options_map[st.session_state.font_size_pref_dn_mobile]

# CSS para centralizar conteúdo das células e ajustar tamanho da fonte
st.markdown(f"""
    <style>
        div[data-testid="stDataFrameResizable"] div[data-baseweb="table-cell"] > div {{
            margin: auto;
            white-space: normal !important; /* Permite quebra de linha no nome do lutador */
            word-break: break-word !important; /* Quebra palavras longas */
        }}
        div[data-testid="stDataFrameResizable"] div[data-baseweb="table-cell"] {{
            font-size:{curr_font_css} !important;
            text-align:center !important;
            vertical-align:middle !important;
            display:flex !important;
            align-items:center !important;
            justify-content:center !important;
            padding-top: 5px !important;
            padding-bottom: 5px !important;
        }}
        div[data-testid="stDataFrameResizable"] div[data-baseweb="table-header-cell"] {{
            font-size:calc({curr_font_css} + 0.05rem) !important;
            font-weight:bold !important;
            text-transform:uppercase;
            text-align:center !important;
            white-space:normal !important;
            word-break:break-word !important;
            background-color: #f0f2f6; /* Cor de fundo leve para o cabeçalho */
        }}
        /* Para imagens, limitar a altura para não esticar demais a linha */
        div[data-testid="stDataFrameResizable"] img {{
            max-height: 50px;
            object-fit: contain;
        }}
    </style>
""", unsafe_allow_html=True)
st.markdown("<hr style='margin-top:5px;margin-bottom:15px;'>",True)

df_fc=None;df_att=None;all_tsks=None;load_err=False;err_ph=st.empty()
with st.spinner("Carregando dados..."):
    try:
        df_fc=load_fightcard_data();df_att=load_attendance_data();all_tsks=get_task_list()
        if df_fc.empty or not all_tsks:load_err=True
    except Exception as e:err_ph.error(f"Erro crítico carregamento: {e}");load_err=True

if load_err:
    if df_fc is not None and df_fc.empty:err_ph.warning("Fightcard vazio.")
    if not all_tsks:err_ph.error("Lista de Tarefas vazia.")
    if not(df_fc is not None and df_fc.empty)and not(not all_tsks):st.error("Falha carregar dados.")
elif df_fc.empty:st.warning("Nenhum dado de Fightcard.")
elif not all_tsks:st.error("TaskList não carregada.")
else:
    avail_evs=sorted(df_fc[FC_EVENT_COL].dropna().unique().tolist(),reverse=True)
    if not avail_evs:st.warning("Nenhum evento no Fightcard.");st.stop()
    ev_opts=["Todos os Eventos"]+avail_evs
    sel_ev_opt=st.selectbox("Selecione Evento:",options=ev_opts,index=0,key="ev_sel_dn_mobile")
    df_fc_disp=df_fc.copy()
    if sel_ev_opt!="Todos os Eventos":df_fc_disp=df_fc[df_fc[FC_EVENT_COL]==sel_ev_opt].copy()
    if df_fc_disp.empty:st.info(f"Nenhuma luta para '{sel_ev_opt}'.");st.stop()

    dash_data_list=[]
    # Agrupa por Evento e Ordem da Luta para processar cada luta
    for (event, fight_order), group in df_fc_disp.sort_values(by=[FC_EVENT_COL, FC_ORDER_COL]).groupby([FC_EVENT_COL, FC_ORDER_COL], sort=False):
        blue_fighter_series = group[group[FC_CORNER_COL] == "blue"].squeeze(axis=0)
        red_fighter_series = group[group[FC_CORNER_COL] == "red"].squeeze(axis=0)

        # Determina a divisão da luta (pega do primeiro lutador válido que tiver)
        division = "N/A"
        if isinstance(blue_fighter_series, pd.Series) and pd.notna(blue_fighter_series.get(FC_DIVISION_COL)):
            division = blue_fighter_series.get(FC_DIVISION_COL)
        elif isinstance(red_fighter_series, pd.Series) and pd.notna(red_fighter_series.get(FC_DIVISION_COL)):
            division = red_fighter_series.get(FC_DIVISION_COL)

        fighters_in_fight = []
        if isinstance(blue_fighter_series, pd.Series) and blue_fighter_series.get(FC_FIGHTER_COL, "N/A") != "N/A":
            fighters_in_fight.append(("Azul", blue_fighter_series))
        if isinstance(red_fighter_series, pd.Series) and red_fighter_series.get(FC_FIGHTER_COL, "N/A") != "N/A":
            fighters_in_fight.append(("Vermelho", red_fighter_series))
        
        # Se não houver lutadores válidos para esta "luta", pula
        if not fighters_in_fight:
            continue

        for corner_name, fighter_data in fighters_in_fight:
            fighter_row = {
                "Evento": event,
                "Luta #": int(fight_order) if pd.notna(fight_order) else "",
                "Canto": corner_name,
                "Divisão": division
            }

            fighter_name_fc = str(fighter_data.get(FC_FIGHTER_COL, "N/A")).strip()
            athlete_id_fc = str(fighter_data.get(FC_ATHLETE_ID_COL, "")).strip()
            picture_url = fighter_data.get(FC_PICTURE_COL, "")

            fighter_row["Foto"] = picture_url if isinstance(picture_url, str) and picture_url.startswith("http") else None
            
            id_display = athlete_id_fc if athlete_id_fc else "N/D"
            fighter_row["Lutador [ID - Nome]"] = f"{id_display} - {fighter_name_fc}" if fighter_name_fc != "N/A" else "N/A"

            if fighter_name_fc != "N/A" and athlete_id_fc:
                for task in all_tsks:
                    emoji_status = get_task_status_representation(athlete_id_fc, task, df_att)
                    fighter_row[task] = emoji_status
            else:
                for task in all_tsks:
                    fighter_row[task] = STATUS_TO_EMOJI.get("Pendente", DEFAULT_EMOJI)
            
            dash_data_list.append(fighter_row)

    if not dash_data_list:st.info(f"Nenhuma luta processada para '{sel_ev_opt}'.");st.stop()
    df_dash=pd.DataFrame(dash_data_list)

    # Configuração das colunas para o data_editor
    col_conf_edit = {
        "Evento": st.column_config.TextColumn(width="small", disabled=True),
        "Luta #": st.column_config.NumberColumn(width="small", format="%d", disabled=True),
        "Canto": st.column_config.TextColumn(width="small", disabled=True, 
                                             help="Canto do Lutador (Azul/Vermelho)"),
        "Foto": st.column_config.ImageColumn("Foto", width="small"), # Largura 'small' para mobile
        "Lutador [ID - Nome]": st.column_config.TextColumn("Lutador", width="medium", disabled=True), # Medium para caber nome
        "Divisão": st.column_config.TextColumn(width="small", disabled=True),
    }

    # Ordem das colunas
    col_ord_list = ["Evento", "Luta #", "Canto", "Foto", "Lutador [ID - Nome]"]
    # Adiciona colunas de tarefas dinamicamente
    for task_name_col in all_tsks:
        col_ord_list.append(task_name_col)
    col_ord_list.append("Divisão")

    leg_parts=[f"{emo}: {dsc}"for emo,dsc in EMOJI_LEGEND.items()if emo.strip()!=""]
    help_txt_leg_disp=", ".join(leg_parts)

    for task_name_col in all_tsks:
        col_conf_edit[task_name_col] = st.column_config.TextColumn(
            label=task_name_col, # Nome curto da tarefa
            width="small", # Pequeno para os emojis
            help=f"Status da Tarefa: {help_txt_leg_disp}",
            disabled=True
        )

    st.subheader(f"Detalhes dos Lutadores: {sel_ev_opt}")
    st.markdown(f"**Legenda:** {help_txt_leg_disp}")
    
    # Ajuste dinâmico da altura da tabela
    num_rows_display = len(df_dash)
    row_height_approx = 65 # Altura aproximada de uma linha com imagem, ajuste conforme necessário
    header_height = 45
    table_height = min(max(300, (num_rows_display * row_height_approx) + header_height), 800) # min 300px, max 800px

    st.data_editor(
        df_dash,
        column_config=col_conf_edit,
        column_order=col_ord_list,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed", # "dynamic" pode ser melhor para mobile se a altura fixa for um problema
        disabled=True,
        height=int(table_height) # Convertido para int
    )
    st.markdown("---")

    st.subheader(f"Estatísticas do Evento: {sel_ev_opt}")
    if not df_dash.empty:
        # Lutas únicas: agrupa por Evento e Luta # e conta os grupos
        tot_lutas_ev = df_dash.groupby([FC_EVENT_COL, "Luta #"]).ngroups
        
        # Atletas únicos: extrai ID da coluna "Lutador [ID - Nome]" e conta os únicos válidos
        valid_athlete_ids = df_dash[df_dash["Lutador [ID - Nome]"] != "N/A"]["Lutador [ID - Nome]"].apply(
            lambda x: x.split(" - ", 1)[0].strip() if isinstance(x, str) and " - " in x else pd.NA
        ).dropna().unique()
        tot_ath_uniq_ev = len(valid_athlete_ids)

        done_c, req_c, not_sol_c, pend_c, tot_tsk_slots = 0, 0, 0, 0, 0
        
        # Filtra apenas linhas com lutadores válidos para contagem de tarefas
        df_valid_fighters_tasks = df_dash[df_dash["Lutador [ID - Nome]"] != "N/A"]

        for tsk in all_tsks:
            if tsk in df_valid_fighters_tasks.columns:
                task_emojis_series = df_valid_fighters_tasks[tsk]
                tot_tsk_slots += len(task_emojis_series)
                done_c += (task_emojis_series == STATUS_TO_EMOJI.get("Done")).sum()
                req_c += (task_emojis_series == STATUS_TO_EMOJI.get("Requested")).sum()
                not_sol_c += (task_emojis_series == STATUS_TO_EMOJI.get("---")).sum() # Inclui "Não Solicitado"
                pend_c += (task_emojis_series == STATUS_TO_EMOJI.get("Pendente")).sum() # Inclui "Não Registrado"
        
        # Para mobile, 2 ou 3 colunas de métricas podem ser melhores
        stat_cols_count = 3 if tot_ath_uniq_ev > 0 else 2 # Ajuste conforme necessário
        stat_cs = st.columns(stat_cols_count)
        
        stat_cs[0].metric("Lutas", tot_lutas_ev)
        if tot_ath_uniq_ev > 0 :
             stat_cs[1].metric("Atletas Únicos", tot_ath_uniq_ev)
        
        # As métricas de tarefas podem ir para uma segunda linha de colunas ou expanders
        # Tentativa com as colunas restantes:
        next_col_idx = 2 if tot_ath_uniq_ev > 0 else 1

        if next_col_idx < stat_cols_count:
            stat_cs[next_col_idx].metric(f"Tarefas {STATUS_TO_EMOJI['Done']}", done_c, help=f"De {tot_tsk_slots} slots de tarefas.")
        else: # Se não houver mais colunas, cria uma nova linha para elas
            extra_stat_cols = st.columns(3) # Para Done, Requested, ---
            extra_stat_cols[0].metric(f"Tarefas {STATUS_TO_EMOJI['Done']}", done_c, help=f"De {tot_tsk_slots} slots de tarefas.")
            if len(extra_stat_cols) > 1:
                extra_stat_cols[1].metric(f"Tarefas {STATUS_TO_EMOJI['Requested']}", req_c)
            if len(extra_stat_cols) > 2:
                extra_stat_cols[2].metric(f"Tarefas {STATUS_TO_EMOJI['---']}", not_sol_c)

        # Se ainda precisar mostrar pendentes e houver espaço:
        # if next_col_idx + 1 < stat_cols_count:
        #     stat_cs[next_col_idx + 1].metric(f"Tarefas {STATUS_TO_EMOJI['Requested']}", req_c)
        # if next_col_idx + 2 < stat_cols_count:
        #     stat_cs[next_col_idx + 2].metric(f"Tarefas {STATUS_TO_EMOJI['---']}", not_sol_c)


    else:st.info("Nenhum dado para estatísticas do evento.")
    st.markdown(f"--- \n *Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
