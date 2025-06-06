"""
================================================================================
 ATUALIZAÇÕES PRINCIPAIS NESTA VERSÃO
================================================================================
1.  SEGUNDA VERIFICAÇÃO (CONFIRMAÇÃO DE AÇÃO):
    - Antes de registrar qualquer alteração de status (como 'Requested' ou 'Done'),
      o sistema agora exibe uma mensagem de confirmação.
    - O usuário deve clicar em "Sim, confirmar" para que a ação seja salva.
    - Isso evita registros acidentais e aumenta a segurança das operações.
    - Implementado usando st.session_state['pending_confirmation'].

2.  FUNCIONALIDADE DE DESFAZER (UNDO):
    - Um botão "↩️ Desfazer" foi adicionado. Ele fica ativo após um registro ser
      realizado com sucesso.
    - Permite que o usuário reverta imediatamente a última ação de registro,
      removendo a entrada correspondente da planilha 'Attendance'.
    - Ideal para corrigir erros de forma rápida.
    - Implementado usando a função undo_last_log() e o estado
      st.session_state['last_action_details'].

3.  MELHORIAS DE ROBUSTEZ:
    - O cálculo do ID do log foi aprimorado para ser mais confiável.
    - A função de desfazer localiza a linha exata a ser removida com base em
      múltiplos critérios (ID do Log, ID do Atleta, Tarefa, Usuário, Timestamp),
      tornando-a mais segura em um ambiente com múltiplas atualizações.
================================================================================
"""

# --- 0. Importar Bibliotecas ---
import streamlit as st  # Para criar a interface web do aplicativo
import pandas as pd  # Para manipulação de dados em DataFrames
import gspread  # Para interagir com a API do Google Sheets
from google.oauth2.service_account import Credentials  # Para autenticação com a API do Google
from datetime import datetime, timedelta  # Para trabalhar com datas e horas (timestamps, validade)
import html  # Para escapar caracteres HTML e prevenir XSS em exibições de dados

# --- 1. Configuração da Página ---
# Define o título da página, o layout e outras configurações iniciais.
st.set_page_config(page_title="Consulta e Registro de Atletas", layout="wide")

# --- Constantes ---
# Define nomes fixos para planilhas e abas, facilitando a manutenção do código.
MAIN_SHEET_NAME = "UAEW_App"  # Nome do arquivo da planilha principal no Google Drive
ATHLETES_TAB_NAME = "df"  # Nome da aba (worksheet) que contém os dados dos atletas
USERS_TAB_NAME = "Users"  # Nome da aba com os dados dos usuários autorizados
ATTENDANCE_TAB_NAME = "Attendance"  # Nome da aba onde os logs de registro são salvos
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"  # Nome exato da coluna de ID do atleta na aba de logs
CONFIG_TAB_NAME = "Config"  # Nome da aba de configurações (lista de tarefas, status, etc.)
NO_TASK_SELECTED_LABEL = "-- Selecione uma Tarefa --"  # Texto padrão para o seletor de tarefas
STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"]  # Status considerados como "pendente"

# --- 2. Conexão com Google Sheets ---
# Usa o cache de recursos do Streamlit para evitar reconectar/reautorizar a cada interação.
@st.cache_resource(ttl=3600)  # Cache válido por 1 hora (3600 segundos)
def get_gspread_client():
    """Autoriza e retorna um cliente gspread para interagir com a API do Google Sheets."""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        # Pega as credenciais do serviço (armazenadas de forma segura no Streamlit Secrets).
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except KeyError as e: 
        st.error(f"Erro de configuração: Chave GCP ausente. Detalhes: {e}", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro na API do Google: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    """Abre uma planilha e retorna um objeto da aba (worksheet) específica."""
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    # Trata erros comuns, como planilha ou aba não encontrada.
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada em '{sheet_name}'.", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨"); st.stop()

