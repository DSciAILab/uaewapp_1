import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import html

# --- Funções de Carregamento de Dados (Dependências da página) ---

@st.cache_data(ttl=600)
def load_athlete_data():
    # ... (código da função load_athlete_data)
    pass

@st.cache_data(ttl=120)
def load_transfers_data():
    # ... (código da função load_transfers_data)
    pass

@st.cache_data(ttl=120)
def load_checkin_data():
    # ... (código da função load_checkin_data)
    pass

# --- Função de Salvamento de Dados (Dependência da página) ---

def save_checkin_record(data: dict):
    # ... (código da função save_checkin_record)
    pass


# --- Código da Página "Check-In de Atletas" ---

def page_checkin_atletas():
    st.header("Check-In e Atribuição de Atletas")
    
    # Carregar dados
    df_athletes = load_athlete_data()
    df_transfers = load_transfers_data()
    df_checkin = load_checkin_data()

    # Filtros
    c1, c2, c3 = st.columns([0.4, 0.4, 0.2])
    with c1: 
        event_list = ["Todos os Eventos"] + sorted([e for e in df_athletes["EVENT"].unique() if e and e != "Z"]) if not df_athletes.empty else []
        st.selectbox("Filtrar Evento:", options=event_list, key="selected_event")
    with c2: st.text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID do lutador...", key="fighter_search_query")
    with c3: st.markdown("<br>", True); st.button("🔄 Atualizar", on_click=lambda:(load_athlete_data.clear(), load_transfers_data.clear(), load_checkin_data.clear(), st.toast("Dados atualizados!")))

    # Filtrar atletas com base nos inputs do usuário
    df_filtered = df_athletes.copy()
    if st.session_state.selected_event != "Todos os Eventos": df_filtered = df_filtered[df_filtered["EVENT"] == st.session_state.selected_event]
    if st.session_state.fighter_search_query:
        term = st.session_state.fighter_search_query.strip().lower()
        df_filtered = df_filtered[df_filtered.apply(lambda r: term in str(r['NAME']).lower() or term in str(r['ID']), axis=1)]

    st.markdown(f"Exibindo **{len(df_filtered)}** atletas.")

    # Loop para exibir cada atleta e seus controles de check-in
    for i, row in df_filtered.iterrows():
        ath_id, ath_name, ath_event = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])
        
        # Card do Atleta
        st.markdown(f"""
        <div style='background-color:#1e1e1e;padding:15px;border-radius:10px;margin-bottom:10px;display:flex;align-items:center;gap:15px;'>
            <img src='{html.escape(row.get("IMAGE",""))}' style='width:60px;height:60px;border-radius:50%;object-fit:cover;'>
            <div><h5 style='margin:0;'>{html.escape(ath_name)}</h5><small style='color:#ccc;'>ID: {html.escape(ath_id)} | Evento: {html.escape(ath_event)}</small></div>
        </div>""", unsafe_allow_html=True)

        # Encontra o registro de check-in existente para este atleta/evento
        current_checkin = None
        if not df_checkin.empty:
            match = df_checkin[(df_checkin['athlete_id'].astype(str) == ath_id) & (df_checkin['event'] == ath_event)]
            if not match.empty:
                current_checkin = match.iloc[0]

        # Filtra os transfers pelo evento do atleta atual e prepara as opções do dropdown
        active_transfers_for_event = df_transfers[(df_transfers['status'] == 'Active') & (df_transfers['event'] == ath_event)] if not df_transfers.empty else pd.DataFrame()
        transfer_options = {
            row['transfer_record_id']: f"{row['bus_number']} | {row['dept_date']} {row['dept_time']} | {row['task']}" 
            for index, row in active_transfers_for_event.iterrows()
        }
        transfer_options_list = ["-- Nenhum --"] + list(transfer_options.values())

        # Widgets de Check-in e Atribuição em colunas
        cols = st.columns([1, 1, 1, 1, 2, 2])
        with cols[0]:
            st.checkbox("Passport", key=f"passport_{ath_id}", value=current_checkin is not None and current_checkin.get('passport') == 'TRUE')
            st.checkbox("Nails", key=f"nails_{ath_id}", value=current_checkin is not None and current_checkin.get('nails') == 'TRUE')
        with cols[1]:
            st.checkbox("Cups", key=f"cups_{ath_id}", value=current_checkin is not None and current_checkin.get('cups') == 'TRUE')
            st.checkbox("Uniform", key=f"uniform_{ath_id}", value=current_checkin is not None and current_checkin.get('uniform') == 'TRUE')
        with cols[2]:
            corners_val = int(current_checkin['corners']) if current_checkin is not None and str(current_checkin.get('corners')).isdigit() else 1
            st.selectbox("Corners", [1, 2, 3], key=f"corners_{ath_id}", index=corners_val - 1)
        with cols[3]:
            transfer_type_val = current_checkin['transfer_type'] if current_checkin is not None and current_checkin.get('transfer_type') else "Bus"
            st.selectbox("Transporte", ["Bus", "Own Transport"], key=f"transfer_type_{ath_id}", index=["Bus", "Own Transport"].index(transfer_type_val))
        with cols[4]:
            assigned_id_str = str(current_checkin['assigned_transfer_id']) if current_checkin is not None else None
            current_selection = next((desc for id, desc in transfer_options.items() if str(id) == assigned_id_str), "-- Nenhum --")
            st.selectbox("Atribuir Transfer", transfer_options_list, key=f"assigned_transfer_{ath_id}", index=transfer_options_list.index(current_selection))

        with cols[5]:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Salvar Status", key=f"save_{ath_id}", use_container_width=True):
                # Coleta os dados de todos os widgets para salvar
                selected_transfer_desc = st.session_state[f"assigned_transfer_{ath_id}"]
                assigned_transfer_id = [id for id, desc in transfer_options.items() if desc == selected_transfer_desc]
                
                checkin_data = {
                    'athlete_id': ath_id, 
                    'athlete_name': ath_name, 
                    'event': ath_event,
                    'assigned_transfer_id': assigned_transfer_id[0] if assigned_transfer_id else "",
                    'passport': st.session_state[f"passport_{ath_id}"], 
                    'nails': st.session_state[f"nails_{ath_id}"],
                    'cups': st.session_state[f"cups_{ath_id}"], 
                    'uniform': st.session_state[f"uniform_{ath_id}"],
                    'corners': st.session_state[f"corners_{ath_id}"], 
                    'transfer_type': st.session_state[f"transfer_type_{ath_id}"],
                    'updated_by': st.session_state.get('current_user_name', 'System'),
                    'updated_at': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                }
                save_checkin_record(checkin_data)

        st.markdown("<hr>", unsafe_allow_html=True)


# Para testar esta página isoladamente, você pode adicionar:
# if __name__ == "__main__":
#     # Você precisaria definir as funções de carregamento e salvamento aqui
#     # e também a conexão com o Google Sheets para um teste funcional.
#     page_checkin_atletas()
