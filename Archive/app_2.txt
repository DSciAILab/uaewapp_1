# 📍 UAE Warriors App - Fightcard Page
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Fightcard", layout="wide")

# 🔐 Conexão com a aba Fightcard
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UAEW_App").worksheet("Fightcard")

sheet = connect_sheet()

@st.cache_data(ttl=30)
def load_data():
    return pd.DataFrame(sheet.get_all_records())

df = load_data()
df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("-", "_")

# Agrupar os atletas por evento e FightOrder
grouped = df.groupby(["Event", "FightOrder"])

st.title("📝 Official Fightcard")

for (event, order), group in grouped:
    if len(group) != 2:
        continue  # Pula pares incompletos

    azul = group[group["Corner"].str.lower() == "blue"].iloc[0] if any(group["Corner"].str.lower() == "blue") else group.iloc[0]
    vermelho = group[group["Corner"].str.lower() == "red"].iloc[0] if any(group["Corner"].str.lower() == "red") else group.iloc[1]

    col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 2, 2])

    with col1:
        st.image(azul["Picture"], width=150)
    with col2:
        st.markdown(f"### 🟦 {azul['Fighter']}")
        st.markdown(f"**Division**: {azul['Division']}")
    with col3:
        st.markdown(f"### 🆚")
        st.markdown(f"#### Fight {order}")
        st.markdown(f"**Event**: {event}")
    with col4:
        st.markdown(f"### 🔴 {vermelho['Fighter']}")
        st.markdown(f"**Division**: {vermelho['Division']}")
    with col5:
        st.image(vermelho["Picture"], width=150)

    st.markdown("---")