# --- 3. Carregamento de Dados ---
# Usa o cache de dados do Streamlit para evitar recarregar os dados da planilha a cada interação.
@st.cache_data(ttl=600)  # Cache válido por 10 minutos (600 segundos)
def load_athlete_data(sheet_name: str = MAIN_SHEET_NAME, athletes_tab_name: str = ATHLETES_TAB_NAME):
    """Carrega, processa e retorna um DataFrame com os dados dos atletas."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, athletes_tab_name)
        data = worksheet.get_all_records()  # Pega todos os dados como uma lista de dicionários.
        if not data: return pd.DataFrame()  # Retorna DataFrame vazio se não houver dados.
        
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame()

        # Verifica se colunas essenciais existem.
        if "ROLE" not in df.columns or "INACTIVE" not in df.columns:
            st.error(f"Colunas 'ROLE'/'INACTIVE' não encontradas em '{athletes_tab_name}'.", icon="🚨"); return pd.DataFrame()
        
        # Limpeza e processamento dos dados.
        df.columns = df.columns.str.strip()  # Remove espaços em branco dos nomes das colunas.
        # Converte a coluna 'INACTIVE' (que pode ser texto ou número) para um tipo booleano.
        if df["INACTIVE"].dtype == 'object':
            df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        elif pd.api.types.is_numeric_dtype(df["INACTIVE"]):
            df["INACTIVE"] = df["INACTIVE"].map({0: False, 1: True}).fillna(True)
        
        # Filtra para manter apenas atletas ativos com o papel 'Fighter'.
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        
        # Prepara e formata colunas específicas.
        df["EVENT"] = df["EVENT"].fillna("Z") if "EVENT" in df.columns else "Z"
        date_cols = ["DOB", "PASSPORT EXPIRE DATE", "BLOOD TEST"]
        for col in date_cols:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
            else: df[col] = "" 
        for col_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE"]:
            df[col_check] = df[col_check].fillna("") if col_check in df.columns else ""
        if "NAME" not in df.columns:
            st.error(f"'NAME' não encontrada em '{athletes_tab_name}'.", icon="🚨"); return pd.DataFrame()
        
        # Ordena os atletas por evento e nome para uma exibição consistente.
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar atletas (gspread): {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=300) # Cache de 5 minutos
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    """Carrega e retorna os dados dos usuários da aba 'Users'."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, users_tab_name)
        return worksheet.get_all_records() or []
    except Exception as e:
        st.error(f"Erro ao carregar usuários '{users_tab_name}': {e}", icon="🚨"); return []

