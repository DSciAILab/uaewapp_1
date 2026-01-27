from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import get_gspread_client, connect_gsheet_tab, load_config_data
from task_logic import (
    BaseConfig, 
    load_athlete_data, 
    load_attendance_data,
    preprocess_attendance,
    get_all_athletes_status,
    clean_and_normalize
)

# --- Inicializa a página ---
bootstrap_page("Batch Operations")

st.title("🔄 Batch Operations")
st.markdown("Selecione múltiplos atletas e aplique alterações de status em lote.")

cfg = BaseConfig()

# --- Carrega dados ---
with st.spinner("Carregando dados..."):
    df_athletes = load_athlete_data(cfg.MAIN_SHEET_NAME, cfg.ATHLETES_TAB_NAME, cfg)
    df_attendance_raw = load_attendance_data(cfg.MAIN_SHEET_NAME, cfg.ATTENDANCE_TAB_NAME, cfg)
    tasks_list, statuses_list = load_config_data()

if df_athletes.empty:
    st.warning("Nenhum atleta encontrado.", icon="⚠️")
    st.stop()

# Preprocessa attendance
df_attendance = preprocess_attendance(df_attendance_raw, cfg)

# --- Seleção de Tarefa ---
st.subheader("1️⃣ Selecione a Tarefa")
if not tasks_list:
    st.error("Nenhuma tarefa configurada. Verifique a aba 'Config' na planilha.", icon="🚨")
    st.stop()

# Use segmented control for tasks (User Request: "segmented com todas as tarefas")
# Fallback to selectbox if too many tasks, but user requested segmented.
selected_task = st.segmented_control(
    "Tarefa:",
    options=tasks_list,
    default=tasks_list[0] if tasks_list else None,
    help="Escolha a tarefa que deseja atualizar em lote",
    key="batch_task_selector"
)

if not selected_task:
    st.info("Selecione uma tarefa acima para começar.")
    st.stop()


# --- Calcula status atual para a tarefa selecionada ---
# (Mantém lógica de cálculo)
athletes_status = get_all_athletes_status(
    df_athletes, 
    df_attendance, 
    selected_task, 
    [], 
    cfg
)

df_athletes = pd.merge(
    df_athletes, 
    athletes_status, 
    on=[cfg.COL_NAME, cfg.COL_EVENT], 
    how='left'
)

df_athletes.fillna({
    'current_task_status': cfg.STATUS_PENDING,
    'latest_task_user': 'N/A',
    'latest_task_timestamp': 'N/A'
}, inplace=True)

# --- Filtros ---
st.subheader("2️⃣ Filtros")
col1, col2, col3 = st.columns(3)

with col1:
    # Filtro por evento
    event_options = ["All Events"] + sorted([
        evt for evt in df_athletes[cfg.COL_EVENT].unique() 
        if evt != cfg.DEFAULT_EVENT_PLACEHOLDER
    ])
    selected_event = st.selectbox("Evento:", options=event_options)

with col2:
    # Filtro por status (User Request: "segmented de todas as opcoes" - assumindo filtro aqui também, ou na ação)
    # Vamos manter selectbox aqui por espaço, e usar segmented na AÇÃO (novo status)
    STATUS_FILTER_LABELS = {
        "All": "Todos",
        cfg.STATUS_PENDING: "Pending",
        cfg.STATUS_REQUESTED: "Requested",
        cfg.STATUS_DONE: "Done",
        cfg.STATUS_NOT_REQUESTED: "Not Requested (---)"
    }
    selected_status_filter = st.selectbox(
        "Status Atual:",
        options=["All", cfg.STATUS_PENDING, cfg.STATUS_REQUESTED, cfg.STATUS_DONE, cfg.STATUS_NOT_REQUESTED],
        format_func=lambda x: STATUS_FILTER_LABELS.get(x, x)
    )

with col3:
    # Busca por nome
    search_query = st.text_input("Buscar Atleta:", placeholder="Nome ou ID...")

# Aplica filtros
df_filtered = df_athletes.copy()

if selected_event != "All Events":
    df_filtered = df_filtered[df_filtered[cfg.COL_EVENT] == selected_event]

if selected_status_filter != "All":
    df_filtered = df_filtered[df_filtered['current_task_status'] == selected_status_filter]

search_term = search_query.strip().lower()
if search_term:
    df_filtered = df_filtered[
        df_filtered[cfg.COL_NAME].str.lower().str.contains(search_term, na=False) |
        df_filtered[cfg.COL_ID].astype(str).str.contains(search_term, na=False)
    ]

# --- Seleção de Atletas ---
st.subheader("3️⃣ Selecione Atletas")

if df_filtered.empty:
    st.info("Nenhum atleta encontrado com os filtros aplicados.", icon="ℹ️")
    st.stop()

st.markdown(f"**{len(df_filtered)} atletas encontrados**")

# --- Botões de Seleção em Lote ---
col_sel_btn1, col_sel_btn2, _ = st.columns([1, 1, 3])

# Estado para controle de seleção
if "batch_selection_key" not in st.session_state:
    st.session_state.batch_selection_key = 0
if "batch_select_all" not in st.session_state:
    st.session_state.batch_select_all = False

with col_sel_btn1:
    if st.button("✅ Selecionar Todos"):
        st.session_state.batch_select_all = True
        st.session_state.batch_selection_key += 1
        st.rerun()

