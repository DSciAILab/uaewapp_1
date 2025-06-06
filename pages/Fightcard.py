import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Fightcard")
st.markdown("<h1 style='text-align:center; color:white;'>FIGHT CARDS</h1>", unsafe_allow_html=True)

@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    df["Corner"] = df["Corner"].str.strip().str.lower()
    return df

def render_fightcard_html(df):
    html = '''
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700&display=swap');
        body, .main {
            background-color: #0e1117;
            color: white;
            font-family: 'Barlow Condensed', sans-serif;
        }
        .fightcard-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 50px;
            table-layout: fixed;
        }
        .fightcard-table th, .fightcard-table td {
            padding: 12px;
            text-align: center;
            vertical-align: middle;
            font-size: 16px;
            color: white;
            border-bottom: 1px solid #444;
        }
        .fightcard-img {
            width: 100px;
            height: 100px;
            object-fit: cover;
            border-radius: 8px;
        }
        .blue {
            background-color: #0d2d51;
            font-weight: bold;
        }
        .red {
            background-color: #3b1214;
            font-weight: bold;
        }
        .middle-cell {
            background-color: #2f2f2f;
            font-weight: bold;
            font-size: 14px;
        }
        .event-header {
            background-color: #111;
            color: white;
            font-weight: bold;
            text-align: center;
            font-size: 20px;
            padding: 12px;
        }
        .fightcard-table th {
            background-color: #1c1c1c;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        @media screen and (max-width: 768px) {
            .fightcard-table td, .fightcard-table th {
                font-size: 13px;
                padding: 8px;
            }
            .fightcard-img {
                width: 60px;
                height: 60px;
            }
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
                    <th colspan='2'>Blue Corner</th>
                    <th>Fight Details</th>
                    <th colspan='2'>Red Corner</th>
                </tr>
            </thead>
            <tbody>
        '''
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

        html += "</tbody></table>"

    return html

df = load_data()
html = render_fightcard_html(df)
st.components.v1.html(html, height=6000, scrolling=True)
