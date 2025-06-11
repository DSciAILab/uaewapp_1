import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Controle de Tarefas", layout="wide")

# --- Inicialização do Session State ---
# ### [MODIFICADO] ### Adiciona 'photo_size' ao estado da sessão.
if 'name_font_size' not in st.session_state: st.session_state.name_font_size = 18
if 'number_font_size' not in st.session_state: st.session_state.number_font_size = 48
if 'photo_size' not in st.session_state: st.session_state.photo_size = 60 # Tamanho padrão da foto
if 'task_locked' not in st.session_state: st.session_state.task_locked = False
if 'task_name_input' not in st.session_state: st.session_state.task_name_input = ""


# --- Controles da Sidebar ---
with st.sidebar:
    st.header("Controles de Exibição")
    st.session_state.name_font_size = st.slider("Tamanho do Nome (px)", 12, 32, st.session_state.name_font_size)
    st.session_state.number_font_size = st.slider("Tamanho do Número (px)", 24, 96, st.session_state.number_font_size)
    # ### [MODIFICADO] ### Adiciona o slider para controlar o tamanho da foto.
    st.session_state.photo_size = st.slider("Tamanho da Foto (px)", 40, 120, st.session_state.photo_size)


# --- CSS Dinâmico ---
# ### [MODIFICADO] ### O CSS agora usa o valor de 'photo_size' para as imagens.
st.markdown(f"""
<style>
    div[data-testid="stToolbar"], #MainMenu, header {{ visibility: hidden; }}
    .athlete-photo {{
        width: {st.session_state.photo_size}px;
        height: {st.session_state.photo_size}px;
        border-radius: 50%;
        object-fit: cover;
        border: 2px solid #4F4F4F;
    }}
    .finished-photo {{
        width: {int(st.session_state.photo_size * 0.7)}px; /* Foto finalizada um pouco menor */
        height: {int(st.session_state.photo_size * 0.7)}px;
        border-radius: 50%;
        object-fit: cover;
        filter: grayscale(100%);
        opacity: 0.6;
    }}
    .athlete-name {{ font-size: {st.session_state.name_font_size}px !important; font-weight: bold; line-height: 1.2; }}
    .call-number {{ font-size: {st.session_state.number_font_size}px !important; font-weight: bold; text-align: center; color: #17a2b8; }}
</style>
""", unsafe_allow_html=True)


# --- Carregamento de Dados ---
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
@st.cache_data(ttl=300)
def load_fightcard_data(url):
    try:
        df = pd.read_csv(url); df.columns = df.columns.str.strip(); df = df.dropna(subset=['AthleteID', 'Fighter'])
        df['AthleteID'] = df['AthleteID'].astype(str); df['Fighter'] = df['Fighter'].str.strip()
        return df
    except Exception as e: st.error(f"Erro ao carregar dados: {e}"); return pd.DataFrame()

# --- Funções de Lógica ---
def initialize_task_state(task_name, athletes_df):
    if 'tasks' not in st.session_state: st.session_state.tasks = {}
    st.session_state.tasks[task_name] = {"athletes": {}, "next_checkin_number": 1}
    for _, athlete in athletes_df.iterrows():
        st.session_state.tasks[task_name]['athletes'][athlete['AthleteID']] = {
            "name": athlete['Fighter'], "pic": athlete.get('Picture', 'https://via.placeholder.com/100?text=NA'),
            "status": "aguardando", "checkin_number": None
        }

def update_athlete_status(task_name, athlete_id, new_status):
    task_data = st.session_state.tasks[task_name]; athlete_data = task_data['athletes'][athlete_id]
    if new_status == 'na fila' and athlete_data['status'] == 'aguardando':
        athlete_data['checkin_number'] = task_data['next_checkin_number']; task_data['next_checkin_number'] += 1
    athlete_data['status'] = new_status

def unlock_task():
    st.session_state.task_locked = False; st.session_state.task_name_input = ""

# --- Interface Principal ---
col_title, col_clock = st.columns([3, 1])
with col_title: st.title("Controle de Tarefas com Fila Dinâmica")
with col_clock: clock_placeholder = st.empty()
st_autorefresh(interval=1000, key="clock_refresh")
clock_placeholder.markdown(f"<h3 style='text-align: right; color: #A0A0A0;'>{datetime.now().strftime('%H:%M:%S')}</h3>", unsafe_allow_html=True)

all_athletes_df = load_fightcard_data(FIGHTCARD_SHEET_URL)
if all_athletes_df.empty: st.stop()