def get_valid_user_info(user_input: str, sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    """Verifica se o input do usuário (ID ou Nome) corresponde a um usuário válido na planilha."""
    if not user_input: return None
    all_users = load_users_data(sheet_name, users_tab_name)
    if not all_users: return None
    
    # Prepara o input para comparação (remove espaços e converte para maiúsculas).
    proc_input = user_input.strip().upper()
    # Permite input do ID com ou sem o prefixo "PS".
    val_id_input = proc_input[2:] if proc_input.startswith("PS") and len(proc_input) > 2 and proc_input[2:].isdigit() else proc_input
    
    # Itera sobre os usuários cadastrados para encontrar uma correspondência.
    for record in all_users:
        ps_sheet = str(record.get("PS", "")).strip()
        name_sheet = str(record.get("USER", "")).strip().upper()
        if ps_sheet == val_id_input or ("PS" + ps_sheet) == proc_input or name_sheet == proc_input or ps_sheet == proc_input:
            return record  # Retorna o registro do usuário se encontrado.
    return None  # Retorna None se não encontrar.

@st.cache_data(ttl=600) # Cache de 10 minutos
def load_config_data(sheet_name: str = MAIN_SHEET_NAME, config_tab_name: str = CONFIG_TAB_NAME):
    """Carrega dados de configuração (lista de tarefas e status) da aba 'Config'."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab_name)
        data = worksheet.get_all_values()
        if not data or len(data) < 1: st.error(f"Aba '{config_tab_name}' vazia/sem cabeçalho.", icon="🚨"); return [],[]
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().unique().tolist() if "TaskList" in df_conf.columns else []
        statuses = df_conf["TaskStatus"].dropna().unique().tolist() if "TaskStatus" in df_conf.columns else []
        if not tasks: st.warning(f"'TaskList' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        if not statuses: st.warning(f"'TaskStatus' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        return tasks, statuses
    except Exception as e: st.error(f"Erro ao carregar config '{config_tab_name}': {e}", icon="🚨"); return [], []

@st.cache_data(ttl=120) # Cache de 2 minutos para dados que mudam com frequência.
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    """Carrega e retorna um DataFrame com os logs de registro da aba 'Attendance'."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        # Garante que todas as colunas esperadas existam no DataFrame para evitar erros.
        expected_cols_order = ["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes"]
        for col in expected_cols_order:
            if col not in df_att.columns: df_att[col] = None
        return df_att
    except Exception as e: st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

# --- 4. Funções de Ação ---
def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, att_tab_name: str = ATTENDANCE_TAB_NAME):
    """Adiciona uma nova linha de log na aba 'Attendance'."""
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name)
        all_vals = log_ws.get_all_values() # Pega todos os valores para determinar o próximo ID.
        
        # Lógica para determinar o próximo número de ID do log (coluna '#').
        next_num_str = "1"
        if len(all_vals) > 1:
            last_entry_first_col_val = all_vals[-1][0] if all_vals[-1] and all_vals[-1][0] else ''
            if str(last_entry_first_col_val).strip().isdigit():
                next_num_str = str(int(last_entry_first_col_val) + 1)
            else:
                next_num_str = str(len(all_vals))
        elif len(all_vals) == 1 and all_vals[0]:
            next_num_str = "1"
        else:
             next_num_str = "1"

        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)
        new_row_data = [next_num_str, ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        
        # Adiciona a nova linha na planilha.
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        
        # ATUALIZAÇÃO: Armazena os detalhes desta ação para a funcionalidade "Desfazer".
        st.session_state.last_action_details = {
            "log_id_val": next_num_str,
            "athlete_id": ath_id,
            "task": task,
            "user": user_ident,
            "timestamp": ts,
            "sheet_name": sheet_name,
            "tab_name": att_tab_name
        }
        load_attendance_data.clear(); return True # Limpa o cache de 'Attendance' para refletir a mudança.
    except Exception as e: st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨"); return False

def undo_last_log():
    """Desfaz a última ação de registro, removendo a linha correspondente da planilha."""
    # Verifica se há uma ação para desfazer.
    if 'last_action_details' not in st.session_state or not st.session_state.last_action_details:
        st.warning("Nenhuma ação recente para desfazer.", icon="🤷")
        return

    details = st.session_state.last_action_details
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, details["sheet_name"], details["tab_name"])
        
        all_records = log_ws.get_all_records()
        row_to_delete_idx = -1

        # Itera de trás para frente para encontrar a linha exata que corresponde à última ação.
        # Isso é mais seguro do que simplesmente deletar a última linha da planilha.
        header_row = log_ws.row_values(1)
        id_column_header = header_row[0] if header_row else "#" # Nome da primeira coluna (ID do log)

        for i in range(len(all_records) -1, -1, -1):
            record = all_records[i]
            # Compara todos os detalhes para garantir que é a linha correta.
            if str(record.get(id_column_header, '')) == str(details["log_id_val"]) and \
               str(record.get(ID_COLUMN_IN_ATTENDANCE, '')) == str(details["athlete_id"]) and \
               record.get("Task") == details["task"] and \
               record.get("User") == details["user"] and \
               record.get("Timestamp") == details["timestamp"]:
                row_to_delete_idx = i + 2 # +1 (0-indexed -> 1-indexed) +1 (cabeçalho)
                break
        
        if row_to_delete_idx != -1:
            log_ws.delete_rows(row_to_delete_idx)
            st.success(f"Ação desfeita com sucesso!", icon="↩️")
            del st.session_state.last_action_details # Limpa a ação para não desfazer duas vezes.
            load_attendance_data.clear() # Limpa o cache para atualizar a UI.
        else:
            st.error("Não foi possível encontrar o registro para desfazer.", icon="🚨")
            if 'last_action_details' in st.session_state: del st.session_state.last_action_details

    except Exception as e:
        st.error(f"Erro ao desfazer a ação: {e}", icon="🚨")
        if 'last_action_details' in st.session_state: del st.session_state.last_action_details

def is_blood_test_expired(date_str: str) -> bool:
    """Verifica se a data do exame de sangue (Blood Test) está expirada (mais de 182 dias)."""
    if not date_str or pd.isna(date_str): return True
    try:
        dt_obj = pd.to_datetime(date_str, format="%d/%m/%Y", errors='coerce').to_pydatetime()
        return dt_obj < (datetime.now() - timedelta(days=182)) if dt_obj else True
    except: return True

