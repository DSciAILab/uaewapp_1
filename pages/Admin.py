# pages/11_Task_Table.py
from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import unicodedata

# utils base (recomendado: @st.cache_resource dentro de utils)
from utils import get_gspread_client, connect_gsheet_tab, load_config_data

# =========================
# Toggle de performance (fusível)
# =========================
USE_FAST_APPEND = True  # True = append em lote (rápido) | False = modo antigo (append por linha)

# =========================
# Bootstrap (config + auth + sidebar)
# =========================
bootstrap_page("Task Table")
st.title("Task Table")

# =========================
# Constantes
# =========================
MAIN_SHEET_NAME   = "UAEW_App"
ATHLETES_TAB_NAME = "df"
ATTENDANCE_TAB    = "Attendance"
DEFAULT_EVENT     = "Z"

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
    for k in ("TS_raw", "TimeStamp", "Timestamp"):
        if k in row and str(row[k]).strip():
            dt = pd.to_datetime(str(row[k]), dayfirst=True, errors="coerce")
            if pd.notna(dt):
                return dt.strftime("%d/%m/%Y")
    return "N/A"

def _status_logical(raw: str) -> str:
    s = "" if raw is None else str(raw).strip()
    low = s.lower()
    if low == "done": return "Done"
    if low == "requested": return "Requested"
    if s == "---": return "---"
    return "Pending"

# =========================
# Data loaders (cache)
# =========================
@st.cache_data(ttl=600)
def load_athletes() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, MAIN_SHEET_NAME, ATHLETES_TAB_NAME)
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()

        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        if "role" not in df.columns or "inactive" not in df.columns:
            return pd.DataFrame()

        if df["inactive"].dtype == "object":
            df["inactive"] = df["inactive"].astype(str).str.upper().map(
                {"FALSE": False, "TRUE": True, "": True}
            ).fillna(True)
        elif pd.api.types.is_numeric_dtype(df["inactive"]):
            df["inactive"] = df["inactive"].map({0: False, 1: True}).fillna(True)

        df = df[(df["role"] == "1 - Fighter") & (df["inactive"] == False)].copy()

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
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, MAIN_SHEET_NAME, ATTENDANCE_TAB)
        all_vals = ws.get_all_values()
        if not all_vals:
            return pd.DataFrame()
        headers = [h if h is not None else "" for h in (all_vals[0] if all_vals else [])]
        rows = all_vals[1:] if len(all_vals) > 1 else []
        df = pd.DataFrame(rows, columns=headers)

        for col in ["Event", "Fighter", "Task", "Status", "User", "TimeStamp", "Timestamp", "Notes", "Athlete ID"]:
            if col not in df.columns:
                df[col] = ""

        df["fighter_norm"] = df["Fighter"].astype(str).apply(_normalize_txt)
        df["event_norm"]   = df["Event"].astype(str).apply(_normalize_txt)
        df["task_norm"]    = df["Task"].astype(str).str.strip().str.lower()
        df["status_norm"]  = df["Status"].astype(str).str.strip().str.lower()

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
# Índice cacheado (último status por grupo)
# =========================
@st.cache_data(ttl=120)
def build_attendance_index() -> pd.DataFrame:
    """Último registro por (event_norm, fighter_norm, task_norm)."""
    df_att = load_attendance()
    if df_att.empty:
        return pd.DataFrame()

    idx_cols = ["event_norm", "fighter_norm", "task_norm"]
    df_sorted = df_att.sort_values(by=["TS_dt"], ascending=False)
    latest = df_sorted.drop_duplicates(subset=idx_cols, keep="first")

    keep = idx_cols + ["Status", "User", "TS_dt", "TS_raw"]
    for c in keep:
        if c not in latest.columns:
            latest[c] = ""
    return latest[keep].reset_index(drop=True)

# =========================
# Status por task / All (cacheados)
# =========================
@st.cache_data(ttl=120)
def compute_status_for_task(task_name: str) -> pd.DataFrame:
    df_a = load_athletes()
    if df_a.empty:
        return pd.DataFrame()

    base = df_a.copy()
    base["name_norm"]  = base["name"].apply(_normalize_txt)
    base["event_norm"] = base["event"].apply(_normalize_txt)

    idx = build_attendance_index()
    if idx.empty or not task_name:
        base["current_status"] = "Pending"
        base["latest_user"] = "N/A"
        base["latest_date"] = "N/A"
        return base[["id","name","event","fight_number","corner","current_status","latest_user","latest_date"]]

    t_norm = task_name.strip().lower()
    idx_t = idx[idx["task_norm"] == t_norm]

    merged = pd.merge(
        base,
        idx_t,
        left_on=["name_norm", "event_norm"],
        right_on=["fighter_norm", "event_norm"],
        how="left"
    )

    merged["current_status"] = merged["Status"].apply(_status_logical)
    merged["latest_user"]    = merged["User"].fillna("N/A")

    def _fmt_row(row):
        if pd.notna(row.get("TS_dt", pd.NaT)):
            return row["TS_dt"].strftime("%d/%m/%Y")
        raw = str(row.get("TS_raw", "")).strip()
        if raw:
            dt = pd.to_datetime(raw, dayfirst=True, errors="coerce")
            if pd.notna(dt): return dt.strftime("%d/%m/%Y")
        return "N/A"

    merged["latest_date"] = merged.apply(_fmt_row, axis=1)

    keep_cols = ["id","name","event","fight_number","corner","current_status","latest_user","latest_date"]
    for c in keep_cols:
        if c not in merged.columns: merged[c] = ""
    return merged[keep_cols].reset_index(drop=True)