if not st.session_state.task_locked:
    st.subheader("1. Defina a Tarefa")
    temp_task_name = st.text_input("Digite o nome da tarefa para criar ou acessar a fila:", placeholder="Ex: Photoshoot, Media Day, Pesagem...", key="temp_input")
    if st.button("Iniciar Fila para esta Tarefa"):
        if temp_task_name:
            st.session_state.task_name_input = temp_task_name
            st.session_state.task_locked = True
            st.rerun()
        else:
            st.warning("Por favor, digite um nome para a tarefa.")
else:
    col_task_info, col_task_button = st.columns([4, 1])
    with col_task_info: st.success(f"Fila ativa para a tarefa: **{st.session_state.task_name_input}**")
    with col_task_button: st.button("Mudar Tarefa", on_click=unlock_task, use_container_width=True)

if st.session_state.task_locked and st.session_state.task_name_input:
    task_name = st.session_state.task_name_input
    if task_name not in st.session_state.get('tasks', {}): initialize_task_state(task_name, all_athletes_df)
    
    st.divider()
    st.subheader("2. Encontre o Atleta")
    search_query = st.text_input("Buscar por Nome ou ID:", key=f"search_{task_name}").lower()
    df_filtered = all_athletes_df[all_athletes_df['Fighter'].str.lower().str.contains(search_query) | all_athletes_df['AthleteID'].str.contains(search_query)] if search_query else all_athletes_df

    st.divider()
    st.subheader("3. Gerencie a Fila")

    waiting_list, checked_in_list, finished_list = [], [], []
    for _, row in df_filtered.iterrows():
        athlete_id = row['AthleteID']
        status_data = st.session_state.tasks[task_name]['athletes'].get(athlete_id)
        if not status_data: continue
        item = (athlete_id, status_data)
        if status_data['status'] == 'aguardando': waiting_list.append(item)
        elif status_data['status'] == 'na fila': checked_in_list.append(item)
        else: finished_list.append(item)
    
    checked_in_list.sort(key=lambda item: item[1]['checkin_number'])
    
    if not search_query:
        totals = {s: len([a for a in st.session_state.tasks[task_name]['athletes'].values() if a['status'] == s]) for s in ['aguardando', 'na fila', 'finalizado']}
    else:
        totals = {'aguardando': len(waiting_list), 'na fila': len(checked_in_list), 'finalizado': len(finished_list)}

    col1, col2, col3 = st.columns(3)

    with col1:
        st.header(f"Aguardando ({totals['aguardando']})")
        for athlete_id, athlete in waiting_list:
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 3])
                with pic_col: st.markdown(f'<img class="athlete-photo" src="{athlete["pic"]}">', unsafe_allow_html=True)
                with name_col:
                    st.markdown(f"<p class='athlete-name'>{athlete['name']}</p>", unsafe_allow_html=True)
                    st.button("➡️ Check-in", key=f"checkin_{task_name}_{athlete_id}", on_click=update_athlete_status, args=(task_name, athlete_id, 'na fila'), use_container_width=True, type="secondary")

    with col2:
        st.header(f"Na Fila ({totals['na fila']})")
        for index, (athlete_id, athlete) in enumerate(checked_in_list):
            is_next = index == 0
            container_border_color = "#00BFFF" if is_next else "#808495"
            with st.container(border=True):
                num_col, pic_col, name_col = st.columns([1, 1, 2])
                with num_col: st.markdown(f"<p class='call-number' style='color:{container_border_color};'>{athlete['checkin_number']}</p>", unsafe_allow_html=True)
                with pic_col: st.markdown(f'<img class="athlete-photo" style="border-color:{container_border_color};" src="{athlete["pic"]}">', unsafe_allow_html=True)
                with name_col:
                    st.markdown(f"<p class='athlete-name'>{athlete['name']}</p>", unsafe_allow_html=True)
                    if is_next: st.markdown("⭐ **PRÓXIMO!**")
                    st.button("🏁 Check-out", key=f"checkout_{task_name}_{athlete_id}", on_click=update_athlete_status, args=(task_name, athlete_id, 'finalizado'), use_container_width=True, type="primary")

    with col3:
        st.header(f"Finalizados ({totals['finalizado']})")
        for athlete_id, athlete in finished_list:
             with st.container(border=True):
                pic_col, name_col = st.columns([1, 4])
                with pic_col: st.markdown(f'<img class="finished-photo" src="{athlete["pic"]}">', unsafe_allow_html=True)
                with name_col: st.markdown(f"<p class='athlete-name' style='text-decoration: line-through; color: #808495;'>{athlete['name']}</p>", unsafe_allow_html=True)

elif not st.session_state.task_locked:
    st.info("Digite um nome de tarefa e clique em 'Iniciar Fila' para começar.")
