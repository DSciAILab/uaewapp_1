import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Fightcard")

# Função para carregar dados
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    df["Corner"] = df["Corner"].str.strip().str.lower()
    return df

# Função para renderizar a tabela em HTML
def render_fightcard_html(df):
    html = """
    <style>
        .fightcard-table { width: 100%; border-collapse: collapse; margin-bottom: 50px; }
        .fightcard-table td { padding: 10px; text-align: center; vertical-align: middle; font-size: 16px; }
        .fightcard-table img.fightcard-img { width: 100px; border-radius: 10px; }
        .blue { background-color: #e0f0ff; font-weight: bold; }
        .red { background-color: #ffe0e0; font-weight: bold; }
        .middle-cell { background-color: #f9f9f9; font-weight: bold; font-size: 14px; }
        .event-header { background-color: #222; color: white; font-weight: bold; text-align: center; font-size: 18px; padding: 8px; }
    </style>
    """

    grouped = df.groupby("Event")

    for event, group in grouped:
        html += f"<div class='event-header'>{event}</div>"
        html += """
        <table class='fightcard-table'>
            <thead>
                <tr>
                    <th colspan='2' style='background-color:#cce5ff;'>BLUE CORNER</th>
                    <th style='background-color:#eee;'>FIGHT INFO</th>
                    <th colspan='2' style='background-color:#f5c6cb;'>RED CORNER</th>
                </tr>
            </thead>
            <tbody>
        """

        fights = group.groupby("FightOrder")

        for fight_order, fight_df in fights:
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

        html += "</tbody></table>"

    return html

# Execução da página
df = load_data()
html = render_fightcard_html(df)
st.markdown(html, unsafe_allow_html=True)
