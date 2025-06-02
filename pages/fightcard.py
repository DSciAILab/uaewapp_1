import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Fightcard")

# Função para carregar dados da aba "Fightcard"
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("-", "_")
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    df["Corner"] = df["Corner"].str.strip().str.lower()
    return df

# Função para renderizar a tabela em HTML
def render_fightcard_html(df):
    html = '''
    <style>
        .fightcard-table { width: 100%; border-collapse: collapse; margin-bottom: 50px; }
        .fightcard-table td, .fightcard-table th {
            padding: 10px;
            text-align: center;
            vertical-align: middle;
            font-size: 16px;
            border: 1px solid #444;
        }
        .fightcard-table img.fightcard-img {
            width: 100px;
            border-radius: 8px;
        }
        .blue { background-color: #102B46; color: white; }
        .red { background-color: #360D0D; color: white; }
        .middle-cell {
            background-color: #2F2F2F;
            color: white;
            font-weight: bold;
            font-size: 15px;
        }
        .event-header {
            background-color: #111;
            color: white;
            font-weight: bold;
            text-align: center;
            font-size: 22px;
            padding: 12px;
            margin-top: 40px;
            border-radius: 6px;
        }
    </style>
    '''

    grouped = df.groupby("Event")

    for event, group in grouped:
        html += f"<div class='event-header'>{event}</div>"
        html += '''
        <table class='fightcard-table'>
            <thead>
                <tr>
                    <th colspan='2' class='blue'>BLUE CORNER</th>
                    <th class='middle-cell'>FIGHT</th>
                    <th colspan='2' class='red'>RED CORNER</th>
                </tr>
            </thead>
            <tbody>
        '''

        fights = group.groupby("FightOrder")

        for fight_order, fight_df in fights:
            blue = fight_df[fight_df["Corner"] == "blue"]
            red = fight_df[fight_df["Corner"] == "red"]

            blue = blue.iloc[0] if not blue.empty else {}
            red = red.iloc[0] if not red.empty else {}

            blue_img = f"<img src='{blue.get('Picture', '')}' class='fightcard-img'>" if blue.get("Picture", "") else ""
            red_img = f"<img src='{red.get('Picture', '')}' class='fightcard-img'>" if red.get("Picture", "") else ""
            blue_name = blue.get("Fighter", "")
            red_name = red.get("Fighter", "")
            division = blue.get("Division", "") or red.get("Division", "")
            info = f"FIGHT #{int(fight_order)}<br>{division}"

            html += f'''
            <tr>
                <td class='blue'>{blue_img}</td>
                <td class='blue'>{blue_name}</td>
                <td class='middle-cell'>{info}</td>
                <td class='red'>{red_name}</td>
                <td class='red'>{red_img}</td>
            </tr>
            '''

        html += "</tbody></table>"

    return html

# Execução da página
df = load_data()
html = render_fightcard_html(df)
st.markdown(html, unsafe_allow_html=True)
