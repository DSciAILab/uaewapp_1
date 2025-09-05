# pages/11_Task_Table.py
from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re
import unicodedata

# utils base
from utils import get_gspread_client, connect_gsheet_tab, load_config_data

# =========================
# Bootstrap (config + auth + sidebar) — não repita set_page_config aqui
# =========================
bootstrap_page("Task Table")
st.title("Task Table")

# =========================
# Constantes
# =========================
MAIN_SHEET_NAME   = "UAEW_App"
ATHLETES_TAB_NAME = "df"
ATTENDANCE_TAB    = "Attendance"
DEFAULT_EVENT     = "Z"  # usado nas suas páginas

# =========================
# Helpers
# =========================
def _clean_str_series(s: pd.Series) -> pd.Series:
    if s is None or s.empty:
        return pd.Series([], dtype=str)
    s = s.fillna("").astype(str).str.strip()
    invalid = {"", "none", "None", "null", "NULL", "nan", "NaN", "<NA>"}
    return s.replace({k: "" for k in invalid})

def _normalize_txt(t: str) -> str:
    if not isinstance(t, str):
        return ""
    t = t.strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join([c for c in t if not unicodedata.combining(c)])
    return " ".join(t.split())

def _parse_ts_series(raw: pd.Series) -> pd.Series:
    if raw is None or raw.empty:
        return pd.Series([], dtype="datetime64[ns]")
    tries = [
        pd.to_datetime(raw, format="%d/%m/%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, format="%d/%m/%Y", errors="coerce"),
        pd.to_datetime(raw, format="%d-%m-%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, format="%d-%m-%Y", errors="coerce"),
        pd.to_datetime(raw, errors="coerce"),
    ]
    out = tries[0]
    for cand in tries[1:]:
        out = out.fillna(cand)
    return out

def _fmt_dt_or_text(row) -> str:
    if pd.notna(row.get("TS_dt", pd.NaT)):
        return row["TS_dt"].strftime("%d/%m/%Y")
    # fallback para qualquer texto de TS
    for k in ("TS_raw", "TimeStamp", "Timestamp"):
        if k in row and str(row[k]).strip():
            try:
                dt = pd.to_datetime(str(row[k]), dayfirst=True, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%d/%m/%Y")
            except Exception:
                pass
    return "N/A"

def _status_logical(raw: str) -> str:
    s = "" if raw is None else str(raw).strip()
    low = s.lower()
    if low == "done":
        return "Done"
    if low == "requested":
        return "Requested"
    if s == "---":
        return "Not Requested"
    return "Pending"

# =========================
# Data loaders (cache)
# =========================
@st.cache_data(ttl=600)
def load_athletes() -> pd.DataFrame:
    """Carrega df de atletas e normaliza colunas mais usadas."""
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, MAIN_SHEET_NAME, ATHLETES_TAB_NAME)
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()
        # normaliza nomes das colunas como nas outras páginas
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        # filtros básicos
        if "role" not in df.columns or "inactive" not in df.columns:
            return pd.DataFrame()
        # inactive pode vir como texto/num
        if df["inactive"].dtype == "object":
            df["inactive"] = df["inactive"].astype(str).str.upper().map(
                {"FALSE": False, "TRUE": True, "": True}
            ).fillna(True)
        elif pd.api.types.is_numeric_dtype(df["inactive"]):
            df["inactive"] = df["inactive"].map({0: False, 1: True}).fillna(True)
        df = df[(df["role"] == "1 - Fighter") & (df["inactive"] == False)].copy()

        # preencher colunas usadas
        for c in ["event", "id", "name", "fight_number", "corner"]:
            if c not in df.columns:
                df[c] = ""
        df["event"] = df["event"].fillna(DEFAULT_EVENT)

        return df.sort_values(by=["event", "name"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading athletes: {e}", icon="🚨")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_attendance() -> pd.DataFrame:
    """Carrega Attendance respeitando os headers reais da planilha."""
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, MAIN_SHEET_NAME, ATTENDANCE_TAB)
        all_vals = ws.get_all_values()
        if not all_vals:
            return pd.DataFrame()
        headers = [h if h is not None else "" for h in (all_vals[0] if all_vals else [])]
        rows = all_vals[1:] if len(all_vals) > 1 else []
        df = pd.DataFrame(rows, columns=headers)

        # Garante as colunas que usamos:
        for col in ["Event", "Fighter", "Task", "Status", "User", "TimeStamp", "Timestamp", "Notes", "Athlete ID"]:
            if col not in df.columns:
                df[col] = ""
        # normalizações auxiliares
        df["fighter_norm"] = df["Fighter"].astype(str).apply(_normalize_txt)
        df["event_norm"]   = df["Event"].astype(str).apply(_normalize_txt)
        df["task_norm"]    = df["Task"].astype(str).str.strip().str.lower()
        df["status_norm"]  = df["Status"].astype(str).str.strip().str.lower()

        # timestamp preferindo TimeStamp
        t2 = df.get("TimeStamp")
        t1 = df.get("Timestamp")
        if t2 is None and t1 is None:
            df["TS_raw"] = ""
        else:
            s2 = _clean_str_series(t2) if t2 is not None else pd.Series([""]*len(df))
            s1 = _clean_str_series(t1) if t1 is not None else pd.Series([""]*len(df))
            df["TS_raw"] = s2.where(s2 != "", s1)
        df["TS_dt"] = _parse_ts_series(df["TS_raw"])
        return df
    except Exception as e:
        st.error(f"Error loading attendance: {e}", icon="🚨")
        return pd.DataFrame()

# =========================
# Status atual por atleta+evento para uma Task
# =========================
@st.cache_data(ttl=180)
def compute_status_for_task(task_name: str) -> pd.DataFrame:
    """Retorna um DF com status atual da task para cada atleta+evento."""
    df_a = load_athletes()
    df_att = load_attendance()
    if df_a.empty:
        return pd.DataFrame()

    base = df_a.copy()
    base["name_norm"]  = base["name"].apply(_normalize_txt)
    base["event_norm"] = base["event"].apply(_normalize_txt)

    if df_att.empty or not task_name:
        base["current_status"] = "Pending"
        base["latest_user"] = "N/A"
        base["latest_date"] = "N/A"
        return base

    # máscara de task (case-insensitive, aceita variações exatas)
    t_norm = task_name.strip().lower()
    df_task = df_att[df_att["task_norm"] == t_norm].copy()
    if df_task.empty:
        base["current_status"] = "Pending"
        base["latest_user"] = "N/A"
        base["latest_date"] = "N/A"
        return base

    df_task["__idx__"] = np.arange(len(df_task))

    merged = pd.merge(
        base,
        df_task,
        left_on=["name_norm", "event_norm"],
        right_on=["fighter_norm", "event_norm"],
        how="left",
        suffixes=("", "_att")
    ).sort_values(by=["name_norm", "event_norm", "TS_dt", "__idx__"], ascending=[True, True, False, False])

    latest = merged.drop_duplicates(subset=["name_norm", "event_norm"], keep="first")
    latest["current_status"] = latest["Status"].apply(_status_logical)
    latest["latest_user"]    = latest["User"].fillna("N/A")
    latest["latest_date"]    = latest.apply(_fmt_dt_or_text, axis=1)

    # mantém só colunas de exibição úteis
    keep_cols = [
        "id", "name", "event", "fight_number", "corner",
        "current_status", "latest_user", "latest_date"
    ]
    for c in keep_cols:
        if c not in latest.columns:
            latest[c] = ""
    return latest[keep_cols].reset_index(drop=True)

# =========================
# Writer (bulk log)
# =========================
def _append_by_header(ws, values: dict) -> None:
    """Alinha valores à ordem de cabeçalho atual; cria header padrão se vazio."""
    all_vals = ws.get_all_values()
    if not all_vals:
        header = ["#", "Event", "Athlete ID", "Name", "Fighter", "Task", "Status", "User", "Timestamp", "TimeStamp", "Notes"]
        ws.append_row(header, value_input_option="USER_ENTERED")
        header_row = header
    else:
        header_row = all_vals[0]

    next_num = len(all_vals) + 1  # inclui header
    rowvals = dict(values)
    rowvals.setdefault("#", str(next_num))
    aligned = [rowvals.get(h, "") for h in header_row]
    ws.append_row(aligned, value_input_option="USER_ENTERED")

def bulk_log(selected_rows: pd.DataFrame, task_name: str, status: str, note: str = "") -> int:
    """Grava uma linha por atleta selecionado na aba Attendance."""
    if selected_rows.empty:
        return 0
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, MAIN_SHEET_NAME, ATTENDANCE_TAB)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get("current_user_name", "System")

        n = 0
        for _, r in selected_rows.iterrows():
            values = {
                "Event":      str(r.get("event", "")),
                "Athlete ID": str(r.get("id", "")),
                "Name":       str(r.get("name", "")),
                "Fighter":    str(r.get("name", "")),
                "Task":       str(task_name),
                "Status":     str(status),
                "User":       user_ident,
                "Timestamp":  "",      # manter vazio
                "TimeStamp":  ts,      # escrever aqui
                "Notes":      note or "",
            }
            _append_by_header(ws, values)
            n += 1
        # refresh caches
        load_attendance.clear()
        compute_status_for_task.clear()
        return n
    except Exception as e:
        st.error(f"Error writing logs: {e}", icon="🚨")
        return 0

# =========================
# UI — Filtros
# =========================
tasks, _statuses = load_config_data()
if not tasks:
    tasks = ["Blood Test", "Photoshoot", "Video Shooting", "Walkout Music", "Stats"]  # fallback

# chaves únicas por página
K_TASK   = "tasktable_selected_task"
K_EVENT  = "tasktable_selected_event"
K_STAT   = "tasktable_selected_status"
K_SEARCH = "tasktable_search"

# defaults
st.session_state.setdefault(K_TASK, tasks[0])
st.session_state.setdefault(K_EVENT, "All Events")
st.session_state.setdefault(K_STAT, "All")
st.session_state.setdefault(K_SEARCH, "")

with st.expander("Settings", expanded=True):
    st.segmented_control(
        "Task:",
        options=tasks,
        key=K_TASK,
        help="Selecione a tarefa para visualizar/editar."
    )
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.segmented_control("Status:", options=["All", "Done", "Requested", "Not Requested", "Pending"], key=K_STAT)
    with c2:
        # eventos disponíveis
        df_a_for_events = load_athletes()
        event_opts = ["All Events"] + sorted([e for e in df_a_for_events["event"].unique() if e != DEFAULT_EVENT]) if not df_a_for_events.empty else ["All Events"]
        st.selectbox("Event:", options=event_opts, key=K_EVENT)
    with c3:
        st.text_input("Search (name or ID):", key=K_SEARCH)

# =========================
# Dados da task selecionada
# =========================
df = compute_status_for_task(st.session_state[K_TASK])
if not df.empty:
    # filtros
    if st.session_state[K_EVENT] != "All Events":
        df = df[df["event"] == st.session_state[K_EVENT]]

    q = st.session_state[K_SEARCH].strip().lower()
    if q:
        df = df[
            df["name"].str.lower().str.contains(q, na=False) |
            df["id"].astype(str).str.contains(q, na=False)
        ]

    if st.session_state[K_STAT] != "All":
        df = df[df["current_status"] == st.session_state[K_STAT]]

# =========================
# Botões em lote + Tabela editável com checkbox
# =========================
st.subheader(f"Records — {st.session_state[K_TASK]}")
left, mid, right = st.columns([1.2, 1.2, 6])

# placeholder para ações
_action = None
with left:
    if st.button("Done", type="primary", use_container_width=True):
        _action = "Done"
with mid:
    if st.button("Requested", use_container_width=True):
        _action = "Requested"
with right:
    if st.button("Not Requested", use_container_width=True):
        _action = "---"  # mantemos o padrão de escrita

# prepara df para edição (checkbox)
if df.empty:
    st.info("No records for the selected filters.")
else:
    df_view = df.copy()
    df_view.insert(0, "Select", False)
    # ordenação padrão: por fight_number e corner (blue antes de red)
    df_view["FNO"] = pd.to_numeric(df_view["fight_number"], errors="coerce").fillna(999)
    df_view["COR"] = df_view["corner"].astype(str).str.lower().map({"blue": 0, "red": 1}).fillna(2)
    df_view = df_view.sort_values(by=["event", "FNO", "COR", "name"]).drop(columns=["FNO", "COR"])

    edited = st.data_editor(
        df_view,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Select": st.column_config.CheckboxColumn(help="Mark rows to apply the bulk action"),
            "id":     st.column_config.TextColumn("ID", disabled=True),
            "name":   st.column_config.TextColumn("Name", disabled=True),
            "event":  st.column_config.TextColumn("Event", disabled=True),
            "fight_number": st.column_config.TextColumn("Fight", disabled=True),
            "corner": st.column_config.TextColumn("Corner", disabled=True),
            "current_status": st.column_config.TextColumn("Current Status", disabled=True),
            "latest_user":    st.column_config.TextColumn("Latest User", disabled=True),
            "latest_date":    st.column_config.TextColumn("Latest Date", disabled=True),
        },
        key="tasktable_editor",
    )

    # ação em lote (se houver)
    if _action is not None:
        selected = edited[edited["Select"] == True].copy()
        if selected.empty:
            st.warning("Select at least one row to apply the action.", icon="⚠️")
        else:
            status_to_write = "Not Requested" if _action == "---" else _action
            count = bulk_log(selected, st.session_state[K_TASK], status_to_write)
            if count > 0:
                st.success(f"{count} record(s) updated as '{status_to_write}'.", icon="✅")
                st.rerun()
