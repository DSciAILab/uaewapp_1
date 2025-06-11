import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Controle de Tarefas", layout="wide")

# --- CSS para Fotos Circulares ---
st.markdown("""
<style>
.athlete-photo {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid #4F4F4F;
}
.finished-photo {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    object-fit: cover;
    filter: grayscale(100%);
    opacity: 0.6;
}
</style>
""", unsafe_allow_html=True)


# --- Carregamento de Dados da Planilha ---
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"

@st.cache_data(ttl=300)
def load_fightcard_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['AthleteID', 'Fighter'])
        df['AthleteID'] = df['AthleteID'].astype(str)
        df['Fighter'] = df['Fighter'].str.strip()
        return df
    except Exception as e:
        st.error(f"Não foi possível carregar os dados. Verifique o link. Erro: {e}")
        return pd.DataFrame()

# --- Funções de Lógica e Estado ---
def initialize_task_state(task_name, athletes_df):
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
    task_data = st.session_state.tasks[task_name]
    athlete_data = task_data['athletes'][athlete_id]
    
    if new_status == 'na fila' and athlete_data['status'] == 'aguardando':
        athlete_data['checkin_number'] = task_data['next_checkin_number']
        task_data['next_checkin_number'] += 1
    
    athlete_data['status'] = new_status


# --- Interface Principal do Aplicativo ---

# --- 1. Header com Título e Relógio Dinâmico ---
col_title, col_clock = st.columns([3, 1])
with col_title:
    st.title("Controle de Tarefas com Fila Dinâmica")
with col_clock:
    clock_placeholder = st.empty()

# Força a página a recarregar a cada segundo
st_autorefresh(interval=1000, key="clock_refresh")
clock_placeholder.markdown(
    f"<h3 style='text-align: right; color: #A0A0A0;'>{datetime.now().strftime('%H:%M:%S')}</h3>",
    unsafe_allow_html=True
)


all_athletes_df = load_fightcard_data(FIGHTCARD_SHEET_URL)

if all_athletes_df.empty:
    st.stop()

# --- 2. Definição da Tarefa ---
st.subheader("1. Defina a Tarefa")
task_name_input = st.text_input(
    "Digite o nome da tarefa para criar ou acessar a fila:",
    placeholder="Ex: Photoshoot, Media Day, Pesagem...",
    help="Cada nome de tarefa cria uma fila de check-in separada."
).strip()

if task_name_input:
    if 'tasks' not in st.session_state or task_name_input not in st.session_state.tasks:
        initialize_task_state(task_name_input, all_athletes_df)
    
    st.success(f"Fila ativa para a tarefa: **{task_name_input}**")
    st.divider()

    # --- 3. Ferramenta de Busca ---
    st.subheader("2. Encontre o Atleta")
    search_query = st.text_input(
        "Buscar por Nome ou ID:",
        key=f"search_{task_name_input}"
    ).lower()

    if search_query:
        df_filtered = all_athletes_df[
            all_athletes_df['Fighter'].str.lower().str.contains(search_query) |
            all_athletes_df['AthleteID'].str.contains(search_query)
        ]
    else:
        df_filtered = all_athletes_df

    st.divider()

    # --- 4. Listas de Status ---
    st.subheader("3. Gerencie a Fila")

    waiting_list, checked_in_list, finished_list = [], [], []
    for _, athlete_row in df_filtered.iterrows():
        athlete_id = athlete_row['AthleteID']
        athlete_status_data = st.session_state.tasks[task_name_input]['athletes'].get(athlete_id)
        if not athlete_status_data: continue
        item = (athlete_id, athlete_status_data)
        if athlete_status_data['status'] == 'aguardando': waiting_list.append(item)
        elif athlete_status_data['status'] == 'na fila': checked_in_list.append(item)
        else: finished_list.append(item)
    
    checked_in_list.sort(key=lambda item: item[1]['checkin_number'])
    
    if not search_query:
        total_waiting = len([a for a in st.session_state.tasks[task_name_input]['athletes'].values() if a['status'] == 'aguardando'])
        total_in_queue = len([a for a in st.session_state.tasks[task_name_input]['athletes'].values() if a['status'] == 'na fila'])
        total_finished = len([a for a in st.session_state.tasks[task_name_input]['athletes'].values() if a['status'] == 'finalizado'])
    else:
        total_waiting, total_in_queue, total_finished = len(waiting_list), len(checked_in_list), len(finished_list)

    col1, col2, col3 = st.columns(3)

    # --- Coluna "Aguardando" ---
    with col1:
        st.header(f"Aguardando ({total_waiting})")
        for athlete_id, athlete in waiting_list:
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 3])
                with pic_col:
                    st.markdown(f'<img class="athlete-photo" src="{athlete["pic"]}">', unsafe_allow_html=True)
                with name_col:
                    st.write(f"**{athlete['name']}**")
                    st.button("➡️ Check-in", key=f"checkin_{task_name_input}_{athlete_id}",
                              on_click=update_athlete_status, args=(task_name_input, athlete_id, 'na fila'),
                              use_container_width=True, type="secondary")

    # --- Coluna "Na Fila" ---
    with col2:
        st.header(f"Na Fila ({total_in_queue})")
        for athlete_id, athlete in checked_in_list:
            with st.container(border=True):
                num_col, content_col = st.columns([1, 4])
                with num_col:
                    st.markdown(f"<h1 style='text-align: center;'>{athlete['checkin_number']}</h1>", unsafe_allow_html=True)
                with content_col:
                    pic_col, name_col = st.columns([1, 2])
                    with pic_col:
                         st.markdown(f'<img class="athlete-photo" src="{athlete["pic"]}">', unsafe_allow_html=True)
                    with name_col:
                        st.write(f"**{athlete['name']}**")
                        st.button("🏁 Check-out", key=f"checkout_{task_name_input}_{athlete_id}",
                                  on_click=update_athlete_status, args=(task_name_input, athlete_id, 'finalizado'),
                                  use_container_width=True, type="primary")

    # --- Coluna "Finalizados" ---
    with col3:
        st.header(f"Finalizados ({total_finished})")
        for athlete_id, athlete in finished_list:
             with st.container(border=True):
                pic_col, name_col = st.columns([1, 4])
                with pic_col:
                     st.markdown(f'<img class="finished-photo" src="{athlete["pic"]}">', unsafe_allow_html=True)
                with name_col:
                    st.write(f"~~{athlete['name']}~~")

else:
    st.info("Digite um nome de tarefa para começar.")