@st.cache_data(ttl=120)
def compute_status_for_all(tasks: list[str]) -> pd.DataFrame:
    dfs = []
    for t in tasks:
        dft = compute_status_for_task(t)
        if not dft.empty:
            dft = dft.copy()
            dft["task"] = t
            dfs.append(dft)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# =========================
# View filtrada + ordenada (cache)
# =========================
@st.cache_data(ttl=60)
def get_filtered_view(df: pd.DataFrame, event_filter: str, status_filter: str, q: str, sel_task: str) -> pd.DataFrame:
    if df.empty:
        return df

    out = df
    if event_filter != "All Events":
        out = out[out["event"] == event_filter]

    q = (q or "").strip().lower()
    if q:
        out = out[
            out["name"].str.lower().str.contains(q, na=False) |
            out["id"].astype(str).str.contains(q, na=False)
        ]

    if status_filter != "All":
        out = out[out["current_status"] == status_filter]

    out = out.copy()
    out["FNO"] = pd.to_numeric(out["fight_number"], errors="coerce").fillna(999)
    out["COR"] = out["corner"].astype(str).str.lower().map({"blue": 0, "red": 1}).fillna(2)
    sort_keys = ["event", "FNO", "COR", "name"]
    if sel_task == "All" and "task" in out.columns:
        sort_keys = ["task"] + sort_keys
    out = out.sort_values(by=sort_keys).drop(columns=["FNO", "COR"])
    return out.reset_index(drop=True)

# =========================
# Writer — duas versões (FAST e LEGACY)
# =========================
def _ensure_header_and_get_next(ws):
    """Garante header e retorna (header_row, next_row_number)."""
    all_vals = ws.get_all_values()
    if not all_vals:
        header = ["#", "Event", "Athlete ID", "Name", "Fighter", "Task", "Status", "User", "Timestamp", "TimeStamp", "Notes"]
        ws.update("A1", [header], value_input_option="USER_ENTERED")
        return header, 2
    else:
        header_row = all_vals[0]
        next_row = len(all_vals) + 1
        return header_row, next_row

def _append_by_header_legacy(ws, values: dict) -> None:
    """Modo antigo: alinha e dá append_row (mais lento)."""
    all_vals = ws.get_all_values()
    if not all_vals:
        header = ["#", "Event", "Athlete ID", "Name", "Fighter", "Task", "Status", "User", "Timestamp", "TimeStamp", "Notes"]
        ws.append_row(header, value_input_option="USER_ENTERED")
        header_row = header
    else:
        header_row = all_vals[0]

    next_num = len(all_vals) + 1
    rowvals = dict(values)
    rowvals.setdefault("#", str(next_num))
    aligned = [rowvals.get(h, "") for h in header_row]
    ws.append_row(aligned, value_input_option="USER_ENTERED")

def bulk_log_fast(selected_rows: pd.DataFrame, task_name: str, status: str, note: str = "") -> int:
    """FAST: 1 chamada com values_append."""
    if selected_rows.empty:
        return 0
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, MAIN_SHEET_NAME, ATTENDANCE_TAB)
        header_row, next_row = _ensure_header_and_get_next(ws)

        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get("current_user_name", "System")

        rows_to_append = []
        num = next_row
        for _, r in selected_rows.iterrows():
            rowvals = {
                "#": str(num),
                "Event":      str(r.get("event", "")),
                "Athlete ID": str(r.get("id", "")),
                "Name":       str(r.get("name", "")),
                "Fighter":    str(r.get("name", "")),
                "Task":       str(task_name),
                "Status":     str(status),  # '---' já vem quando Not Requested
                "User":       user_ident,
                "Timestamp":  "",
                "TimeStamp":  ts,
                "Notes":      note or "",
            }
            rows_to_append.append([rowvals.get(h, "") for h in header_row])
            num += 1

        # uma única chamada
        ws.spreadsheet.values_append(
            f"{ATTENDANCE_TAB}!A1",
            params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
            body={"values": rows_to_append},
        )
        return len(rows_to_append)
    except Exception as e:
        st.error(f"Error writing logs: {e}", icon="🚨")
        return 0

