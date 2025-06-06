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
# ATHLETES_INFO_TAB_NAME = "df" # Não é mais primariamente necessário se AthleteID está no Fightcard
# ATHLETE_SHEET_NAME_COL = "NAME" 
# ATHLETE_SHEET_ID_COL = "ID"     
ATTENDANCE_TAB_NAME = "Attendance"
ATTENDANCE_ATHLETE_ID_COL = "Athlete ID" # ID do atleta na aba Attendance (DEVE CORRESPONDER ao AthleteID do Fightcard)
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"
# NAME_COLUMN_IN_ATTENDANCE = "Fighter" # Pode ser removido se Attendance for buscado apenas por ID

# Novas Constantes para Fightcard
FC_EVENT_COL = "Event"
FC_FIGHTER_COL = "Fighter"      # Nome do lutador
FC_ATHLETE_ID_COL = "AthleteID" # NOVA COLUNA DE ID DO ATLETA NO FIGHTCARD
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
    # ... (como antes)
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets: st.error("CRÍTICO: `gcp_service_account` não nos segredos.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e: st.error(f"CRÍTICO: Erro gspread client: {e}", icon="🚨"); st.stop()


def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    # ... (como antes) ...
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
        # --- Carrega e trata a nova coluna AthleteID ---
        if FC_ATHLETE_ID_COL in df.columns:
            df[FC_ATHLETE_ID_COL] = df[FC_ATHLETE_ID_COL].astype(str).str.strip().fillna("") # Garante string e trata NaNs
        else:
            st.error(f"CRÍTICO: Coluna '{FC_ATHLETE_ID_COL}' não encontrada no Fightcard. Verifique a planilha.")
            df[FC_ATHLETE_ID_COL] = "" # Adiciona coluna vazia para evitar erros, mas funcionalidade será limitada
        
        return df.dropna(subset=[FC_FIGHTER_COL, FC_ORDER_COL, FC_ATHLETE_ID_COL]) # Garante que temos ID
    except Exception as e: st.error(f"Erro ao carregar Fightcard: {e}"); return pd.DataFrame()

# load_athletes_info_df não é mais necessária se FC_ATHLETE_ID_COL existe e é confiável.
# Se você ainda precisar dela para outras infos, mantenha-a. Por agora, vou comentá-la.
# @st.cache_data(ttl=600)
# def load_athletes_info_df(sheet_name=MAIN_SHEET_NAME, athletes_tab=ATHLETES_INFO_TAB_NAME):
#     # ...

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    # ... (como antes, mas garanta que ATTENDANCE_ATHLETE_ID_COL é string e limpa) ...
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records()); 
        if df_att.empty: return pd.DataFrame()
        # Garante que colunas chave são string e limpas
        cols_to_process = [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL]
        # NAME_COLUMN_IN_ATTENDANCE não é mais crucial se usamos ID para tudo
        # if NAME_COLUMN_IN_ATTENDANCE not in cols_to_process: cols_to_process.append(NAME_COLUMN_IN_ATTENDANCE)
        
        for col in cols_to_process:
            if col in df_att.columns: df_att[col] = df_att[col].astype(str).str.strip()
            else: df_att[col] = None 
        return df_att 
    except Exception as e: st.error(f"Erro ao carregar Attendance: {e}"); return pd.DataFrame()


@st.cache_data(ttl=600)
def get_task_list(sheet_name=MAIN_SHEET_NAME, config_tab=CONFIG_TAB_NAME):
    # ... (como antes) ...
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab)
    try:
        data = worksheet.get_all_values();
        if not data or len(data) < 1: return [] 
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        return df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
    except Exception as e: st.error(f"Erro ao carregar TaskList da Config: {e}"); return []


def get_task_status_representation(athlete_id_to_check, task_name, df_attendance):
    # Esta função já usa athlete_id_to_check, o que é bom.
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
    if ATTENDANCE_TIMESTAMP_COL in relevant_records.columns:
        try:
            rel_sorted=relevant_records.copy();rel_sorted.loc[:,"Timestamp_dt"]=pd.to_datetime(rel_sorted[ATTENDANCE_TIMESTAMP_COL],format="%d/%m/%Y %H:%M:%S",errors='coerce')
            if rel_sorted["Timestamp_dt"].notna().any():latest_status_str=rel_sorted.sort_values(by="Timestamp_dt",ascending=False,na_position='last').iloc[0][ATTENDANCE_STATUS_COL]
        except:pass
    return STATUS_TO_EMOJI.get(str(latest_status_str).strip(),DEFAULT_EMOJI)

# --- Início da Página Streamlit ---
st.markdown("<h1 style='text-align: center; font-size: 2.5em; margin-bottom: 5px;'>DASHBOARD DE ATLETAS E TAREFAS</h1>",unsafe_allow_html=True)
refresh_count = st_autorefresh(interval=60000,limit=None,key="dash_auto_refresh_v2")

