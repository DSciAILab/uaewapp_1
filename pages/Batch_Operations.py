from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
from datetime import datetime
from utils import get_gspread_client, connect_gsheet_tab, load_config_data
from task_app import (
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

selected_task = st.selectbox(
    "Tarefa:",
    options=tasks_list,
    help="Escolha a tarefa que deseja atualizar em lote"
)

# --- Calcula status atual para a tarefa selecionada ---
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
    # Filtro por status
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

# Checkbox para selecionar todos
select_all = st.checkbox("Selecionar todos os atletas filtrados", key="select_all_batch")

# Cria dataframe para exibição
display_df = df_filtered[[
    cfg.COL_ID, 
    cfg.COL_NAME, 
    cfg.COL_EVENT, 
    cfg.COL_FIGHT_NUMBER,
    'current_task_status'
]].copy()

display_df.columns = ['ID', 'Nome', 'Evento', 'Luta', 'Status Atual']

# Adiciona coluna de seleção
if 'selected_athletes' not in st.session_state:
    st.session_state['selected_athletes'] = set()

# Se "selecionar todos" foi marcado
if select_all:
    st.session_state['selected_athletes'] = set(df_filtered.index.tolist())
else:
    # Remove atletas que não estão mais no filtro
    st.session_state['selected_athletes'] = st.session_state['selected_athletes'].intersection(
        set(df_filtered.index.tolist())
    )

# Exibe tabela com checkboxes
selected_indices = []
for idx, row in df_filtered.iterrows():
    col_check, col_info = st.columns([0.5, 9.5])
    
    with col_check:
        is_selected = st.checkbox(
            "✓",
            value=idx in st.session_state['selected_athletes'],
            key=f"athlete_check_{idx}",
            label_visibility="collapsed"
        )
        if is_selected:
            st.session_state['selected_athletes'].add(idx)
            selected_indices.append(idx)
        elif idx in st.session_state['selected_athletes']:
            st.session_state['selected_athletes'].remove(idx)
    
    with col_info:
        status_color = cfg.STATUS_COLOR_MAP.get(
            row['current_task_status'], 
            cfg.STATUS_COLOR_MAP[cfg.STATUS_PENDING]
        )
        st.markdown(
            f"""<div style="background-color: {status_color}; padding: 10px; border-radius: 5px; margin-bottom: 5px;">
                <b>{row[cfg.COL_NAME]}</b> (ID: {row[cfg.COL_ID]}) | 
                Evento: {row[cfg.COL_EVENT]} | 
                Luta: {row[cfg.COL_FIGHT_NUMBER] or 'N/A'} | 
                Status: <b>{row['current_task_status'] or 'Pending'}</b>
            </div>""",
            unsafe_allow_html=True
        )

st.divider()

# --- Ação em Lote ---
st.subheader("4️⃣ Ação em Lote")

num_selected = len(st.session_state['selected_athletes'])
st.info(f"**{num_selected} atleta(s) selecionado(s)**", icon="📋")

if num_selected == 0:
    st.warning("Selecione pelo menos um atleta para aplicar ações em lote.", icon="⚠️")
    st.stop()

# Seleção do novo status
col_action1, col_action2 = st.columns(2)

with col_action1:
    new_status = st.selectbox(
        "Novo Status:",
        options=[cfg.STATUS_REQUESTED, cfg.STATUS_DONE, cfg.STATUS_NOT_REQUESTED],
        format_func=lambda x: {
            cfg.STATUS_REQUESTED: "Requested",
            cfg.STATUS_DONE: "Done",
            cfg.STATUS_NOT_REQUESTED: "Not Requested (---)"
        }.get(x, x)
    )

with col_action2:
    notes = st.text_input("Notas (opcional):", placeholder="Adicione observações...")

# Botão de aplicar
st.markdown("---")

col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("✅ Aplicar Alterações em Lote", type="primary", use_container_width=True):
        try:
            # Prepara dados para gravação
            gspread_client = get_gspread_client()
            ws_attendance = connect_gsheet_tab(
                gspread_client, 
                cfg.MAIN_SHEET_NAME, 
                cfg.ATTENDANCE_TAB_NAME
            )
            
            # Pega o próximo ID disponível com get_all_values
            all_values = ws_attendance.get_all_values()
            next_id = 1
            if all_values and len(all_values) > 1:
                # Assume que a coluna ID está no índice correto ou busca pelo nome
                headers = all_values[0]
                try:
                    id_idx = headers.index(cfg.ATT_COL_ID)
                    existing_ids = [
                        int(str(row[id_idx])) 
                        for row in all_values[1:] 
                        if len(row) > id_idx and str(row[id_idx]).isdigit()
                    ]
                    next_id = max(existing_ids, default=0) + 1
                except ValueError:
                    # Se não achar a coluna ID, tenta usar a coluna 0 ou 4 como fallback baseado na estrutura conhecida
                    # Fallback seguro: pega o maior número na coluna 0 (geralmente #) ou 4 (Athlete ID)
                    # Mas ATT_COL_ID geralmente é "Athlete ID". 
                    pass
            
            # Prepara linhas para inserção
            rows_to_insert = []
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            user_name = st.session_state.get('current_user_name', 'Unknown')
            
            for idx in st.session_state['selected_athletes']:
                athlete_row = df_filtered.loc[idx]
                
                new_row = [
                    str(next_id),
                    str(athlete_row[cfg.COL_EVENT]),
                    str(athlete_row[cfg.COL_NAME]),
                    str(athlete_row[cfg.COL_NAME]),  # Fighter
                    str(athlete_row[cfg.COL_ID]),
                    selected_task,
                    new_status,
                    user_name,
                    "",  # Timestamp (vazio)
                    timestamp,  # TimeStamp
                    notes or "Batch Update"
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
                    f"✅ {len(rows_to_insert)} registro(s) adicionado(s) com sucesso! "
                    f"Tarefa '{selected_task}' marcada como '{new_status}'.",
                    icon="🎉"
                )
                
                # Limpa seleção
                st.session_state['selected_athletes'] = set()
                
                # Limpa cache para forçar reload
                load_attendance_data.clear()
                preprocess_attendance.clear()
                
                st.rerun()
            
        except Exception as e:
            st.error(f"Erro ao aplicar alterações em lote: {e}", icon="🚨")

with col_btn2:
    if st.button("🗑️ Limpar Seleção", use_container_width=True):
        st.session_state['selected_athletes'] = set()
        st.rerun()