# --- 5. Lógica Principal do Aplicativo ---
st.title("Consulta e Registro de Atletas")

# Inicialização do st.session_state para guardar informações entre interações.
default_ss = {
    "warning_message": None, "user_confirmed": False, "current_user_id": "", "current_user_name": "Usuário",
    "current_user_image_url": "", "show_personal_data": True, "selected_task": NO_TASK_SELECTED_LABEL,
    "selected_statuses": [],
    "pending_confirmation": None,  # Guarda detalhes da ação que aguarda confirmação.
    "last_action_details": None    # Guarda detalhes da última ação para o "Undo".
}
for k, v in default_ss.items():
    if k not in st.session_state: st.session_state[k] = v
if 'user_id_input' not in st.session_state: st.session_state['user_id_input'] = st.session_state['current_user_id']

# --- Seção de Autenticação do Usuário ---
with st.container(border=True):
    st.subheader("Identificação do Usuário")
    col_input_ps, col_user_status_display = st.columns([0.6, 0.4])
    with col_input_ps:
        st.session_state['user_id_input'] = st.text_input(
            "PS (ID de usuário) ou Nome", value=st.session_state['user_id_input'],
            key="uid_w", label_visibility="collapsed", placeholder="Digite seu PS ou Nome"
        )
        if st.button("Confirmar Usuário", key="confirm_b_w", use_container_width=True, type="primary"):
            u_in = st.session_state['user_id_input'].strip()
            if u_in:
                u_inf = get_valid_user_info(u_in)
                if u_inf:
                    # Se o usuário é válido, atualiza o session_state com seus dados.
                    st.session_state.update(
                        current_user_ps_id_internal=str(u_inf.get("PS", u_in)).strip(),
                        current_user_id=u_in, current_user_name=str(u_inf.get("USER", u_in)).strip(),
                        current_user_image_url=str(u_inf.get("USER_IMAGE", "")).strip(),
                        user_confirmed=True, warning_message=None,
                        pending_confirmation=None, last_action_details=None # Reseta estados de ação ao trocar de user.
                    )
                else:
                    st.session_state.update(user_confirmed=False, warning_message=f"⚠️ Usuário '{u_in}' não encontrado.")
            else:
                st.session_state.update(warning_message="⚠️ ID/Nome do usuário vazio.", user_confirmed=False)
    
    # Exibe as informações do usuário logado ou mensagens de erro/aviso.
    with col_user_status_display:
        if st.session_state.user_confirmed and st.session_state.current_user_name != "Usuário":
            un, ui = html.escape(st.session_state.current_user_name), html.escape(st.session_state.get("current_user_ps_id_internal", ""))
            uim = st.session_state.get('current_user_image_url', "")
            image_html = f'<img src="{html.escape(uim, True)}" style="width:50px;height:50px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:10px;">' if uim and uim.startswith("http") else "<div style='width:50px;height:50px;border-radius:50%;background-color:#333;margin-right:10px;display:inline-block;vertical-align:middle;'></div>"
            st.markdown(f'<div style="display:flex;align-items:center;height:50px;">{image_html}<div><span style="font-weight:bold;">{un}</span><br><span style="font-size:0.9em;color:#ccc;">PS: {ui}</span></div></div>', unsafe_allow_html=True)
        elif st.session_state.get('warning_message'):
            st.warning(st.session_state.warning_message, icon="🚨")

    # Se o usuário altera o ID no campo, ele precisa confirmar novamente.
    if st.session_state.user_confirmed and st.session_state.current_user_id.strip().upper() != st.session_state.user_id_input.strip().upper() and st.session_state.user_id_input.strip() != "":
        st.session_state.update(user_confirmed=False, warning_message="⚠️ ID/Nome alterado. Confirme novamente.", pending_confirmation=None, last_action_details=None); st.rerun()