if 'font_size_pref_dn3' not in st.session_state: st.session_state.font_size_pref_dn3="Normal" # Nova chave de estado
font_options_map={"Normal":"1.0rem","Médio":"1.1rem","Grande":"1.2rem"}
ctrl_cols=st.columns([0.25,0.25,0.5])
with ctrl_cols[0]:
    if st.button("🔄 Atualizar Agora",key="refresh_dash_manual_btn3",use_container_width=True): # Nova chave
        load_fightcard_data.clear();load_attendance_data.clear();get_task_list.clear()
        # load_athletes_info_df.clear() # Não mais necessário se não for usada
        st.toast("Dados atualizados!",icon="🎉");st.rerun()
with ctrl_cols[1]:
    font_sel=st.selectbox("Fonte Tabela:",options=list(font_options_map.keys()),index=list(font_options_map.keys()).index(st.session_state.font_size_pref_dn3),key="font_sel_dn3") # Nova chave
    if font_sel!=st.session_state.font_size_pref_dn3:st.session_state.font_size_pref_dn3=font_sel;st.rerun()
curr_font_css=font_options_map[st.session_state.font_size_pref_dn3]
st.markdown(f"""<style> div[data-testid="stDataFrameResizable"] div[data-baseweb="table-cell"] > div {{ margin: auto; }} div[data-testid="stDataFrameResizable"] div[data-baseweb="table-cell"] {{ font-size:{curr_font_css} !important; text-align:center !important; vertical-align:middle !important; display:flex !important; align-items:center !important; justify-content:center !important;}} div[data-testid="stDataFrameResizable"] div[data-baseweb="table-header-cell"] {{ font-size:calc({curr_font_css} + 0.05rem) !important; font-weight:bold !important; text-transform:uppercase; text-align:center !important; white-space:normal !important; word-break:break-word !important;}} </style>""",True)
st.markdown("<hr style='margin-top:5px;margin-bottom:15px;'>",True)

