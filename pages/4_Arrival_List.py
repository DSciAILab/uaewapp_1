# pages/4_Arrival_List.py
from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import datetime
from utils import get_gspread_client, connect_gsheet_tab

# --- Bootstrap: configura página, autentica e desenha o sidebar unificado ---
bootstrap_page("Arrival List")
st.title("Arrival List")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
DATA_TAB_NAME = "df"

# --- Data Loading ---
@st.cache_data(ttl=600)
def load_arrival_data(sheet_name: str = MAIN_SHEET_NAME, data_tab_name: str = DATA_TAB_NAME) -> pd.DataFrame:
    """Loads and processes arrival data from the Google Sheet."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, data_tab_name)
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()

        # Mantém apenas colunas relevantes que existirem
        display_cols = [
            "INACTIVE", "ID", "ROLE", "CORNER", "NAME",
            "ArrivalFlight", "ArrivalDate", "ArrivalTime", "ArrivalAirport",
            "transfer_arrival_status", "transfer_arrival_car", "transfer_arrival_driver"
        ]
        existing_cols = [c for c in display_cols if c in df.columns]
        df = df[existing_cols]

        # NAME é essencial
        if "NAME" in df.columns:
            df["NAME"] = df["NAME"].astype(str).str.strip()
            df = df[df["NAME"].ne("")].copy()
        else:
            st.error("The 'NAME' column is essential and was not found in the sheet.", icon="🚨")
            return pd.DataFrame()

        # Normalizações leves (evitam comparações quebradas)
        if "CORNER" in df.columns:
            df["CORNER"] = df["CORNER"].astype(str).str.strip().str.upper()

        if "ArrivalAirport" in df.columns:
            df["ArrivalAirport"] = df["ArrivalAirport"].astype(str).str.strip()

        if "ArrivalDate" in df.columns:
            df["ArrivalDate"] = df["ArrivalDate"].astype(str).str.strip()

        if "ArrivalTime" in df.columns:
            df["ArrivalTime"] = df["ArrivalTime"].astype(str).str.strip()

        if "transfer_arrival_status" in df.columns:
            s = df["transfer_arrival_status"].astype(str).str.strip().str.upper()
            s = s.replace({"CANCELLED": "CANCELED"})  # normaliza variação britânica
            df["transfer_arrival_status"] = s

        return df

    except Exception as e:
        st.error(f"Error loading arrival data: {e}", icon="🚨")
        return pd.DataFrame()


def highlight_today(row: pd.Series):
    """Destaca linhas do dia (funciona quando ArrivalDate está como 'dd/mm' ou 'dd/mm/yyyy')."""
    today = datetime.datetime.now()
    today_dm = today.strftime("%d/%m")
    val = str(row.get("ArrivalDate", "")).strip()
    if not val:
        return [""] * len(row)

    # aceita tanto dd/mm quanto dd/mm/yyyy
    if val == today_dm:
        return ["background-color: #ffe066"] * len(row)
    try:
        dt = datetime.datetime.strptime(val, "%d/%m/%Y")
        if dt.strftime("%d/%m") == today_dm:
            return ["background-color: #ffe066"] * len(row)
    except Exception:
        pass
    return [""] * len(row)


# --- Main Application ---
with st.spinner("Loading data..."):
    df_arrivals = load_arrival_data()

# Filtra INACTIVE (mantém apenas ativos)
if not df_arrivals.empty and "INACTIVE" in df_arrivals.columns:
    df_arrivals = df_arrivals[df_arrivals["INACTIVE"].isin([False, "FALSE", "false", "False", 0, "0"])]
    df_arrivals.drop(columns=["INACTIVE"], inplace=True, errors="ignore")

if df_arrivals.empty:
    st.info("No arrival records found with a filled name.")
else:
    with st.expander("Settings", expanded=True):
        # Filtro de tipo (fighters / car request)
        filtro = st.segmented_control(
            "Filter arrivals:",
            options=["All", "Only Fighters", "Cars with request"],
            key="role_car_filter",
            default="All",
        )

        df_filtrado = df_arrivals.copy()
        if filtro == "Only Fighters" and "ROLE" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["ROLE"].astype(str).str.upper() == "1 - FIGHTER"]
        elif filtro == "Cars with request" and "transfer_arrival_car" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["transfer_arrival_car"].astype(str).str.strip() != ""]

        # --- Filtro por STATUS (coluna transfer_arrival_status) ---
        status_filter = st.segmented_control(
            "Filter by status:",
            options=["All", "Planned", "Done", "Canceled", "No Show"],
            key="status_filter",
            default="All",
        )

        if status_filter != "All" and "transfer_arrival_status" in df_filtrado.columns:
            target = status_filter.upper()
            if target == "CANCELED":
                mask = df_filtrado["transfer_arrival_status"].isin(["CANCELED", "CANCELLED"])
            else:
                mask = df_filtrado["transfer_arrival_status"] == target
            df_filtrado = df_filtrado[mask]

        # === Toggles lado a lado ===
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            modo_cards = st.toggle("View as cards", value=True, key="view_as_cards")
        with col_t2:
            hide_resident = st.toggle(
                "Hide airport: Resident",
                value=False,
                key="hide_resident_cards",
                help="When ON, hides cards where ArrivalAirport = Resident (cards view only).",
            )

        # Search box (todas as colunas)
        search = st.text_input("Search in any column:")
        df_search = df_filtrado.copy()
        if search:
            patt = str(search).strip()
            if patt:
                mask = pd.Series(False, index=df_search.index)
                for col in df_search.columns:
                    mask = mask | df_search[col].astype(str).str.contains(patt, case=False, na=False)
                df_search = df_search[mask]

    # --- Métricas (baseadas em df_search) ---
    def norm_status_series(s: pd.Series) -> pd.Series:
        s = s.astype(str).str.strip().str.upper()
        return s.replace({"CANCELLED": "CANCELED"})

    status_series = norm_status_series(df_search.get("transfer_arrival_status", pd.Series(dtype=str)))

    total_filtered = len(df_search)
    total_all = len(df_arrivals)
    planned_count = (status_series == "PLANNED").sum()
    done_count = (status_series == "DONE").sum()
    canceled_count = (status_series == "CANCELED").sum()
    noshow_count = (status_series == "NO SHOW").sum()

    summary_html = f"""
    <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0;">
        <span style="font-weight:bold;">Showing {total_filtered} of {total_all} arrivals:</span>
        <span style="background-color:#ffe066;color:#23272f;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Planned: {planned_count}</span>
        <span style="background-color:#27ae60;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Done: {done_count}</span>
        <span style="background-color:#e74c3c;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Canceled: {canceled_count}</span>
        <span style="background-color:#95a5a6;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">No Show: {noshow_count}</span>
    </div>"""
    st.markdown(summary_html, unsafe_allow_html=True)

    if modo_cards:
        # Aplica o "hide resident" apenas nos cards
        df_cards = df_search.copy()
        if hide_resident and "ArrivalAirport" in df_cards.columns:
            df_cards = df_cards[~df_cards["ArrivalAirport"].astype(str).str.strip().str.lower().eq("resident")]

        now = datetime.datetime.now()
        today_str = now.strftime("%d/%m")

        corner_colors = {
            "RED": "#e74c3c",
            "BLUE": "#3498db",
            "GREEN": "#27ae60",
            "YELLOW": "#f1c40f",
            "BLACK": "#23272f",
            "WHITE": "#f8f9fa",
        }

        groups = df_cards.groupby("ArrivalDate") if "ArrivalDate" in df_cards.columns else [(None, df_cards)]

        for arrival_date, group in groups:
            st.subheader(f"Arrivals on {arrival_date} ({len(group)})")

            for _, row in group.iterrows():
                card_color, text_color = "#23272f", "#f8f9fa"

                # calcula janela crítica (laranja) para próximas 3h / últimas 30min
                arrival_dt = None
                try:
                    ad = str(row.get("ArrivalDate", "")).strip()
                    at = str(row.get("ArrivalTime", "")).strip()
                    if ad and at:
                        # aceita dd/mm e dd/mm/yyyy
                        if len(ad.split("/")) == 2:
                            arrival_datetime_str = f"{ad}/{now.year} {at}"
                            arrival_dt = datetime.datetime.strptime(arrival_datetime_str, "%d/%m/%Y %H:%M")
                        else:
                            arrival_datetime_str = f"{ad} {at}"
                            arrival_dt = datetime.datetime.strptime(arrival_datetime_str, "%d/%m/%Y %H:%M")
                except Exception:
                    arrival_dt = None

                is_today = (str(arrival_date) == today_str)
                if arrival_dt:
                    diff = arrival_dt - now
                    if datetime.timedelta(minutes=-30) <= diff <= datetime.timedelta(hours=3):
                        card_color, text_color = "#FF8C00", "#f8f9fa"
                elif is_today:
                    card_color, text_color = "#ffe066", "#23272f"

                corner = str(row.get("CORNER", "")).upper()
                corner_label_color = corner_colors.get(corner, "#888")

                # status chip (inclui CANCELED e NO SHOW)
                raw_status = str(row.get("transfer_arrival_status", "")).strip().upper()
                status = "CANCELED" if raw_status in ("CANCELLED", "CANCELED") else raw_status

                if status == "PLANNED":
                    status_label = "<span style='background-color:#ffe066;color:#23272f;padding:2px 8px;border-radius:8px;font-weight:bold;'>Planned</span>"
                elif status == "DONE":
                    status_label = "<span style='background-color:#27ae60;color:#fff;padding:2px 8px;border-radius:8px;font-weight:bold;'>Done</span>"
                elif status == "CANCELED":
                    status_label = "<span style='background-color:#e74c3c;color:#fff;padding:2px 8px;border-radius:8px;font-weight:bold;'>Canceled</span>"
                elif status == "NO SHOW":
                    status_label = "<span style='background-color:#95a5a6;color:#fff;padding:2px 8px;border-radius:8px;font-weight:bold;'>No Show</span>"
                else:
                    safe = str(row.get("transfer_arrival_status", ""))
                    status_label = f"<span style='background-color:#888;color:#fff;padding:2px 8px;border-radius:8px;'>{safe}</span>"

                car_val = str(row.get("transfer_arrival_car", "")).strip()
                driver_val = str(row.get("transfer_arrival_driver", "")).strip()

                # monta a linha inferior (car / driver / status)
                if car_val or driver_val:
                    line_html = "<div style='display:flex;gap:18px;align-items:center;'>"
                    if car_val:
                        line_html += f"<span><strong>Car:</strong> {car_val}</span>"
                    if driver_val:
                        line_html += f"<span style='margin-left:12px;opacity:0.9;'><strong>Driver:</strong> {driver_val}</span>"
                    line_html += status_label + "</div>"
                else:
                    line_html = f"<div style='display:flex;align-items:center;'>{status_label}</div>"

                st.markdown(
                    f"""
                    <div style="background-color: {card_color}; border-radius: 12px; padding: 16px; margin-bottom: 12px; color: {text_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                        <div style="display: flex; align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 20px; font-weight: bold;">{row.get('NAME','')}</span>
                            <span style="background-color: {corner_label_color}; color: #fff; font-size: 14px; font-weight: bold; border-radius: 8px; padding: 2px 10px; margin-left: 12px;">{corner}</span>
                        </div>
                        <div style="display: flex; gap: 18px; margin-bottom: 8px;">
                            <span><strong>Flight:</strong> {row.get('ArrivalFlight','')}</span>
                            <span><strong>Time:</strong> {row.get('ArrivalTime','')}</span>
                            <span><strong>Airport:</strong> {row.get('ArrivalAirport','')}</span>
                        </div>
                        {line_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        # --- Tabela ---
        df_search_sorted = df_search.copy()
        current_year = datetime.datetime.now().year
        if "ArrivalDate" in df_search_sorted.columns and "ArrivalTime" in df_search_sorted.columns:
            # cria coluna auxiliar para ordenar data/hora; remove ao exibir
            ad = df_search_sorted["ArrivalDate"].astype(str).str.strip()
            # aceita dd/mm e dd/mm/yyyy
            ad_full = ad.where(ad.str.count("/") == 2, ad + f"/{current_year}")
            df_search_sorted["ArrivalDateTime"] = pd.to_datetime(
                ad_full + " " + df_search_sorted["ArrivalTime"].astype(str).str.strip(),
                format="%d/%m/%Y %H:%M",
