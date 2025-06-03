import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Consulta de Atletas", layout="wide")

# Autenticação com Google Sheets
@st.cache_resource
def connect_gsheet(sheet_name, tab_name):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    worksheet = client.open(sheet_name).worksheet(tab_name)
    return worksheet

# Carregamento de dados
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)]
    df["EVENT"] = df["EVENT"].fillna("Z")
    df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce").dt.strftime("%d/%m/%Y")
    df["PASSPORT EXPIRE DATE"] = pd.to_datetime(df["PASSPORT EXPIRE DATE"], errors="coerce").dt.strftime("%d/%m/%Y")
    df["BLOOD TEST"] = pd.to_datetime(df["BLOOD TEST"], errors="coerce").dt.strftime("%d/%m/%Y")
    return df.sort_values(by=["EVENT", "NAME"])

# Função para registrar no log de presença
def registrar_log(nome, tipo, user_id):
    sheet = connect_gsheet("UAEW_App", "Attendance")
    data_registro = datetime.now().strftime("%d/%m/%Y %H:%M")
    nova_linha = [nome, data_registro, tipo, user_id]
    sheet.append_row(nova_linha, value_input_option="USER_ENTERED")

# Interface
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

    blood_info = f"<tr><td><b>Blood Test in:</b></td><td>{row['BLOOD TEST']}</td></tr>" if tipo == "Blood Test" and pd.notna(row["BLOOD TEST"]) else ""

    button_text = "Subscrever attendance por uma nova?" if tipo == "Blood Test" and pd.notna(row["BLOOD TEST"]) else "Registrar Attendance"

    st.markdown(f"""
    <div style='background-color:{"#143d14" if presenca_registrada else "#1e1e1e"}; padding:20px; border-radius:10px; margin-bottom:15px;'>
        <div style='display:flex; align-items:center; gap:20px; flex-wrap:wrap; justify-content:space-between;'>
            <div style='display:flex; align-items:center; gap:15px;'>
                <img src='{row["IMAGE"]}' style='width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid white;'>
                <div>
                    <h4 style='margin:0;'>{row["NAME"]}</h4>
                    <p style='margin:0;'>{row["EVENT"]}</p>
                    {"<p style='margin:0; font-size:13px;'>Blood Test in: " + row["BLOOD TEST"] + "</p>" if blood_info else ""}
                </div>
            </div>
            <table style='font-size:14px; color:white;'>
                <tr><td><b>Gênero:</b></td><td>{row["GENDER"]}</td></tr>
                <tr><td><b>Nascimento:</b></td><td>{row["DOB"]}</td></tr>
                <tr><td><b>Nacionalidade:</b></td><td>{row["NATIONALITY"]}</td></tr>
                <tr><td><b>Passaporte:</b></td><td>{row["PASSPORT"]}</td></tr>
                <tr><td><b>Expira em:</b></td><td>{row["PASSPORT EXPIRE DATE"]}</td></tr>
            </table>
            <div style='min-width:180px; text-align:right;'>
                <form method='post'>
                    <input type='hidden' name='index' value='{i}'>
                    <button type='submit' name='attend_{i}' style='padding:10px 15px; background-color:#00b300; color:white; border:none; border-radius:5px;'>{button_text}</button>
                </form>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button(f"{button_text} - {row['NAME']}", key=f"attend_{i}"):
        if not user_id.strip():
            st.warning("⚠️ Informe seu PS antes de registrar a presença.")
        else:
            st.session_state["presencas"][presenca_id] = True
            registrar_log(row["NAME"], tipo, user_id)
            st.rerun()
