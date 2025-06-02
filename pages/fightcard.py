import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Fightcard")

# 📦 Carregar dados do Google Sheets
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    df["Corner"] = df["Corner"].str.strip().str.lower()
    return df

# 🎨 Função de renderização do HTML
def render_fightcard_html(df):
    html = """
    <style>
        .fightcard-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 40px;
            table-layout: fixed;
        }
        .fightcard-table td {
            padding: 10px;
            text-align: center;
            vertical-align: middle;
            font-size: 16px;
            font-weight: bold;
        }
        .fightcard-img {
            width: 100px;
            height: 100px;
            object-fit: cover;
            border-radius: 8px;
        }
        .blue {
            background-color: #cce5ff;
            color: #003366;
        }
        .red {
            background-color: #f5c6cb;
            color: #660000;
        }
        .middle-cell {
            background-color: #f1f1f1;
            color: #333;
            font-size: 15px;
        }
        .event-header {
            background-color: #222;
            color: white;
            font-weight: bold;
            text-align: center;
            font-size: 20px;
            padding: 10px;
            margin-top: 30px;
        }
    </style>
    """

    grouped = df.groupby("Event")

    for event, group in grouped:
        html += f"<div class='event-header'>{event}</div>"
        html += "<table class='fightcard-table'>"

        fights = group.groupby("FightOrder")

        for fight_order, fight_df in fights:
            blue = fight_df[fight_df["Corner"] == "blue"].squeeze()
            red = fight_df[fight_df["Corner"] == "red"].squeeze()

            blue_img = f"<img src='{blue.get('Picture', '')}' class='fightcard-img'>" if isinstance(blue, pd.Series) and blue.get("Picture") else ""
            red_img = f"<img src='{red.get('Picture', '')}' class='fightcard-img'>" if isinstance(red, pd.Series) and red.get("Picture") else ""
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

        html += "</table>"

    return html

# 🚀 Executar página
df = load_data()
html = render_fightcard_html(df)
st.components.v1.html(html, height=6000, scrolling=True)
