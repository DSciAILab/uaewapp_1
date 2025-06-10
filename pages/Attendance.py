import streamlit as st
import pandas as pd

# --- Configuração da Página ---
st.set_page_config(page_title="Chamada de Atletas", layout="wide")

# --- Carregamento de Dados da Planilha ---
# URL pública do Google Sheet (formato CSV)
# IMPORTANTE: A sua planilha precisa estar com o compartilhamento "Qualquer pessoa com o link pode ver"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"

@st.cache_data(ttl=300) # Armazena os dados por 5 minutos
def load_fightcard_data(url):
    """Carrega os dados da planilha e os limpa para uso."""
    try:
        df = pd.read_csv(url)
        # Limpeza básica dos dados
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['AthleteID', 'Fighter', 'Event'])
        df['AthleteID'] = df['AthleteID'].astype(int)
        df['Fighter'] = df['Fighter'].str.strip()
        return df
    except Exception as e:
        st.error(f"Não foi possível carregar os dados da planilha. Verifique o link e as permissões. Erro: {e}")
        return pd.DataFrame()

# --- Funções de Lógica e Estado ---

def initialize_or_reset_state(athletes_df):
    """Prepara o st.session_state para um novo evento."""
    st.session_state.athletes = {}
    for _, athlete in athletes_df.iterrows():
        athlete_id = athlete['AthleteID']
        st.session_state.athletes[athlete_id] = {
            "name": athlete['Fighter'],
            "pic": athlete.get('Picture', 'https://via.placeholder.com/100?text=NA'),
            "status": "aguardando",  # Status inicial: aguardando, na fila, finalizado
            "checkin_number": None
        }
    st.session_state.next_checkin_number = 1

def check_in_athlete(athlete_id):
    """Muda o status do atleta para 'na fila' e atribui um número."""
    athlete = st.session_state.athletes[athlete_id]
    athlete['checkin_number'] = st.session_state.next_checkin_number
    athlete['status'] = 'na fila'
    st.session_state.next_checkin_number += 1

def check_out_athlete(athlete_id):
    """Muda o status do atleta para 'finalizado'."""
    st.session_state.athletes[athlete_id]['status'] = 'finalizado'

def cancel_check_in(athlete_id):
    """Retorna um atleta da fila para a lista de espera."""
    st.session_state.athletes[athlete_id]['status'] = 'aguardando'
    # O número de check-in é mantido nulo, ele pegará um novo número se fizer check-in de novo.
    st.session_state.athletes[athlete_id]['checkin_number'] = None


# --- Interface Principal do Aplicativo ---

st.title("Sistema de Chamada com Check-in e Check-out")

# Carrega todos os dados da planilha
all_athletes_df = load_fightcard_data(FIGHTCARD_SHEET_URL)

if all_athletes_df.empty:
    st.stop()

# Filtro de Seleção de Evento
events = sorted(all_athletes_df['Event'].unique().tolist())
selected_event = st.selectbox("1. Selecione o Evento para iniciar a chamada:", ["-- Nenhum --"] + events)

# A lógica principal só executa se um evento for selecionado
if selected_event != "-- Nenhum --":
    
    # Verifica se o evento mudou. Se sim, reinicia o estado.
    if 'current_event' not in st.session_state or st.session_state.current_event != selected_event:
        st.session_state.current_event = selected_event
        athletes_for_event = all_athletes_df[all_athletes_df['Event'] == selected_event]
        initialize_or_reset_state(athletes_for_event)
        st.rerun()

    st.success(f"Chamada iniciada para o evento: **{selected_event}**")
    st.markdown("Use os botões para mover os atletas entre as colunas.")

    # Botão para reiniciar a chamada do evento atual
    if st.button("🗑️ Reiniciar Chamada do Evento Atual"):
        athletes_for_event = all_athletes_df[all_athletes_df['Event'] == selected_event]
        initialize_or_reset_state(athletes_for_event)
        st.rerun()
    st.divider()

    # Separa os atletas em três listas baseadas no status
    waiting_list = []
    checked_in_list = []
    finished_list = []
    for athlete_id, athlete_data in st.session_state.athletes.items():
        if athlete_data['status'] == 'aguardando':
            waiting_list.append((athlete_id, athlete_data))
        elif athlete_data['status'] == 'na fila':
            checked_in_list.append((athlete_id, athlete_data))
        else: # finalizado
            finished_list.append((athlete_id, athlete_data))

    # Ordena a lista de check-in pelo número da chamada
    checked_in_list.sort(key=lambda item: item[1]['checkin_number'])

    # Cria três colunas para a interface
    col_waiting, col_checked_in, col_finished = st.columns(3)

    # Coluna 1: Aguardando Check-in
    with col_waiting:
        st.header(f"Aguardando ({len(waiting_list)})")
        for athlete_id, athlete in waiting_list:
            with st.container(border=True):
                c1, c2 = st.columns([1, 3])
                c1.image(athlete.get('pic', "https://via.placeholder.com/100?text=NA"), width=70)
                with c2:
                    st.subheader(athlete['name'])
                    st.button(
                        "➡️ Check-in", key=f"checkin_{athlete_id}",
                        on_click=check_in_athlete, args=(athlete_id,),
                        use_container_width=True, type="primary"
                    )

    # Coluna 2: Na Fila
    with col_checked_in:
        st.header(f"Na Fila ({len(checked_in_list)})")
        if not checked_in_list:
            st.info("Nenhum atleta na fila.")
        for athlete_id, athlete in checked_in_list:
            with st.container(border=True, height=140):
                c1, c2, c3 = st.columns([1, 2, 2])
                c1.markdown(f"<h1 style='text-align: center; color: #17a2b8;'>{athlete['checkin_number']}</h1>", unsafe_allow_html=True)
                with c2:
                    st.subheader(athlete['name'])
                    st.image(athlete.get('pic', "https://via.placeholder.com/100?text=NA"), width=70)
                with c3:
                    st.button(
                        "🏁 Check-out", key=f"checkout_{athlete_id}",
                        on_click=check_out_athlete, args=(athlete_id,),
                        use_container_width=True, type="primary"
                    )
                    st.button(
                        "↩️ Cancelar", key=f"cancel_{athlete_id}",
                        on_click=cancel_check_in, args=(athlete_id,),
                        use_container_width=True, help="Retorna o atleta para a lista de espera"
                    )

    # Coluna 3: Finalizados
    with col_finished:
        st.header(f"Finalizados ({len(finished_list)})")
        for athlete_id, athlete in finished_list:
            with st.container(border=True):
                 st.markdown(f"✅ ~~{athlete['name']}~~", unsafe_allow_html=True)

else:
    st.info("Selecione um evento para começar.")
