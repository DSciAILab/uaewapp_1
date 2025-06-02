# 📍 UAE Warriors App - Fight Card Page
# ✅ Layout unificado com colunas alinhadas e imagens centralizadas

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 🔐 Autenticação com Google Sheets
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client

# 📥 Carrega a aba 'Fightcard'
@st.cache_data(ttl=60)
def load_data():
    sheet = connect_sheet().open("UAEW_App").worksheet("Fightcard")
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("\u00a0", "")
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    return df

# 🎨 Estilos
st.markdown("""
<style>
.fightcard-table {
    border-collapse: collapse;
    width: 100%;
    margin-top: 20px;
}
.fightcard-table td {
    border: 1px solid #444;
    padding: 10px;
    text-align: center;
    font-size: 0.9rem;
}
.fightcard-table td.middle-cell {
    background-color: #333;
    color: white;
    font-weight: bold;
    font-size: 1rem;
}
.fightcard-table td.blue {
    background-color: #0a2342;
    color: white;
}
.fightcard-table td.red {
    background-color: #2c0f13;
    color: white;
}
.fightcard-img {
    width: 70px;
    height: 70px;
    border-radius: 50%;
    object-fit: cover;
}
</style>
""", unsafe_allow_html=True)

# 🧩 Renderiza o fightcard
def render_fightcard_html(df):
    html = "<table class='fightcard-table'>"
    html += "<tr><td class='blue'>PICTURE</td><td class='blue'>FIGHTER</td><td class='middle-cell'>FIGHT</td><td class='red'>FIGHTER</td><td class='red'>PICTURE</td></tr>"

    grouped = df.groupby("Event")

    for event, group in grouped:
        group_sorted = group.sort_values("FightOrder")
        fights = group_sorted.groupby("FightOrder")
        for i, (_, fighters) in enumerate(fights):
            blue = fighters[fighters["Corner"].str.lower() == "blue"].squeeze()
            red = fighters[fighters["Corner"].str.lower() == "red"].squeeze()

            blue_img = f"<img src='{blue.get('Picture', '')}' class='fightcard-img'>" if blue.get("Picture", "") else ""
            red_img = f"<img src='{red.get('Picture', '')}' class='fightcard-img'>" if red.get("Picture", "") else ""

            fight_number = f"FIGHT #{int(blue['FightOrder'])}" if not pd.isna(blue.get("FightOrder")) else ""
            division = blue.get("Division", "") or red.get("Division", "")

            html += f"""
            <tr>
                <td class='blue'>{blue_img}</td>
                <td class='blue'>{blue.get("Fighter", "")}</td>
                <td class='middle-cell'>{fight_number}<br>{division}</td>
                <td class='red'>{red.get("Fighter", "")}</td>
                <td class='red'>{red_img}</td>
            </tr>
            """

    html += "</table>"
    return html

# 🚀 Executa a página
st.title("🥋 UAE Warriors - Fight Card")
df = load_data()
html = render_fightcard_html(df)
st.markdown(html, unsafe_allow_html=True)
