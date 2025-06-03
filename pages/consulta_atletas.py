import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Consulta de Atletas", layout="wide")

# CSS Responsivo
st.markdown("""
<style>
@media only screen and (max-width: 768px) {
    div[style*="display:flex"][style*="justify-content:space-between"] {
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 10px !important;
    }
    div[style*="text-align:right"] {
        text-align: left !important;
        font-size: 14px !important;
    }
    img[style*="border-radius:50%"] {
        width: 60px !important;
        height: 60px !important;
    }
    h4 {
        font-size: 18px !important;
    }
}
</style>
""", unsafe_allow_html=True)

# 🔐 Conectar ao Google Sheets
@st.cache_resource
def connect_gsheet(sheet_name, tab_name):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    worksheet = client.open(sheet_name).worksheet(tab_name)
    return worksheet

# 📥 Carregar dados dos atletas
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)]
    df["EVENT"] = df["EVENT"].fillna("Z")
    df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce").dt.strftime("%d/%m/%Y")
    df["PASSPORT EXPIRE DATE"] = pd.to_datetime(df["PASSPORT EXPIRE DATE"], errors="coerce").dt.strftime("%d/%m/%Y")
    return df.sort_values(by=["EVENT", "NAME"])

# 📝 Função para registrar log no Google Sheets
def registrar_log(nome, tipo, user_id):
    sheet = connect_gsheet("UAEW_App", "Attendance")
    data_registro = datetime.now().strftime("%d/%m/%Y %H:%M")
    nova_linha = [nome, data_registro, tipo, user_id]
    sheet.append_row(nova_linha, value_input_option="USER_ENTERED")

# 🌐 Interface do app
st.title("Consulta de Atletas")
user_id = st.text_input("Informe seu PS (ID de usuário)", max_chars=15)
tipo = st.selectbox("Tipo de verificação", ["Blood Test", "PhotoShoot"])
status_view = st.radio("Filtro", ["Todos", "Feitos", "Restantes"], horizontal=True)

df = load_data()

# Simulação de estado de presença
if "presencas" not in st.session_state:
    st.session_state["presencas"] = {}

# 🔁 Loop pelos atletas
for i, row in df.iterrows():
    presenca_id = f"{row['NAME']}_{tipo}"
    presenca_registrada = st.session_state["presencas"].get(presenca_id, False)

    if status_view == "Feitos" and not presenca_registrada:
        continue
    if status_view == "Restantes" and presenca_registrada:
        continue

    with st.container():
        st.markdown(f"""
        <div style='display:flex; align-items:center; justify-content:space-between; background-color:{"#143d14" if presenca_registrada else "#1e1e1e"}; padding:15px; border-radius:10px; margin-bottom:10px;'>
            <div style='display:flex; align-items:center; gap:20px;'>
                <img src='{row["IMAGE"]}' style='width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid white;'>
                <div>
                    <h4 style='margin:0;'>{row["NAME"]}</h4>
                    <p style='margin:0; font-size:14px;'>Evento: <b>{row["EVENT"]}</b></p>
                </div>
            </div>
            <div style='font-size:14px; text-align:right; min-width:300px;'>
                <p><b>Gênero:</b> {row["GENDER"]}</p>
                <p><b>Nascimento:</b> {row["DOB"]}</p>
                <p><b>Nacionalidade:</b> {row["NATIONALITY"]}</p>
                <p><b>Passaporte:</b> {row["PASSPORT"]}</p>
                <p><b>Expira em:</b> {row["PASSPORT EXPIRE DATE"]}</p>
                {f"<p><b>📱 WhatsApp:</b> <a href='https://wa.me/{str(row['MOBILE']).replace('+','').replace(' ','')}' target='_blank'>{row['MOBILE']}</a></p>" if pd.notna(row.get("MOBILE")) else ""}
                {f"<p><b>📄 <a href='{row['PASSPORT IMAGE']}' target='_blank'>Ver Passaporte</a></b></p>" if pd.notna(row.get("PASSPORT IMAGE")) else ""}
            </div>
            <div style='text-align:right;'>
                {f"<p style='color:#5efc82; font-weight:bold;'>✅ Attendance registrada</p>" if presenca_registrada else ""}
        """, unsafe_allow_html=True)

        # Botão de presença
        if not presenca_registrada:
            if st.button(f"Registrar presença de {row['NAME']}", key=f"attend_{i}"):
                if not user_id.strip():
                    st.warning("⚠️ Informe seu PS antes de registrar a presença.")
                else:
                    st.session_state["presencas"][presenca_id] = True
                    registrar_log(row["NAME"], tipo, user_id)
                    st.success("✅ Presença registrada com sucesso!")
                    st.rerun()

        st.markdown("</div></div><hr>", unsafe_allow_html=True)