df_fc=None;df_att=None;all_tsks=None;load_err=False;err_ph=st.empty() # Removido df_ath_info daqui
with st.spinner("Carregando dados..."):
    try:
        df_fc=load_fightcard_data();df_att=load_attendance_data();all_tsks=get_task_list()
        # df_ath_info=load_athletes_info_df() # Não carrega mais por padrão
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
    ev_opts=["Todos os Eventos"]+avail_evs;sel_ev_opt=st.selectbox("Selecione Evento:",options=ev_opts,index=0,key="ev_sel_dn3") # Nova chave
    df_fc_disp=df_fc.copy()
    if sel_ev_opt!="Todos os Eventos":df_fc_disp=df_fc[df_fc[FC_EVENT_COL]==sel_ev_opt].copy()
    if df_fc_disp.empty:st.info(f"Nenhuma luta para '{sel_ev_opt}'.");st.stop()
    
    # fighter_to_id_map não é mais necessário se usamos FC_ATHLETE_ID_COL
    
    dash_data_list=[]
    for order,group in df_fc_disp.sort_values(by=[FC_EVENT_COL,FC_ORDER_COL]).groupby([FC_EVENT_COL,FC_ORDER_COL]):
        ev,f_ord=order;bl_s=group[group[FC_CORNER_COL]=="blue"].squeeze(axis=0);rd_s=group[group[FC_CORNER_COL]=="red"].squeeze(axis=0)
        row_d={"Evento":ev,"Luta #":int(f_ord)if pd.notna(f_ord)else""}
        for corn_pref,ser_data in[("Azul",bl_s),("Vermelho",rd_s)]:
            f_name_fc=str(ser_data.get(FC_FIGHTER_COL,"N/A")).strip()if isinstance(ser_data,pd.Series)else"N/A"
            # --- USA O NOVO FC_ATHLETE_ID_COL ---
            athlete_id_from_fightcard = str(ser_data.get(FC_ATHLETE_ID_COL, "")).strip() if isinstance(ser_data, pd.Series) else ""
            
            pic_u=ser_data.get(FC_PICTURE_COL,"")if isinstance(ser_data,pd.Series)else""
            row_d[f"Foto {corn_pref}"]=pic_u if isinstance(pic_u,str)and pic_u.startswith("http")else None
            
            # --- Coluna Combinada: ID - Nome ---
            id_display = athlete_id_from_fightcard if athlete_id_from_fightcard else "N/D"
            row_d[f"Lutador {corn_pref}"]=f"{id_display} - {f_name_fc}"if f_name_fc!="N/A"else"N/A"
            
            if pd.notna(f_name_fc)and f_name_fc!="N/A" and athlete_id_from_fightcard: # Usa athlete_id_from_fightcard
                for tsk in all_tsks:
                    emoji_stat = get_task_status_representation(athlete_id_from_fightcard,tsk,df_att) # Passa ID do fightcard
                    row_d[f"{tsk} ({corn_pref})"]=emoji_stat
            else:
                for tsk in all_tsks:row_d[f"{tsk} ({corn_pref})"]=STATUS_TO_EMOJI.get("Pendente",DEFAULT_EMOJI)
        row_d["Divisão"]=bl_s.get(FC_DIVISION_COL,rd_s.get(FC_DIVISION_COL,"N/A"))if isinstance(bl_s,pd.Series)else(rd_s.get(FC_DIVISION_COL,"N/A")if isinstance(rd_s,pd.Series)else"N/A")
        dash_data_list.append(row_d)

    if not dash_data_list:st.info(f"Nenhuma luta processada para '{sel_ev_opt}'.");st.stop()
    df_dash=pd.DataFrame(dash_data_list)

    col_conf_edit={ # Removidas colunas de ID separadas
        "Evento":st.column_config.TextColumn(width="small",disabled=True),"Luta #":st.column_config.NumberColumn(width="small",format="%d",disabled=True),
        "Foto Azul":st.column_config.ImageColumn("Foto(A)",width="small"),"Lutador Azul":st.column_config.TextColumn("Lutador(A) [ID - Nome]",width="large",disabled=True),
        "Divisão":st.column_config.TextColumn(width="medium",disabled=True),
        "Lutador Vermelho":st.column_config.TextColumn("Lutador(V) [ID - Nome]",width="large",disabled=True),"Foto Vermelho":st.column_config.ImageColumn("Foto(V)",width="small"),
    }
    col_ord_list=["Evento","Luta #","Foto Azul","Lutador Azul"] # Removidas colunas de ID separadas
    for tsk_n_col in all_tsks:col_ord_list.append(f"{tsk_n_col} (Azul)")
    col_ord_list.append("Divisão")
    for tsk_n_col in all_tsks:col_ord_list.append(f"{tsk_n_col} (Vermelho)")
    col_ord_list.extend(["Lutador Vermelho","Foto Vermelho"]) # Removidas colunas de ID separadas
    
    leg_parts=[f"{emo}: {dsc}"for emo,dsc in EMOJI_LEGEND.items()if emo.strip()!=""]
    help_txt_leg_disp=", ".join(leg_parts)
    for tsk_n_col in all_tsks:
        col_conf_edit[f"{tsk_n_col} (Azul)"]=st.column_config.TextColumn(label=tsk_n_col,width="small",help=f"Status:{help_txt_leg_disp}",disabled=True)
        col_conf_edit[f"{tsk_n_col} (Vermelho)"]=st.column_config.TextColumn(label=tsk_n_col,width="small",help=f"Status:{help_txt_leg_disp}",disabled=True)

    st.subheader(f"Detalhes das Lutas e Tarefas: {sel_ev_opt}")
    st.markdown(f"**Legenda Status Tarefas:** {help_txt_leg_disp}")
    tbl_h=(len(df_dash)+1)*45+10;tbl_h=max(400,min(tbl_h,1200))
    st.data_editor(df_dash,column_config=col_conf_edit,column_order=col_ord_list,hide_index=True,use_container_width=True,num_rows="fixed",disabled=True,height=tbl_h)
    st.markdown("---")

    st.subheader(f"Estatísticas do Evento: {sel_ev_opt}")
    if not df_dash.empty:
        tot_lutas_ev=df_dash["Luta #"].nunique();uniq_f_ev=set()
        for _,r in df_dash.iterrows(): # Usa a coluna combinada para extrair IDs para contagem de únicos
            if r["Lutador Azul"]!="N/A":uniq_f_ev.add(r["Lutador Azul"].split(" - ",1)[0].strip())
            if r["Lutador Vermelho"]!="N/A":uniq_f_ev.add(r["Lutador Vermelho"].split(" - ",1)[0].strip())
        tot_ath_uniq_ev=len(uniq_f_ev)
        done_c,req_c,not_sol_c,pend_c,tot_tsk_slots=0,0,0,0,0
        for tsk in all_tsks:
            for corn in["Azul","Vermelho"]:
                col_n=f"{tsk} ({corn})"
                if col_n in df_dash.columns:
                    val_f_mask=df_dash[f"Lutador {corn}"]!="N/A";tsk_emo_ser=df_dash.loc[val_f_mask,col_n]
                    tot_tsk_slots+=len(tsk_emo_ser)
                    done_c+=(tsk_emo_ser==STATUS_TO_EMOJI["Done"]).sum();req_c+=(tsk_emo_ser==STATUS_TO_EMOJI["Requested"]).sum()
                    not_sol_c+=(tsk_emo_ser==STATUS_TO_EMOJI["---"]).sum();pend_c+=(tsk_emo_ser==STATUS_TO_EMOJI["Pendente"]).sum()
        stat_cs=st.columns(5)
        stat_cs[0].metric("Lutas",tot_lutas_ev);stat_cs[1].metric("Atletas Únicos",tot_ath_uniq_ev)
        stat_cs[2].metric(f"Tarefas {STATUS_TO_EMOJI['Done']}",done_c,help=f"De {tot_tsk_slots} slots.")
        stat_cs[3].metric(f"Tarefas {STATUS_TO_EMOJI['Requested']}",req_c)
        stat_cs[4].metric(f"Tarefas {STATUS_TO_EMOJI['---']}",not_sol_c)
    else:st.info("Nenhum dado para estatísticas do evento.")
    st.markdown(f"--- \n *Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
