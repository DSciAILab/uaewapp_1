# 🔹 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.1.61

### Novidades desta versão:
- Comentários linha a linha adicionados
- Filtro "Corner" agora só permite seleção entre "Red" e "Blue"
- Campo "Editar" agora usa `st.toggle` para destravar as caixas
- Corrigido erro ao editar colunas ausentes com try/except
- Informações de luta organizadas em tabelas lado a lado (Fight, Division, Opponent)
- Toggle ativa e bloqueia linha via coluna LockBy = "1724"
- Tarefas interativas com toggle: clique para alternar entre Required e Done
- Centralização dos textos das tabelas
"""

# 🔑 Importações necessárias
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 🔐 Conexão com Google Sheets (com validação e tratamento de erro)
@st.cache_resource
def connect_sheet():
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet_file = client.open("UAEW_App")

        if "App" not in [ws.title for ws in sheet_file.worksheets()]:
            st.error("A aba 'App' não existe no arquivo 'UAEW_App'.")
            return None

        return sheet_file.worksheet("App")
    except Exception as e:
        st.error(f"Erro ao conectar com Google Sheets: {e}")
        return None

# 🔄 Carrega dados da planilha e renomeia colunas duplicadas
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    if sheet is None:
        st.error("❌ Falha ao conectar à planilha.")
        st.stop()

    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        df["original_index"] = df.index
        if "CORNER" in df.columns:
            df.rename(columns={"CORNER": "Coach"}, inplace=True)
        return df, sheet
    except Exception as e:
        st.error(f"Erro ao carregar os dados da planilha: {e}")
        st.stop()

# 📂 Atualiza valores na planilha de forma individual
def salvar_valor(sheet, row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar valor em linha {row+2}, coluna {col_index+1}: {e}")

# ⚙️ Configuração inicial da página
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10000, key="autorefresh")

# 🎨 Estilo customizado em HTML e CSS
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.athlete-header { display: flex; justify-content: center; align-items: center; gap: 1rem; margin: 1rem 0; }
.avatar { border-radius: 50%; width: 65px; height: 65px; object-fit: cover; }
.name-tag { font-size: 1.8rem; font-weight: bold; }
.badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin: 3px; text-transform: uppercase; display: inline-block; cursor: pointer; text-align: center; }
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
table { width: 100%; margin: 5px 0; border-collapse: collapse; text-align: center; }
th, td { text-align: center; padding: 4px 8px; border: 1px solid #444; }
th { font-weight: bold; }
.section-label { font-weight: bold; margin-top: 1rem; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# 🔍 Carregando dados e planilha
df, sheet = load_data()

# 🛠️ Painel de Debug para verificar headers e conexão
def show_debug(sheet, df):
    with st.expander("🛠️ Debug Info"):
        st.markdown("### Verificação de Conexão com Google Sheets")
        if sheet:
            st.success("✅ Conectado com sucesso à aba 'App'")
            st.markdown(f"**Título da aba:** `{sheet.title}`")
            try:
                headers_raw = sheet.row_values(1)
                headers = [h.strip() for h in headers_raw]
                st.write("🔣 Cabeçalhos detectados:", headers)
            except Exception as e:
                st.error(f"❌ Erro ao ler cabeçalhos: {e}")
        else:
            st.error("❌ A aba 'App' não foi carregada. Verifique o nome da planilha ou permissões da conta.")
        st.markdown("### Prévia do DataFrame carregado")
        try:
            st.dataframe(df.head())
        except:
            st.warning("⚠️ DataFrame `df` não pôde ser carregado corretamente.")

show_debug(sheet, df)

# ✅ Headers protegidos
try:
    headers = [h.strip() for h in sheet.row_values(1)]
except Exception as e:
    st.error(f"Erro ao acessar cabeçalhos da planilha: {e}")
    st.stop()

tarefas = [t for t in headers if t.upper() in ["PHOTOSHOOT", "BLOOD TEST", "UNIFORM", "MUSIC", "STATS"]]

# 📍 Filtros no sidebar
st.sidebar.title("📂 Filtros")
eventos = ["Todos"] + sorted(df["Event"].dropna().unique().tolist())
corner_opts = ["Blue", "Red"]
status_opts = ["Todos", "Somente Pendentes", "Somente Concluídos"]

selected_event = st.sidebar.selectbox("Event", eventos)
selected_corner = st.sidebar.selectbox("Corner", corner_opts)
selected_status = st.sidebar.selectbox("Status das Tarefas", status_opts)

# 📃 Aplicando filtros
if selected_event != "Todos":
    df = df[df["Event"] == selected_event]
df = df[df["Corner"] == selected_corner]

if selected_status == "Somente Pendentes":
    df = df[df[tarefas].apply(lambda row: any(str(row[t]).lower() == "required" for t in tarefas), axis=1)]
elif selected_status == "Somente Concluídos":
    df = df[df[tarefas].apply(lambda row: all(str(row[t]).lower() == "done" for t in tarefas), axis=1)]

# 🏻 Exibindo resultados por atleta
for _, row in df.iterrows():
    lock = row.get("LockBy")
    id_unico = f"lock_{row['original_index']}"
    edicao_liberada = st.toggle("Editar", key=id_unico, value=(lock == "1724"), disabled=(lock not in ["", "1724"]))

    if edicao_liberada and lock != "1724":
        salvar_valor(sheet, row['original_index'], headers.index("LockBy"), "1724")
    elif not edicao_liberada and lock == "1724":
        salvar_valor(sheet, row['original_index'], headers.index("LockBy"), "")

    st.markdown("<hr>", unsafe_allow_html=True)
    col1, col2 = st.columns([0.3, 0.7])
    with col1:
        st.image(row.get("Avatar"), width=100)
    with col2:
        st.markdown(f"<div class='name-tag'>{row.get('Name')}</div>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center;'>Fight {row.get('Fight Order')} | {row.get('Division')} | Opponent {row.get('Oponent')}</p>", unsafe_allow_html=True)

    info1, info2 = st.columns(2)
    with info1:
        st.markdown("<div class='section-label'>Detalhes Pessoais</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <table>
            <tr><th>Event</th><td>{row.get('Event')}</td></tr>
            <tr><th>Corner</th><td>{row.get('Corner')}</td></tr>
            <tr><th>Weight</th><td>{row.get('Weight')}</td></tr>
        </table>""", unsafe_allow_html=True)

        st.markdown("<div class='section-label'>Hotel</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <table>
            <tr><th>Check-in</th><td>{row.get('Check-in')}</td></tr>
            <tr><th>Check-out</th><td>{row.get('Check-out')}</td></tr>
            <tr><th>Room</th><td>{row.get('Room')}</td></tr>
        </table>""", unsafe_allow_html=True)

    with info2:
        st.markdown("<div class='section-label'>Logística</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <table>
            <tr><th>Flight</th><td>{row.get('Flight')}</td></tr>
            <tr><th>Arrival</th><td>{row.get('Arrival')}</td></tr>
            <tr><th>Coach</th><td>{row.get('Coach')}</td></tr>
        </table>""", unsafe_allow_html=True)

        st.markdown("<div class='section-label'>Notas</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <table>
            <tr><th>Note</th><td>{row.get('Note')}</td></tr>
            <tr><th>Comments</th><td>{row.get('Comments')}</td></tr>
        </table>""", unsafe_allow_html=True)

    st.markdown("<div class='section-label'>Tarefas</div>", unsafe_allow_html=True)
    badge_line = []
    for t in tarefas:
        valor_atual = str(row.get(t, "")).lower()
        classe = "badge-neutral"
        if valor_atual == "required":
            classe = "badge-required"
        elif valor_atual == "done":
            classe = "badge-done"

        if edicao_liberada:
            if st.button(t.upper(), key=f"{t}_{row['original_index']}"):
                novo_valor = "done" if valor_atual == "required" else "required"
                salvar_valor(sheet, row['original_index'], headers.index(t), novo_valor)
                st.experimental_rerun()

        badge_line.append(f"<span class='badge {classe}'>{t.upper()}</span>")

    st.markdown(" ".join(badge_line), unsafe_allow_html=True)
