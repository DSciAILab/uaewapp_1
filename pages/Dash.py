[TODO: CONTINUAÇÃO DO CÓDIGO INTEGRADA ABAIXO]

# --- Continuação completa do script ---

# --- Constantes ---
MAIN_SHEET_NAME = "UAEW_App"
CONFIG_TAB_NAME = "Config"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
ATTENDANCE_TAB_NAME = "Attendance"
ATTENDANCE_ATHLETE_ID_COL = "Athlete ID"
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"

FC_EVENT_COL = "Event"
FC_FIGHTER_COL = "Fighter"
FC_ATHLETE_ID_COL = "AthleteID"
FC_CORNER_COL = "Corner"
FC_ORDER_COL = "FightOrder"
FC_PICTURE_COL = "Picture"
FC_DIVISION_COL = "Division"

TASK_EMOJI_MAP = {
    "Walkout Music": "🎵",
    "Stats": "📊",
    "Black Screen Video": "⬛",
    "Video Shooting": "🎥",
    "Photoshoot": "📸",
    "Blood Test": "🩸",
}

STATUS_INFO = {
    "Done": {"class": "status-done", "text": "Done"},
    "Requested": {"class": "status-requested", "text": "Requested"},
    "---": {"class": "status-neutral", "text": "---"},
    "Pending": {"class": "status-pending", "text": "Pending"},
    "Pendente": {"class": "status-pending", "text": "Pending"},
    "Não Registrado": {"class": "status-pending", "text": "Not Registered"},
    "Não Solicitado": {"class": "status-neutral", "text": "Not Requested"},
}
DEFAULT_STATUS_CLASS = "status-pending"

# --- Autenticação com Google Sheets ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    return gspread_client.open(sheet_name).worksheet(tab_name)

# --- Carregamento de dados ---
@st.cache_data
def load_fightcard_data():
    df = pd.read_csv(FIGHTCARD_SHEET_URL)
    df.columns = df.columns.str.strip()
    df[FC_ORDER_COL] = pd.to_numeric(df[FC_ORDER_COL], errors="coerce")
    df[FC_CORNER_COL] = df[FC_CORNER_COL].astype(str).str.strip().str.lower()
    df[FC_FIGHTER_COL] = df[FC_FIGHTER_COL].astype(str).str.strip()
    df[FC_PICTURE_COL] = df[FC_PICTURE_COL].astype(str).str.strip().fillna("")
    if FC_ATHLETE_ID_COL in df.columns:
        df[FC_ATHLETE_ID_COL] = df[FC_ATHLETE_ID_COL].astype(str).str.strip().fillna("")
    else:
        df[FC_ATHLETE_ID_COL] = ""
    return df.dropna(subset=[FC_FIGHTER_COL, FC_ORDER_COL, FC_ATHLETE_ID_COL])

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, tab_name=ATTENDANCE_TAB_NAME):
    client = get_gspread_client()
    ws = connect_gsheet_tab(client, sheet_name, tab_name)
    df = pd.DataFrame(ws.get_all_records())
    for col in [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL]:
        df[col] = df[col].astype(str).str.strip()
    return df

@st.cache_data(ttl=600)
def get_task_list(sheet_name=MAIN_SHEET_NAME, tab_name=CONFIG_TAB_NAME):
    client = get_gspread_client()
    ws = connect_gsheet_tab(client, sheet_name, tab_name)
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df["TaskList"].dropna().astype(str).str.strip().unique().tolist()

def get_task_status(athlete_id, task_name, df_att):
    if df_att.empty or not athlete_id or not task_name:
        return STATUS_INFO.get("Pending", {"class": DEFAULT_STATUS_CLASS, "text": "Pending"})
    filt = (
        df_att[ATTENDANCE_ATHLETE_ID_COL].str.strip() == str(athlete_id).strip()
    ) & (
        df_att[ATTENDANCE_TASK_COL].str.strip() == str(task_name).strip()
    )
    records = df_att[filt]
    if records.empty:
        return STATUS_INFO.get("Pending", {"class": DEFAULT_STATUS_CLASS, "text": "Pending"})
    latest = records.iloc[-1][ATTENDANCE_STATUS_COL]
    return STATUS_INFO.get(str(latest).strip(), {"class": DEFAULT_STATUS_CLASS, "text": latest})