def bulk_log_legacy(selected_rows: pd.DataFrame, task_name: str, status: str, note: str = "") -> int:
    """LEGACY: append_row por linha."""
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
                "Status":     str(status),  # '---' quando Not Requested
                "User":       user_ident,
                "Timestamp":  "",
                "TimeStamp":  ts,
                "Notes":      note or "",
            }
            _append_by_header_legacy(ws, values)
            n += 1
        return n
    except Exception as e:
        st.error(f"Error writing logs: {e}", icon="🚨")
        return 0

def bulk_log(selected_rows: pd.DataFrame, task_name: str, status: str, note: str = "") -> int:
    """Chama FAST ou LEGACY conforme o fusível."""
    count = bulk_log_fast(selected_rows, task_name, status, note) if USE_FAST_APPEND else bulk_log_legacy(selected_rows, task_name, status, note)
    if count > 0:
        # invalidação mínima (reidrata status rapidamente)
        load_attendance.clear()
        build_attendance_index.clear()
        compute_status_for_task.clear()
        compute_status_for_all.clear()
    return count

# =========================
# UI — Filtros
# =========================
tasks, _statuses = load_config_data()
if not tasks:
    tasks = ["Blood Test", "Photoshoot", "Video Shooting", "Walkout Music", "Stats"]

task_options = ["All"] + tasks

K_TASK   = "tasktable_selected_task"
K_EVENT  = "tasktable_selected_event"
K_STAT   = "tasktable_selected_status"
K_SEARCH = "tasktable_search"

st.session_state.setdefault(K_TASK, "All")
st.session_state.setdefault(K_EVENT, "All Events")
st.session_state.setdefault(K_STAT, "All")
st.session_state.setdefault(K_SEARCH, "")

with st.expander("Settings", expanded=True):
    st.segmented_control(
        "Task:",
        options=task_options,
        key=K_TASK,
        help="Selecione a tarefa para visualizar/editar."
    )
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.segmented_control("Status:", options=["All", "Done", "Requested", "Not Requested", "Pending"], key=K_STAT)
    with c2:
        df_a_for_events = load_athletes()
        event_opts = ["All Events"] + sorted([e for e in df_a_for_events["event"].unique() if e != DEFAULT_EVENT]) if not df_a_for_events.empty else ["All Events"]
        st.selectbox("Event:", options=event_opts, key=K_EVENT)
    with c3:
        st.text_input("Search (name or ID):", key=K_SEARCH)

# =========================
# Dados (suporta "All")
# =========================
sel_task = st.session_state[K_TASK]
if sel_task == "All":
    df = compute_status_for_all(tasks)
else:
    df = compute_status_for_task(sel_task)
    if not df.empty:
        df = df.copy()
        df["task"] = sel_task

# filtros cacheados
df_view = get_filtered_view(
    df=df,
    event_filter=st.session_state[K_EVENT],
    status_filter=st.session_state[K_STAT],
    q=st.session_state[K_SEARCH],
    sel_task=sel_task,
)

# =========================
# Botões + Tabela
# =========================
title_task = "All" if sel_task == "All" else sel_task
st.subheader(f"Records — {title_task}")
left, mid, right = st.columns([1.2, 1.2, 6])

_action = None
with left:
    if st.button("Done", type="primary", use_container_width=True):
        _action = "Done"
with mid:
    if st.button("Requested", use_container_width=True):
        _action = "Requested"
with right:
    if st.button("Not Requested", use_container_width=True):
        _action = "---"  # gravar exatamente '---'

if df_view.empty:
    st.info("No records for the selected filters.")
else:
    # Selecionar todos visíveis
    select_all_visible = st.checkbox("Select all visible", value=False)

    df_edit = df_view.copy()
    df_edit.insert(0, "Select", bool(select_all_visible))

    # Altura dinâmica
    rows_to_show = min(len(df_edit), 30)
    row_height   = 35
    extra_pad    = 120
    table_height = rows_to_show * row_height + extra_pad

    edited = st.data_editor(
        df_edit,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        height=table_height,
        column_config={
            "Select": st.column_config.CheckboxColumn(help="Mark rows to apply the bulk action"),
            "task":   st.column_config.TextColumn("Task", disabled=True),
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

    # Aplicar ação em lote
    if _action is not None:
        selected = edited[edited["Select"] == True].copy()
        if selected.empty:
            st.warning("Select at least one row to apply the action.", icon="⚠️")
        else:
            status_to_write = "---" if _action == "---" else _action
            if sel_task == "All" and "task" in selected.columns:
                total = 0
                for t, chunk in selected.groupby("task"):
                    total += bulk_log(chunk, t, status_to_write)
                if total > 0:
                    st.success(f"{total} record(s) updated.", icon="✅")
                    st.rerun()
            else:
                count = bulk_log(selected, sel_task, status_to_write)
                if count > 0:
                    st.success(f"{count} record(s) updated as '{status_to_write}'.", icon="✅")
                    st.rerun()
