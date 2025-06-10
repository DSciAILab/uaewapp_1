import streamlit as st

# --- Configuração da Página ---
st.set_page_config(page_title="Chamada de Atletas", layout="wide")

# --- Banco de Dados Falso (Substitua pelos seus atletas se quiser) ---
# Para simplificar, estamos definindo os atletas diretamente no código.
# Cada atleta precisa de um 'id' único.
ATHLETES_DATA = [
    {"id": 101, "name": "Bruno 'Caveira' Machado", "pic": "https://i.pravatar.cc/150?img=1"},
    {"id": 102, "name": "Juliana 'Fênix' Silva", "pic": "https://i.pravatar.cc/150?img=2"},
    {"id": 103, "name": "Carlos 'Trovão' Andrade", "pic": "https://i.pravatar.cc/150?img=3"},
    {"id": 104, "name": "Fernanda 'Pantera' Costa", "pic": "https://i.pravatar.cc/150?img=4"},
    {"id": 105, "name": "Ricardo 'Ice' Borges", "pic": "https://i.pravatar.cc/150?img=5"},
    {"id": 106, "name": "Leticia 'Víbora' Martins", "pic": "https://i.pravatar.cc/150?img=6"},
    {"id": 107, "name": "Vitor 'Demolidor' Almeida", "pic": "https://i.pravatar.cc/150?img=7"},
]

# --- Funções de Lógica ---

def initialize_state():
    """
    Prepara o st.session_state na primeira vez que o app é executado.
    Cria um dicionário de atletas e um contador para o número da chamada.
    """
    if 'athletes' not in st.session_state:
        st.session_state.athletes = {}
        # Popula o estado com os dados iniciais dos atletas
        for athlete in ATHLETES_DATA:
            st.session_state.athletes[athlete['id']] = {
                "name": athlete['name'],
                "pic": athlete['pic'],
                "status": "aguardando",  # Status inicial
                "checkin_number": None  # Nenhum número de chamada ainda
            }
        # Inicializa o contador do próximo número de chamada
        st.session_state.next_checkin_number = 1

def check_in_athlete(athlete_id):
    """
    Função chamada quando o botão de check-in é clicado.
    Muda o status do atleta, atribui o número de chamada e incrementa o contador.
    """
    athlete = st.session_state.athletes[athlete_id]
    
    # Atribui o próximo número da fila ao atleta
    athlete['checkin_number'] = st.session_state.next_checkin_number
    # Muda o status para indicar que ele está na fila
    athlete['status'] = 'na fila'
    
    # Incrementa o contador para o próximo atleta
    st.session_state.next_checkin_number += 1

def cancel_check_in(athlete_id):
    """
    Função para desfazer um check-in, caso o usuário clique errado.
    """
    athlete = st.session_state.athletes[athlete_id]
    athlete['status'] = 'aguardando'
    athlete['checkin_number'] = None
    # Nota: Não diminuímos o 'next_checkin_number' para manter a sequência de chegada original.

# --- Interface Principal do Aplicativo ---

# Inicializa o estado (só executa na primeira vez)
initialize_state()

st.title("Sistema de Chamada Simples (Check-in)")
st.markdown("Clique em **'➡️ Check-in'** para adicionar um atleta à fila de atendimento com um número sequencial.")

# Botão para reiniciar a chamada e limpar a sessão
if st.button("🗑️ Reiniciar Chamada (Limpa a Fila)"):
    # Remove as chaves específicas do session_state para começar de novo
    del st.session_state.athletes
    del st.session_state.next_checkin_number
    st.rerun()

st.divider()

# Separa os atletas em duas listas: os que aguardam e os que já fizeram check-in
waiting_list = []
checked_in_list = []
for athlete_id, athlete_data in st.session_state.athletes.items():
    if athlete_data['status'] == 'aguardando':
        waiting_list.append((athlete_id, athlete_data))
    else:
        checked_in_list.append((athlete_id, athlete_data))

# Ordena a lista de check-in pelo número da chamada
checked_in_list.sort(key=lambda item: item[1]['checkin_number'])

# Cria duas colunas para a interface
col_waiting, col_checked_in = st.columns(2)

# Coluna da Esquerda: Atletas aguardando check-in
with col_waiting:
    st.header(f"Aguardando Check-in ({len(waiting_list)})")
    if not waiting_list:
        st.success("Todos os atletas já fizeram check-in!")
    
    for athlete_id, athlete in waiting_list:
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            c1.image(athlete['pic'], width=70)
            c2.subheader(athlete['name'])
            # O botão chama a função 'check_in_athlete' com o ID do atleta
            c2.button(
                "➡️ Check-in",
                key=f"checkin_{athlete_id}",
                on_click=check_in_athlete,
                args=(athlete_id,),
                use_container_width=True,
                type="primary"
            )

# Coluna da Direita: Atletas que já fizeram check-in
with col_checked_in:
    st.header(f"Atletas na Fila ({len(checked_in_list)})")
    if not checked_in_list:
        st.info("Nenhum atleta na fila ainda.")

    for athlete_id, athlete in checked_in_list:
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            # Exibe o número da chamada bem grande
            c1.markdown(f"<h1 style='text-align: center; color: #17a2b8;'>{athlete['checkin_number']}</h1>", unsafe_allow_html=True)
            with c2:
                st.subheader(athlete['name'])
                st.image(athlete['pic'], width=70)
            # Botão para cancelar, caso precise
            c3.button(
                "❌",
                key=f"cancel_{athlete_id}",
                on_click=cancel_check_in,
                args=(athlete_id,),
                help="Cancelar check-in e retornar para a lista de espera"
            )