def generate_dashboard_html(df, tasks):
    header = """
    <thead><tr>
        <th class='blue-corner-header' colspan='{0}'>BLUE CORNER</th>
        <th class='center-col-header' rowspan=2>FIGHT<br>INFO</th>
        <th class='red-corner-header' colspan='{0}'>RED CORNER</th>
    </tr><tr>
    """.format(len(tasks) + 2)
    for t in reversed(tasks): header += f"<th class='task-header'>{TASK_EMOJI_MAP.get(t, t[0])}</th>"
    header += "<th>Fighter</th><th>Photo</th><th>Photo</th><th>Fighter</th>"
    for t in tasks: header += f"<th class='task-header'>{TASK_EMOJI_MAP.get(t, t[0])}</th>"
    header += "</tr></thead>"

    body = "<tbody>"
    for _, row in df.iterrows():
        body += "<tr>"
        for t in reversed(tasks):
            s = row.get(f"{t} (Azul)", {"class": "", "text": ""})
            body += f"<td class='status-cell {s['class']}' title='{s['text']}'></td>"
        body += f"<td class='fighter-name fighter-name-blue'>{row['Lutador Azul']}</td>"
        body += f"<td class='photo-cell'><img class='fighter-img' src='{row['Foto Azul']}'/></td>"
        body += f"<td class='center-info-cell'><div class='fight-info-number'>{row['Fight #']}</div><div class='fight-info-event'>{row['Event']}</div><div class='fight-info-division'>{row['Division']}</div></td>"
        body += f"<td class='photo-cell'><img class='fighter-img' src='{row['Foto Vermelho']}'/></td>"
        body += f"<td class='fighter-name fighter-name-red'>{row['Lutador Vermelho']}</td>"
        for t in tasks:
            s = row.get(f"{t} (Vermelho)", {"class": "", "text": ""})
            body += f"<td class='status-cell {s['class']}' title='{s['text']}'></td>"
        body += "</tr>"
    body += "</tbody>"
    return f"<div class='dashboard-container'><table class='dashboard-table'>{header}{body}</table></div>"

# --- Execução do dashboard ---
df_fc = load_fightcard_data()
df_att = load_attendance_data()
tasks = get_task_list()

if df_fc.empty or not tasks:
    st.warning("Dados do Fightcard ou TaskList não carregados.")
    st.stop()

fight_data = []
for (event, order), group in df_fc.groupby([FC_EVENT_COL, FC_ORDER_COL]):
    row = {"Event": event, "Fight #": int(order)}
    blue = group[group[FC_CORNER_COL] == "blue"].squeeze()
    red = group[group[FC_CORNER_COL] == "red"].squeeze()
    for side, data in [("Azul", blue), ("Vermelho", red)]:
        row[f"Lutador {side}"] = data.get(FC_FIGHTER_COL, "N/A")
        row[f"Foto {side}"] = data.get(FC_PICTURE_COL, "")
        aid = data.get(FC_ATHLETE_ID_COL, "")
        for task in tasks:
            row[f"{task} ({side})"] = get_task_status(aid, task, df_att)
    row["Division"] = blue.get(FC_DIVISION_COL, red.get(FC_DIVISION_COL, ""))
    fight_data.append(row)

df_final = pd.DataFrame(fight_data)
st.markdown(generate_dashboard_html(df_final, tasks), unsafe_allow_html=True)

st.markdown(f"<p style='font-size: 0.8em; text-align: center; color: #888;'>*Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*</p>", unsafe_allow_html=True)
