import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Fightcard")

# 🔁 Carrega os dados
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    df["Corner"] = df["Corner"].str.strip().str.lower()
    return df

# 🧱 Gera HTML do fightcard
def render_fightcard_html(df):
    style = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        .fightcard-table {
            width: 100%;
            border-collapse: collapse;
            font-family: 'Inter', sans-serif;
        }
        .fightcard-table tr {
            border-bottom: 1px solid #444;
        }
        .fightcard-table td {
            padding: 12px;
            text-align: center;
            vertical-align: middle;
            font-size: 15px;
        }
        .fightcard-img {
            width: 80px;
            height: 80px;
            border-radius: 8px;
            object-fit: cover;
            border: 1px solid #555;
        }
        .blue {
            background-color: #0d2c47;
            color: white;
            font-weight: 600;
        }
        .red {
            background-color: #440f0f;
            color: white;
            font-weight: 600;
        }
        .middle-cell {
            background-color: #2b2b2b;
            color: #f5f5f5;
            font-size: 13px;
            font-weight: bold;
            line-height: 1.4;
        }
        .header {
            background-color: #111;
            color: white;
            text-align: center;
            font-weight: 700;
            font-size: 18px;
            padding: 10px;
        }
        .subheader {
            background-color: #0d2c47;
            color: white;
            font-size: 14px;
            font-weight: bold;
        }
        .subheader-red {
            background-color: #440f0f;
            color: white;
            font-size: 14px;
            font-weight: bold;
        }
        .subheader-middle {
            background-color: #2b2b2b;
            color: white;
            font-size: 14px;
            font-weight: bold;
        }
    </style>
    """

    html = style
    grouped = df.groupby("Event")

    for event, group in grouped:
        html += f"<div class='header'>{event}</div>"
        html += """
        <table class='fightcard-table'>
            <thead>
                <tr>
                    <td class='subheader' colspan='2'>BLUE CORNER</td>
                    <td class='subheader-middle'>FIGHT DETAILS</td>
                    <td class='subheader-red' colspan='2'>RED CORNER</td>
                </tr>
            </thead>
            <tbody>
        """

        for fight_order, fight_df in group.groupby("FightOrder"):
            blue = fight_df[fight_df["Corner"] == "blue"].squeeze()
            red = fight_df[fight_df["Corner"] == "red"].squeeze()

            blue_img = f"<img src='{blue.get('Picture', '')}' class='fightcard-img'>" if isinstance(blue, pd.Series) and blue.get("Picture", "") else ""
            red_img = f"<img src='{red.get('Picture', '')}' class='fightcard-img'>" if isinstance(red, pd.Series) and red.get("Picture", "") else ""
            blue_name = blue.get("Fighter", "") if isinstance(blue, pd.Series) else ""
            red_name = red.get("Fighter", "") if isinstance(red, pd.Series) else ""
            division = blue.get("Division", "") if isinstance(blue, pd.Series) else red.get("Division", "")
            info = f"FIGHT #{int(fight_order)}<br>{division}"

            html += f"""
            <tr>
                <td class='blue'>{blue_img}</td>
                <td class='blue'>{blue_name}</td>
                <td class='middle-cell'>{info}</td>
                <td class='red'>{red_name}</td>
                <td class='red'>{red_img}</td>
            </tr>
            """

        html += "</tbody></table><br>"

    return html

# ▶️ Executar
st.title("🥋 FIGHT CARDS")
df = load_data()
html = render_fightcard_html(df)
st.markdown(html, unsafe_allow_html=True)