# --- Conteúdo Principal do Aplicativo (visível apenas para usuários autenticados) ---
if st.session_state.user_confirmed and st.session_state.current_user_name != "Usuário":
    st.markdown("---")
    with st.spinner("Carregando configurações..."):
        tasks_raw, statuses_list_cfg = load_config_data()
    tasks_for_select = [NO_TASK_SELECTED_LABEL] + tasks_raw
    if not tasks_raw: st.error("Lista de tarefas não carregada.", icon="🚨"); st.stop()
    if not statuses_list_cfg: statuses_list_cfg = STATUS_PENDING_EQUIVALENTS + ["Requested", "Done"]

    # --- Controles Principais: Filtros, Atualizar e Desfazer ---
    cc1, cc2, cc3_refresh, cc3_undo = st.columns([0.35, 0.35, 0.15, 0.15])
    with cc1:
        st.session_state.selected_task = st.selectbox("Tipo de verificação:", tasks_for_select, index=tasks_for_select.index(st.session_state.selected_task) if st.session_state.selected_task in tasks_for_select else 0, key="tsel_w")
    with cc2:
        st.session_state.selected_statuses = st.multiselect("Filtrar Status:", statuses_list_cfg, default=st.session_state.selected_statuses or [], key="smul_w", disabled=(st.session_state.selected_task == NO_TASK_SELECTED_LABEL))
    with cc3_refresh:
        st.markdown("<br>", True)
        # O on_click limpa todos os caches, reseta confirmações pendentes e recarrega a página.
        if st.button("🔄 Atualizar", key="ref_b_w", help="Recarrega todos os dados das planilhas.", on_click=lambda: (load_athlete_data.clear(), load_users_data.clear(), load_config_data.clear(), load_attendance_data.clear(), st.toast("Dados atualizados!", icon="🔄"), setattr(st.session_state, 'pending_confirmation', None), st.rerun()), use_container_width=True):
            pass
    with cc3_undo:
        st.markdown("<br>", True)
        # O botão "Desfazer" só é habilitado se houver uma ação para desfazer.
        if st.session_state.last_action_details:
            if st.button("↩️ Desfazer", key="undo_b_w", help="Desfaz o último registro realizado.", use_container_width=True, type="secondary"):
                undo_last_log()
                st.rerun()
        else:
            st.button("↩️ Desfazer", key="undo_b_w_disabled", help="Nenhuma ação recente para desfazer.", use_container_width=True, disabled=True)

    st.session_state.show_personal_data = st.toggle("Mostrar Dados Pessoais", value=st.session_state.show_personal_data, key="tgl_pd_w")
    st.markdown("---")

    # Carregamento dos dados dos atletas e de registros.
    with st.spinner("Carregando atletas..."): df_athletes = load_athlete_data()
    with st.spinner("Carregando registros..."): df_attendance = load_attendance_data()
    sel_task_actual = st.session_state.selected_task if st.session_state.selected_task != NO_TASK_SELECTED_LABEL else None

    if df_athletes.empty:
        st.info("Nenhum atleta para exibir.")
    else:
        # Lógica para filtrar os atletas com base nos status selecionados.
        df_filtered = df_athletes.copy()
        if sel_task_actual and st.session_state.selected_statuses:
            show_ids = set()
            df_att_filt = df_attendance.copy()
            if ID_COLUMN_IN_ATTENDANCE in df_att_filt.columns:
                df_att_filt[ID_COLUMN_IN_ATTENDANCE] = df_att_filt[ID_COLUMN_IN_ATTENDANCE].astype(str)
            else:
                st.warning(f"A coluna '{ID_COLUMN_IN_ATTENDANCE}' não foi encontrada nos registros. O filtro pode não funcionar.", icon="⚠️")

            for _, ath_r in df_filtered.iterrows():
                ath_id_f = str(ath_r["ID"])
                rel_att = pd.DataFrame()
                if ID_COLUMN_IN_ATTENDANCE in df_att_filt.columns and "Task" in df_att_filt.columns:
                    rel_att = df_att_filt[(df_att_filt[ID_COLUMN_IN_ATTENDANCE] == ath_id_f) & (df_att_filt["Task"] == sel_task_actual)]
                if not rel_att.empty:
                    if "Status" in rel_att.columns and any(s in st.session_state.selected_statuses for s in rel_att["Status"].unique()): show_ids.add(ath_id_f)
                elif rel_att.empty and any(s in st.session_state.selected_statuses for s in STATUS_PENDING_EQUIVALENTS): show_ids.add(ath_id_f)
            df_filtered = df_filtered[df_filtered["ID"].astype(str).isin(list(show_ids))]
        
        st.markdown(f"Exibindo **{len(df_filtered)}** de **{len(df_athletes)}** atletas.")
        if not sel_task_actual: st.info("Selecione uma tarefa para ver as opções de registro e usar os filtros.", icon="ℹ️")

        # --- Loop para exibir cada Atleta em um Card ---
        for i_l, row in df_filtered.iterrows():
            ath_id_d, ath_name_d, ath_event_d = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])
            
            # Busca o status mais recente da tarefa selecionada para o atleta atual.
            task_stat_disp = "Status: Pendente / Não Registrado"; latest_rec_task = None;
            if sel_task_actual and ID_COLUMN_IN_ATTENDANCE in df_attendance.columns and "Task" in df_attendance.columns:
                df_att_chk=df_attendance.copy()
                df_att_chk[ID_COLUMN_IN_ATTENDANCE]=df_att_chk[ID_COLUMN_IN_ATTENDANCE].astype(str)
                ath_task_recs=df_att_chk[(df_att_chk[ID_COLUMN_IN_ATTENDANCE]==ath_id_d)&(df_att_chk["Task"]==sel_task_actual)]
                if not ath_task_recs.empty:
                    # Ordena por timestamp para garantir que estamos pegando o registro mais recente.
                    ath_task_recs['TS_dt'] = pd.to_datetime(ath_task_recs['Timestamp'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
                    latest_rec_task = ath_task_recs.sort_values(by="TS_dt", ascending=False).iloc[0]
                    task_stat_disp = f"Status ({sel_task_actual}): **{latest_rec_task.get('Status', 'N/A')}**"

            # Define a cor de fundo do card com base no status.
            card_bg_col = "#1e1e1e"
            curr_stat_color = latest_rec_task.get('Status') if latest_rec_task is not None else None
            if curr_stat_color == "Done": card_bg_col = "#143d14"  # Verde escuro
            elif curr_stat_color == "Requested": card_bg_col = "#B08D00"  # Amarelo escuro

            # Montagem do HTML para exibir os dados do atleta de forma organizada.
            # (O código HTML para o card permanece o mesmo)
            bt_d_h,bt_ex_h=str(row.get("BLOOD TEST","")),is_blood_test_expired(str(row.get("BLOOD TEST","")))
            bt_html=f"<tr style='color:{"red"if bt_ex_h else("#A0F0A0"if bt_d_h else"orange")};'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>{html.escape(bt_d_h)if bt_d_h else'Não Registrado'}{f' <span style="font-weight:bold;">(Expirado)</span>'if bt_ex_h and bt_d_h else''}</td></tr>"
            pd_tbl_h=f"""<div style='flex-basis:350px;flex-grow:1;'><table style='font-size:14px;color:white;border-collapse:collapse;width:100%;'><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row.get("NATIONALITY","")))}</td></tr>{bt_html}</table></div>"""if st.session_state.show_personal_data else"<div style='flex-basis:300px;flex-grow:1;font-style:italic;color:#ccc;font-size:13px;text-align:center;'>Dados pessoais ocultos.</div>"
            st.markdown(f"""<div style='background-color:{card_bg_col};padding:20px;border-radius:10px;margin-bottom:15px;box-shadow:2px 2px 5px rgba(0,0,0,0.3);'><div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px;'><div style='display:flex;align-items:center;gap:15px;flex-basis:300px;flex-grow:1;'><img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/80?text=No+Image")if pd.notna(row.get("IMAGE"))and row.get("IMAGE")else"https://via.placeholder.com/80?text=No+Image",True)}' style='width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid white;'><div><h4 style='margin:0;text-align:center;font-size:1.5em;'>{html.escape(ath_name_d)}</h4><p style='margin:0;font-size:14px;color:#cccccc;text-align:center;'>{html.escape(ath_event_d)}</p><p style='margin:0;font-size:13px;color:#cccccc;text-align:center;'>ID: {html.escape(ath_id_d)}</p><p style='margin:0;font-size:13px;color:#a0f0a0;text-align:center;'><i>{task_stat_disp}</i></p></div></div>{pd_tbl_h}</div></div>""",True)


            # --- Lógica de Confirmação e Ação ---
            action_key_base = f"{ath_id_d}_{sel_task_actual.replace(' ', '_')}_{i_l}" if sel_task_actual else ""

            if sel_task_actual:
                # Se uma confirmação está pendente PARA ESTE ATLETA/TAREFA, exibe os botões de confirmação.
                if st.session_state.pending_confirmation and st.session_state.pending_confirmation.get("action_key") == action_key_base:
                    confirm_details = st.session_state.pending_confirmation
                    st.warning(f"Tem certeza que deseja {confirm_details['message_verb']} '{sel_task_actual}' para {ath_name_d} como '{confirm_details['status_to_set']}'?", icon="❓")
                    
                    col_sim, col_nao = st.columns(2)
                    with col_sim:
                        # Se o usuário clicar em "Sim", a função de registro é chamada.
                        if st.button("✅ Sim, confirmar", key=f"confirm_yes_{action_key_base}", use_container_width=True, type="primary"):
                            uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
                            registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, confirm_details['status_to_set'], confirm_details['notes'], uid_l)
                            st.session_state.pending_confirmation = None # Limpa o estado de confirmação.
                            st.rerun()
                    with col_nao:
                        # Se clicar em "Cancelar", apenas limpa o estado e recarrega a UI.
                        if st.button("❌ Cancelar", key=f"confirm_no_{action_key_base}", use_container_width=True):
                            st.session_state.pending_confirmation = None
                            st.rerun()
                else:
                    # Se não houver confirmação pendente, exibe os botões de ação normais.
                    # A lógica para 'Walkout Music' é tratada separadamente mas segue o mesmo fluxo de confirmação.
                    if sel_task_actual != "Walkout Music": # Lógica para tarefas padrão
                        curr_ath_task_stat_btn = latest_rec_task.get('Status') if latest_rec_task is not None else None
                        
                        if curr_ath_task_stat_btn == "Requested":
                            # Se o status atual é "Requested", mostra opções para "Concluir" ou "Cancelar".
                            col_btn_act1, col_btn_act2 = st.columns(2)
                            with col_btn_act1:
                                if st.button(f"CONCLUIR '{sel_task_actual}' (Done)", key=f"mark_done_b_{action_key_base}", type="primary", use_container_width=True):
                                    # Ao clicar, NÃO registra. Apenas define o estado de confirmação pendente.
                                    st.session_state.pending_confirmation = {"action_key": action_key_base, "message_verb": "marcar", "status_to_set": "Done", "notes": ""}
                                    st.rerun()
                            with col_btn_act2:
                                if st.button(f"CANCELAR SOL. '{sel_task_actual}' (---)", key=f"mark_pending_b_{action_key_base}", type="secondary", use_container_width=True):
                                    st.session_state.pending_confirmation = {"action_key": action_key_base, "message_verb": "marcar", "status_to_set": "---", "notes": ""}
                                    st.rerun()
                        else:
                            # Se o status é "Pendente" ou "Done", mostra o botão para "Solicitar".
                            btn_lbl_task_btn = f"SOLICITAR '{sel_task_actual}'"
                            btn_type_task_btn = "primary"
                            if curr_ath_task_stat_btn == "Done":
                                btn_lbl_task_btn = f"'{sel_task_actual}' FEITO. Solicitar Novamente?"
                                btn_type_task_btn = "secondary"
                            
                            if st.button(btn_lbl_task_btn, key=f"mark_stat_b_{action_key_base}", type=btn_type_task_btn, use_container_width=True):
                                # Define o estado de confirmação pendente.
                                st.session_state.pending_confirmation = {"action_key": action_key_base, "message_verb": "marcar", "status_to_set": "Requested", "notes": ""}
                                st.rerun()

            st.markdown("<hr style='border-top:1px solid #333;margin-top:10px;margin-bottom:25px;'>", True)
else:
    # Mensagem para usuários que ainda não se autenticaram.
    if not st.session_state.user_confirmed and not st.session_state.get('warning_message'):
        st.warning("🚨 Por favor, confirme seu ID ou Nome de usuário para continuar.", icon="🚨")
