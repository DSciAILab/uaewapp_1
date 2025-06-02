import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Configuração da página
st.set_page_config(page_title="Fightcard", layout="wide")

# 🎨 Estilo visual
st.markdown("""
    <style>
        .fightcard-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }
        .fightcard-table td {
            border: 1px solid #444;
            padding: 10px;
            text-align: center;
            color: white;
            font-size: 0.95rem;
        }
        .fightcard-img {
            height: 100px;
            border-radius: 6px;
        }
        .blue { background-color: rgba(0, 123, 255, 0.15); }
        .red { background-color: rgba(255, 0, 0, 0.15); }
        .middle-cell {
            background-color: #2c2c2c;
            font-weight: bold;
            font-size: 1rem;
        }
        .fightcard-title {
            font-weight: bold;
            font-size: 1.2rem;
            margin-top: 2rem;
        }
        .fightcard-table th {
            background-color: #333;
            padding: 8px;
            font-weight: bold;
            color: #ccc;
        }
    </style>
""", unsafe_allow_html=True)

# 🔐 Google Sheets
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UAEW_App").worksheet("Fightcard")

sheet = connect_sheet()

# 📥 Dados
@st.cache_data(ttl=30)
def load_data():
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("-", "_")
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    return df

df = load_data()

# 📊 Agrupamento
grouped = df.groupby(["Event", "FightOrder"])
st.title("📋 Fightcard Oficial")

event_groups = df.groupby("Event")

for event, group_df in event_groups:
    st.markdown(f"<div class='fightcard-title'>📌 {event}</div>", unsafe_allow_html=True)

    html = """
    <table class='fightcard-table'>
        <tr>
            <th>PICTURE</th>
            <th>FIGHTER</th>
            <th>FIGHT # / DIVISION</th>
            <th>FIGHTER</th>
            <th>PICTURE</th>
        </tr>
    """

    for fight_order, fight_group in group_df.groupby("FightOrder"):
        if fight_group.shape[0] != 2:
            continue

        fight_group = fight_group.sort_values(by="Corner", ascending=False)
        blue = fight_group[fight_group["Corner"].str.lower() == "blue"].iloc[0]
        red = fight_group[fight_group["Corner"].str.lower() == "red"].iloc[0]

        blue_img = f"<img src='{blue.Picture}' class='fightcard-img'>" if blue.Picture else ""
        red_img = f"<img src='{red.Picture}' class='fightcard-img'>" if red.Picture else ""

        html += f"""
        <tr>
            <td class='blue'>{blue_img}</td>
            <td class='blue'>{blue.Fighter}</td>
            <td class='middle-cell'>FIGHT #{int(fight_order)}<br>{blue.Division}</td>
            <td class='red'>{red.Fighter}</td>
            <td class='red'>{red_img}</td>
        </tr>
        """

    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)
