# --- 0. Imports ---
import streamlit as st
import pandas as pd
from datetime import datetime
import html

from utils import get_gspread_client, connect_gsheet_tab
from auth import check_authentication, display_user_sidebar


# --- 1. Config ---
st.set_page_config(page_title="UAEW | Walkout Music", layout="wide")
check_authentication()

MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB = "df"
ATTENDANCE_TAB = "Attendance"

# Colunas esperadas
ATT_COLS = [
    "#", "Event", "Athlete ID", "Name", "Fighter", "Task",
    "Status", "User", "Timestamp", "Notes"
]


# --- 2. Load Attendance ---
@st.cache_data(ttl=120)
def load_attendance() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, MAIN_SHEET_NAME, ATTENDANCE_TAB)
        try:
            records = ws.get_all_records(expected_headers=ATT_COLS)
            df_att = pd.DataFrame(records)
        except Exception:
            vals = ws.get_all_values()
            if not vals:
                return pd.DataFrame(columns=ATT_COLS)
            rows = vals[1:] if len(vals) > 1 else []
            norm_rows = [
                (row[:len(ATT_COLS)] + [""] * (len(ATT_COLS) - len(row)))
                for row in rows
            ]
            df_att = pd.DataFrame(norm_rows, columns=ATT_COLS)

        for col in ATT_COLS:
            if col not in df_att.columns:
                df_att[col] = pd.NA

        if "Athlete ID" in df_att.columns:
            df_att["Athlete ID"] = df_att["Athlete ID"].astype(str)

        return df_att
    except Exception as e:
        st.error(f"Error loading attendance: {e}", icon="🚨")
        return pd.DataFrame(columns=ATT_COLS)


# --- 3. Save Attendance ---
def registrar_log(ath_id, ath_name, ath_event, task, status, notes, user):
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, MAIN_SHEET_NAME, ATTENDANCE_TAB)
        all_vals = ws.get_all_values()
        next_num = int(all_vals[-1][0]) + 1 if len(all_vals) > 1 and str(all_vals[-1][0]).isdigit() else len(all_vals) + 1

        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        new_row = [
            str(next_num),
            ath_event,
            ath_id,
            ath_name,
            ath_name,   # Fighter (duplicado por design da planilha original)
            task,
            status,
            user,
            ts,
            notes
        ]
        ws.append_row(new_row, value_input_option="USER_ENTERED")
        load_attendance.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar log: {e}", icon="🚨")
        return False


# --- 4. Utils ---
def last_event_music_links(df_att: pd.DataFrame, athlete_name: str, event: str):
    """Retorna lista [(label, url)] das últimas 3 músicas do atleta no evento anterior."""
    if df_att.empty:
        return []
    df_filt = df_att[
        (df_att["Name"].astype(str) == athlete_name)
        & (df_att["Task"] == "Walkout Music")
        & (df_att["Event"] == event)
    ].copy()
    if df_filt.empty:
        return []
    df_filt["TS_dt"] = pd.to_datetime(df_filt["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df_filt = df_filt.sort_values(by="TS_dt", ascending=False).head(3)

    links = []
    for i, row in enumerate(df_filt.itertuples(), start=1):
        url = getattr(row, "Notes", "")
        if url:
            label = f"{getattr(row, 'Event', 'N/A')} | Music {i}"
            links.append((label, url))
    return links


# --- 5. Main ---
display_user_sidebar()
st.title("Walkout Music")

with st.spinner("Carregando dados..."):
    df_attendance = load_attendance()
    # Aqui você deve também carregar df_athletes (igual nas outras páginas)
    # Para simplificar, vamos criar um DataFrame fake:
    df_athletes = pd.DataFrame([{
        "ID": "41",
        "NAME": "Abdul Elwahab Saeed",
        "EVENT": "UAEW63",
        "IMAGE": "https://via.placeholder.com/80",
        "MOBILE": "",
        "PASSPORT": "123456",
        "PASSPORT IMAGE": "",
    }])

if df_athletes.empty:
    st.info("Nenhum atleta para exibir.")
else:
    for _, row in df_athletes.iterrows():
        ath_id, ath_name, event = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])

        # --- Links do evento anterior ---
        prev_links = last_event_music_links(df_attendance, ath_name, event)
        pill_anchors = []
        for lbl, url in prev_links:
            pill_anchors.append(
                f"<a href='{html.escape(url, True)}' target='_blank' "
                f"class='pill-link'>{html.escape(lbl)}</a>"
            )
        pills_display = "flex" if pill_anchors else "none"
        pills_html = f"<div class='info-line' style='gap:8px; display:{pills_display};'>" + "".join(pill_anchors) + "</div>"

        # --- Card HTML ---
        card_html = f"""
        <div class='card-container' style='background-color:#1e1e1e;'>
          <img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/60"), True)}' class='card-img'>
          <div class='card-info'>
            <div class='info-line'><span class='fighter-name'>{html.escape(ath_name)} | {html.escape(ath_id)}</span></div>
            <div class='info-line'>Walkout Music: Pending</div>
            <hr style='border-color:#444;margin:5px 0;width:100%;'>
            {pills_html}
          </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

        # --- Edit / Save links ---
        edit_key = f"edit_mode_{ath_id}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False
        is_edit = st.session_state[edit_key]

        if not is_edit:
            if st.button("Edit Music Links", key=f"edit_{ath_id}", use_container_width=True):
                st.session_state[edit_key] = True
                st.rerun()
        else:
            link1 = st.text_input("Music Link 1", key=f"music1_{ath_id}")
            link2 = st.text_input("Music Link 2 (optional)", key=f"music2_{ath_id}")
            link3 = st.text_input("Music Link 3 (optional)", key=f"music3_{ath_id}")

            if st.button("Save Links", key=f"save_{ath_id}", type="primary", use_container_width=True):
                user = st.session_state.get("current_user_name", "System")
                saved = False
                for link in [link1, link2, link3]:
                    if link.strip():
                        registrar_log(ath_id, ath_name, event, "Walkout Music", "Done", link.strip(), user)
                        saved = True
                if saved:
                    st.session_state[edit_key] = False
                    st.success("Links salvos!")
                    st.rerun()
