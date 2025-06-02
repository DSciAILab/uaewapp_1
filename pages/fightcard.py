import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 🔧 Configuração da página
st.set_page_config(page_title="Fightcard", layout="wide")

# 🎨 Estilo visual
st.markdown("""
    <style>
        .fightcard-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        .fightcard-table th, .fightcard-table td {
            border: 1px solid #444;
            padding: 10px;
            text-align: center;
            color: white;
        }
        .fightcard-header {
            background-color: #333;
            font-weight: bold;
            font-size: 1.1rem;
        }
        .fightcard-img {
            height: 100px;
            border-radius: 6px;
        }
        .blue { background-color: rgba(0, 123, 255, 0.15); }
        .red { background-color: rgba(255, 0, 0, 0.1); }
    </style>
""", unsafe_allow_html=True)

# 🔐 Conexão com Google Sheets
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UAEW_App").worksheet("Fightcard")

sheet = connect_sheet()

# 📥 Carregar dados da aba Fightcard
@st.cache_data(ttl=30)
def load_data():
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("-", "_")
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    return df

df = load_data()

# Agrupar por evento e número da luta
grouped = df.groupby(["Event", "FightOrder"])
st.title("📋 Fightcard Oficial")

last_event = None

for (event, order), group in grouped:
    if group.shape[0] != 2:
        continue  # Ignora lutas incompletas

    group = group.sort_values(by="Corner", ascending=False)  # Azul vem primeiro
    blue = group[group["Corner"].str.lower() == "blue"].iloc[0]
    red = group[group["Corner"].str.lower() == "red"].iloc[0]

    if event != last_event:
        st.subheader(f"📌 {event}")
        last_event = event

    st.markdown(f"""
    <table class='fightcard-table'>
        <tr class='fightcard-header'>
            <td class='blue'>PICTURE</td>
            <td class='blue'>FIGHTER</td>
            <td class='fightcard-header'>FIGHT #{int(order)}<br>{blue.Division}</td>
            <td class='red'>FIGHTER</td>
            <td class='red'>PICTURE</td>
        </tr>
        <tr>
            <td class='blue'><img src="{blue.Picture}" class="fightcard-img"></td>
            <td class='blue'>{blue.Fighter}</td>
            <td class='fightcard-header'>x</td>
            <td class='red'>{red.Fighter}</td>
            <td class='red'><img src="{red.Picture}" class="fightcard-img"></td>
        </tr>
    </table>
    """, unsafe_allow_html=True)
