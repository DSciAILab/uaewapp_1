import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="Consulta de Atletas", layout="wide")

# Conectar ao Google Sheets
@st.cache_resource
def connect_gsheet(sheet_name, tab_name):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    worksheet = client.open(sheet_name).worksheet(tab_name)
    return worksheet

# Carregar dados
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

# Registrar presença
def registrar_log(nome, tipo, user_id):
    sheet = connect_gsheet("UAEW_App", "Attendance")
    data_registro = datetime.now().strftime("%d/%m/%Y %H:%M")
    nova_linha = [nome, data_registro, tipo, user_id]
    sheet.append_row(nova_linha, value_input_option="USER_ENTERED")

# UI
st.title("Consulta de Atletas")
user_id = st.text_input("Informe seu PS (ID de usuário)", max_chars=15)
tipo = st.selectbox("Tipo de verificação", ["Blood Test", "PhotoShoot"])
status_view = st.radio("Filtro", ["Todos", "Feitos", "Restantes"], horizontal=True)

df = load_data()
if "presencas" not in st.session_state:
    st.session_state["presencas"] = {}

for i, row in df.iterrows():
    presenca_id = f"{row['NAME']}_{tipo}"
    presenca_registrada = st.session_state["presencas"].get(presenca_id, False)

    if status_view == "Feitos" and not presenca_registrada:
        continue
    if status_view == "Restantes" and presenca_registrada:
        continue

    with st.container():
        bg_color = "#143d14" if presenca_registrada else "#1e1e1e"
        st.markdown(f"""
        <div style='display:flex; align-items:center; justify-content:space-between; background-color:{bg_color}; padding:15px; border-radius:10px; margin-bottom:10px;'>
            <div style='display:flex; align-items:center; gap:20px;'>
                <img src='{row["IMAGE"]}' style='width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid white;'>
                <div>
                    <h4 style='margin:0;'>{row["NAME"]}</h4>
                    <p style='margin:0; font-size:14px;'>Evento: <b>{row["EVENT"]}</b></p>
                    {"<p style='margin:0;'><a href='https://wa.me/" + row["MOBILE"].replace('+','').replace(' ','') + "' target='_blank' style='color:#5efc82;'>Enviar WhatsApp</a></p>" if pd.notna(row.get("MOBILE")) and str(row["MOBILE"]).strip() else ""}
                </div>
            </div>
            <div style='font-size:14px; text-align:right; line-height:1.6;'>
                <b>Gênero:</b> {row["GENDER"]}<br>
                <b>Nascimento:</b> {row["DOB"]}<br>
                <b>Nacionalidade:</b> {row["NATIONALITY"]}<br>
                <b>Passaporte:</b> {row["PASSPORT"]}<br>
                <b>Expira em:</b> {row["PASSPORT EXPIRE DATE"]}<br>
                {"<a href='" + row["PASSPORT IMAGE"] + "' target='_blank' style='color:#00b3ff;'>📄 Ver Passaporte</a>" if pd.notna(row.get("PASSPORT IMAGE")) and str(row["PASSPORT IMAGE"]).startswith("http") else ""}
            </div>
        </div>
        """, unsafe_allow_html=True)

        if presenca_registrada:
            st.success("✅ Attendance registrada")
        else:
            if st.button(f"Registrar presença de {row['NAME']}", key=f"attend_{i}"):
                if not user_id.strip():
                    st.warning("⚠️ Informe seu PS antes de registrar a presença.")
                else:
                    st.session_state["presencas"][presenca_id] = True
                    registrar_log(row["NAME"], tipo, user_id)
                    st.success("✅ Presença registrada com sucesso!")
                    st.rerun()