with col_sel_btn2:
    if st.button("❌ Desmarcar Todos"):
        st.session_state.batch_select_all = False
        st.session_state.batch_selection_key += 1
        st.rerun()

# Tabela Interativa (st.data_editor)
# Prepara dataframe para editor
editor_df = df_filtered[[cfg.COL_ID, cfg.COL_NAME, cfg.COL_EVENT, cfg.COL_FIGHT_NUMBER, 'current_task_status']].copy()

# Define valor inicial baseado no botão clicado
editor_df.insert(0, "Selecionar", st.session_state.batch_select_all) 

# Key dinâmica força o reset do editor quando os botões são clicados
dynamic_key = f"batch_data_editor_{st.session_state.batch_selection_key}"

edited_df = st.data_editor(
    editor_df,
    column_config={
        "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False),
        cfg.COL_ID: st.column_config.TextColumn("ID", disabled=True),
        cfg.COL_NAME: st.column_config.TextColumn("Nome", disabled=True),
        cfg.COL_EVENT: st.column_config.TextColumn("Evento", disabled=True),
        cfg.COL_FIGHT_NUMBER: st.column_config.TextColumn("Luta", disabled=True),
        "current_task_status": st.column_config.TextColumn("Status Atual", disabled=True)
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    key=dynamic_key
)

# Identifica selecionados
selected_indices_in_editor = edited_df[edited_df["Selecionar"]].index
selected_real_indices = selected_indices_in_editor.tolist()
num_selected = len(selected_real_indices)

st.divider()

# --- Ação em Lote ---
st.subheader("4️⃣ Ação em Lote")

st.info(f"**{num_selected} atleta(s) selecionado(s)**", icon="📋")

if num_selected == 0:
    st.warning("Selecione pelo menos um atleta na tabela acima para aplicar ações.")
else:
    # AÇÃO: Novo Status com Segmented Control (User request: "segmented de todas as opcoes")
    col_action1, col_action2 = st.columns([2, 1])
    
    with col_action1:
        st.markdown("**Definir Novo Status:**")
        new_status = st.segmented_control(
            "Novo Status",
            options=[cfg.STATUS_REQUESTED, cfg.STATUS_DONE, cfg.STATUS_NOT_REQUESTED, cfg.STATUS_PENDING],
            format_func=lambda x: {
                cfg.STATUS_REQUESTED: "Requested",
                cfg.STATUS_DONE: "Done",
                cfg.STATUS_NOT_REQUESTED: "Not Requested (---)",
                cfg.STATUS_PENDING: "Clear (Pending)"
            }.get(x, x),
            label_visibility="collapsed",
            key="new_status_segmented"
        )
    
    with col_action2:
        notes = st.text_input("Notas (opcional):", placeholder="Obs para o log...")

    st.markdown("---")
    
    if st.button("✅ Atualizar Status em Lote", type="primary", use_container_width=True, disabled=(not new_status)):
        if not new_status:
            st.error("Selecione um status para aplicar.")
        else:
            try:
                # Prepara dados para gravação
                gspread_client = get_gspread_client()
                ws_attendance = connect_gsheet_tab(
                    gspread_client, 
                    cfg.MAIN_SHEET_NAME, 
                    cfg.ATTENDANCE_TAB_NAME
                )
                
                # Pega o próximo ID disponível
                all_values = ws_attendance.get_all_values()
                next_id = 1
                if all_values and len(all_values) > 1:
                    # Lógica simples de ID incremental baseada na contagem de linhas
                    next_id = len(all_values)

                # Prepara linhas para inserção
                rows_to_insert = []
                timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                user_name = st.session_state.get('current_user_name', 'Unknown')
                
                for idx in selected_real_indices:
                    athlete_row = df_filtered.loc[idx]
                    
                    # Status logic: "Pending" geralmente significa limpar o registro, mas na planilha append-only,
                    # enviamos "" ou o status explícito.
                    status_to_write = "" if new_status == cfg.STATUS_PENDING else new_status
                    
                    new_row = [
                        str(next_id),
                        str(athlete_row[cfg.COL_EVENT]),
                        str(athlete_row[cfg.COL_ID]),     # Athlete ID
                        str(athlete_row[cfg.COL_NAME]),   # Fighter
                        selected_task,                    # Task
                        status_to_write,                  # Status
                        user_name,                        # User
                        timestamp,                        # TimeStamp (ALT)
                        notes or "Batch Update"           # Notes
                    ]
                    rows_to_insert.append(new_row)
                    next_id += 1
                
                # Insere em lote
                if rows_to_insert:
                    body = {"values": rows_to_insert}
                    ws_attendance.spreadsheet.values_append(
                        f"{ws_attendance.title}!A:Z",
                        params={
                            "valueInputOption": "USER_ENTERED",
                            "insertDataOption": "INSERT_ROWS"
                        },
                        body=body
                    )
                    
                    st.success(
                        f"✅ {len(rows_to_insert)} registro(s) atualizado(s) com sucesso!",
                        icon="🎉"
                    )
                    
                    # Limpa cache para forçar reload
                    load_attendance_data.clear()
                    preprocess_attendance.clear()
                    load_athlete_data.clear()
                    
                    time.sleep(3)
                    st.rerun()
                
            except Exception as e:
                st.error(f"Erro ao aplicar alterações em lote: {e}", icon="🚨")

