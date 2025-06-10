import streamlit as st
import pandas as pd
from streamlit_barcode_scanner import st_barcode_scanner # Importa a biblioteca do scanner

# --- Configuração da Página ---
st.set_page_config(page_title="Controle de Tarefas", layout="wide")

# --- Carregamento de Dados da Planilha ---
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"

@st.cache_data(ttl=300)
def load_fightcard_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['AthleteID', 'Fighter'])
        df['AthleteID'] = df['AthleteID'].astype(str) # Trata ID como texto para busca
        df['Fighter'] = df['Fighter'].str.strip()
        return df
    except Exception as e:
        st.error(f"Não foi possível carregar os dados. Verifique o link. Erro: {e}")
        return pd.DataFrame()

# --- Funções de Lógica e Estado (Agora por Tarefa) ---

def initialize_task_state(task_name, athletes_df):
    """Prepara o st.session_state para uma nova tarefa."""
    if 'tasks' not in st.session_state:
        st.session_state.tasks = {}
    
    st.session_state.tasks[task_name] = {
        "athletes": {},
        "next_checkin_number": 1
    }
    for _, athlete in athletes_df.iterrows():
        athlete_id = athlete['AthleteID']
        st.session_state.tasks[task_name]['athletes'][athlete_id] = {
            "name": athlete['Fighter'],
            "pic": athlete.get('Picture', 'https://via.placeholder.com/100?text=NA'),
            "status": "aguardando",
            "checkin_number": None
        }

def update_athlete_status(task_name, athlete_id, new_status):
    """Função central para mudar o status de um atleta para uma tarefa."""
    task_data = st.session_state.tasks[task_name]
    athlete_data = task_data['athletes'][athlete_id]
    
    if new_status == 'na fila' and athlete_data['status'] == 'aguardando':
        athlete_data['checkin_number'] = task_data['next_checkin_number']
        task_data['next_checkin_number'] += 1
    
    athlete_data['status'] = new_status


# --- Interface Principal do Aplicativo ---
st.title("Controle de Tarefas com Fila Dinâmica")

all_athletes_df = load_fightcard_data(FIGHTCARD_SHEET_URL)

if all_athletes_df.empty:
    st.stop()

# --- 1. Caixa de Texto para o Nome da Tarefa ---
st.subheader("1. Defina a Tarefa")
task_name_input = st.text_input(
    "Digite o nome da tarefa para criar ou acessar a fila:",
    placeholder="Ex: Photoshoot, Media Day, Pesagem...",
    help="Cada nome de tarefa cria uma fila de check-in separada."
).strip()

# A lógica principal só executa se um nome de tarefa for inserido
if task_name_input:
    # Inicializa o estado para a tarefa se for a primeira vez
    if 'tasks' not in st.session_state or task_name_input not in st.session_state.tasks:
        initialize_task_state(task_name_input, all_athletes_df)
    
    st.success(f"Fila ativa para a tarefa: **{task_name_input}**")
    st.divider()

    # --- 2. Ferramentas de Busca e Scanner ---
    st.subheader("2. Encontre o Atleta")
    col_search, col_scan = st.columns([2, 1])

    with col_search:
        # Caixa de texto para procurar por nome ou ID
        search_query = st.text_input(
            "Buscar por Nome ou ID:",
            key=f"search_{task_name_input}" # Chave única para o search box
        ).lower()

    with col_scan:
        st.write(" ") # Alinhamento vertical
        # Botão para ativar o scanner de código de barras
        scanned_code = st_barcode_scanner(key=f"scanner_{task_name_input}")
        if scanned_code:
            # Se um código for lido, atualiza a caixa de busca e recarrega
            st.session_state[f"search_{task_name_input}"] = scanned_code
            st.rerun()

    # Filtra o DataFrame de atletas baseado na busca
    if search_query:
        df_filtered = all_athletes_df[
            all_athletes_df['Fighter'].str.lower().str.contains(search_query) |
            all_athletes_df['AthleteID'].str.contains(search_query)
        ]
    else:
        df_filtered = all_athletes_df

    st.divider()

    # --- 3. Listas de Status (Aguardando, Fila, Finalizados) ---
    st.subheader("3. Gerencie a Fila")

    # Separa os atletas em listas
    waiting_list, checked_in_list, finished_list = [], [], []
    
    # Itera sobre os atletas FILTRADOS para popular as listas
    for _, athlete_row in df_filtered.iterrows():
        athlete_id = athlete_row['AthleteID']
        athlete_status_data = st.session_state.tasks[task_name_input]['athletes'].get(athlete_id)

        if not athlete_status_data: continue # Pula se o atleta não estiver no estado (raro)

        item = (athlete_id, athlete_status_data)
        if athlete_status_data['status'] == 'aguardando':
            waiting_list.append(item)
        elif athlete_status_data['status'] == 'na fila':
            checked_in_list.append(item)
        else: # finalizado
            finished_list.append(item)
    
    # Ordena a lista de check-in pelo número
    checked_in_list.sort(key=lambda item: item[1]['checkin_number'])
    
    # Se a busca estiver vazia, mostramos os totais de todos os atletas
    if not search_query:
        total_waiting = len([ath for ath in st.session_state.tasks[task_name_input]['athletes'].values() if ath['status'] == 'aguardando'])
        total_in_queue = len([ath for ath in st.session_state.tasks[task_name_input]['athletes'].values() if ath['status'] == 'na fila'])
        total_finished = len([ath for ath in st.session_state.tasks[task_name_input]['athletes'].values() if ath['status'] == 'finalizado'])
    else: # Se houver busca, os totais são apenas dos resultados filtrados
        total_waiting, total_in_queue, total_finished = len(waiting_list), len(checked_in_list), len(finished_list)


    col1, col2, col3 = st.columns(3)

    with col1:
        st.header(f"Aguardando ({total_waiting})")
        for athlete_id, athlete in waiting_list:
            st.button(f"➡️ {athlete['name']}", key=f"checkin_{task_name_input}_{athlete_id}",
                      on_click=update_athlete_status, args=(task_name_input, athlete_id, 'na fila'),
                      use_container_width=True, type="secondary")

    with col2:
        st.header(f"Na Fila ({total_in_queue})")
        for athlete_id, athlete in checked_in_list:
            st.button(f"🏁 #{athlete['checkin_number']} - {athlete['name']}", key=f"checkout_{task_name_input}_{athlete_id}",
                      on_click=update_athlete_status, args=(task_name_input, athlete_id, 'finalizado'),
                      use_container_width=True, type="primary")

    with col3:
        st.header(f"Finalizados ({total_finished})")
        for athlete_id, athlete in finished_list:
            st.success(f"✅ {athlete['name']}", icon="✅")

else:
    st.info("Digite um nome de tarefa para começar.")
