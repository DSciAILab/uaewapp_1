# ==============================================================================
# PHOTOSHOOT MANAGEMENT SYSTEM - STREAMLIT APP
# ==============================================================================

# --- 0. Import Libraries ---
import streamlit as st
st.set_page_config(page_title="Photoshoot", layout="wide")  # manter como primeira chamada de UI

import pandas as pd
import numpy as np
from datetime import datetime
import html
import time
import unicodedata
import re

# --- Importações do Projeto ---
from utils import get_gspread_client, connect_gsheet_tab, load_users_data, get_valid_user_info, load_config_data
from auth import check_authentication, display_user_sidebar


# ==============================================================================
# CONSTANTES E CONFIGURAÇÕES
# ==============================================================================
class Config:
    """Classe para centralizar todas as constantes do aplicativo."""
    MAIN_SHEET_NAME = "UAEW_App"
    ATHLETES_TAB_NAME = "df"
    ATTENDANCE_TAB_NAME = "Attendance"

    # >>> Tarefa fixa desta página <<<
    FIXED_TASK = "Photoshoot"

    # Aliases/variações que podem aparecer nos logs
    TASK_ALIASES = [r"\bphoto\s*shoot\b", r"\bphotoshoot\b", r"\bphoto\b"]

    # Status lógicos:
    STATUS_PENDING = ""            # pendente/sem registro ou registro com status vazio
    STATUS_NOT_NEEDED = "---"      # explicitamente sem necessidade
    STATUS_REQUESTED = "Requested"
    STATUS_DONE = "Done"

    # Equivalências usadas em badges/cores
    ALL_LOGICAL_STATUSES = [STATUS_PENDING, STATUS_NOT_NEEDED, STATUS_REQUESTED, STATUS_DONE]

    STATUS_COLOR_MAP = {
        STATUS_DONE: "#143d14",
        STATUS_REQUESTED: "#B08D00",
        STATUS_PENDING: "#1e1e1e",     # pendente (sem solicitação)
        STATUS_NOT_NEEDED: "#6c757d",  # não precisa
        # Mapeamentos adicionais para o caso de status brutos ou labels
        "Pending": "#1e1e1e",
        "Not Registred": "#1e1e1e",
        "Issue": "#1e1e1e"
    }

    # Constantes para nomes de colunas (melhora a manutenibilidade)
    COL_ID = "id"
    COL_NAME = "name"
    COL_EVENT = "event"
    COL_ROLE = "role"
    COL_INACTIVE = "inactive"
    COL_IMAGE = "image"
    COL_MOBILE = "mobile"
    COL_FIGHT_NUMBER = "fight_number"
    COL_CORNER = "corner"
    COL_PASSPORT_IMAGE = "passport_image"
    COL_ROOM = "room"

    # Colunas de presença
    ATT_COL_EVENT = "Event"
    ATT_COL_NAME = "Name"
    ATT_COL_FIGHTER = "Fighter"
    ATT_COL_TASK = "Task"
    ATT_COL_STATUS = "Status"
    ATT_COL_USER = "User"
    ATT_COL_TIMESTAMP = "Timestamp"
    ATT_COL_TIMESTAMP_ALT = "TimeStamp" # Gspread pode retornar "TimeStamp" ou "Timestamp"
    ATT_COL_NOTES = "Notes"
    ATT_COL_ID = "#"

    DEFAULT_EVENT_PLACEHOLDER = "Z" # Valor padrão para eventos não especificados

    @staticmethod
    def map_raw_status_to_config(raw_status: str) -> str:
        """
        Mapeia um status bruto da planilha para uma das constantes de status da Config.
        Args:
            raw_status (str): Status lido da planilha (pode ser vazio, 'Requested', 'Done', '---', etc.).
        Returns:
            str: O status correspondente da Config.
        """
        raw_status = "" if raw_status is None else str(raw_status).strip()
        raw_status_low = raw_status.lower()
        if raw_status_low == Config.STATUS_DONE.lower():
            return Config.STATUS_DONE
        if raw_status_low == Config.STATUS_REQUESTED.lower():
            return Config.STATUS_REQUESTED
        if raw_status == Config.STATUS_NOT_NEEDED: # '---' deve ser exato
            return Config.STATUS_NOT_NEEDED
        # Qualquer outra coisa (incluindo vazio) é considerada pendente
        return Config.STATUS_PENDING


# ==============================================================================
# FUNÇÕES AUXILIARES (UTILITÁRIOS)
# ==============================================================================
_INVALID_STRS = {"", "none", "None", "null", "NULL", "nan", "NaN", "<NA>"}

def clean_and_normalize(text: str) -> str:
    """
    Normaliza uma string de texto: remove acentos, converte para minúsculas e remove espaços extras.
    Args:
        text (str): Texto a ser normalizado.
    Returns:
        str: Texto normalizado.
    """
    if not isinstance(text, str):
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    return " ".join(text.split())

def parse_ts_series(raw: pd.Series) -> pd.Series:
    """
    Tenta múltiplos formatos de data/hora e retorna uma série datetime.
    Args:
        raw (pd.Series): Série com strings de data/hora.
    Returns:
        pd.Series: Série convertida para datetime.
    """
    if raw is None or raw.empty:
        return pd.Series([], dtype='datetime64[ns]')
    
    tries = [
        pd.to_datetime(raw, format="%d/%m/%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, format="%d/%m/%Y", errors="coerce"),
        pd.to_datetime(raw, format="%d-%m-%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, format="%d-%m-%Y", errors="coerce"),
        pd.to_datetime(raw, errors="coerce"),  # fallback ISO
    ]
    ts_final = tries[0]
    for cand in tries[1:]:
        ts_final = ts_final.fillna(cand)
    return ts_final

def _clean_str_series(s: pd.Series) -> pd.Series:
    """Limpa uma série de strings, removendo valores inválidos."""
    if s is None or s.empty:
        return pd.Series([], dtype=str)
    s = s.fillna("").astype(str).str.strip()
    return s.replace({k: "" for k in _INVALID_STRS})

def _fmt_date_from_text(s: str) -> str:
    """
    Formata qualquer texto de data/horário para dd/mm/aaaa; se inválido, 'N/A'.
    Args:
        s (str): Texto de data/hora.
    Returns:
        str: Data formatada ou 'N/A'.
    """
    if s is None:
        return "N/A"
    s = str(s).strip()
    if s in _INVALID_STRS:
        return "N/A"
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return dt.strftime("%d/%m/%Y") if pd.notna(dt) else "N/A"

def make_task_mask(task_series: pd.Series, fixed_task: str, aliases: list[str] = None) -> pd.Series:
    """
    Cria uma máscara booleana para localizar registros da tarefa (com aliases).
    Args:
        task_series (pd.Series): Série com os nomes das tarefas (normalizados).
        fixed_task (str): Nome da tarefa fixa.
        aliases (list[str]): Lista de expressões (regex) alternativas para casar a tarefa.
    Returns:
        pd.Series: Série booleana indicando as linhas que casam.
    """
    t = task_series.fillna("").astype(str).str.lower()
    pats = [re.escape(fixed_task.lower())]
    for al in aliases or []:
        pats.append(al)
    regex = "(" + "|".join(pats) + ")"
    return t.str.contains(regex, regex=True, na=False)


# ==============================================================================
# FUNÇÕES DE CARREGAMENTO DE DADOS (COM CACHE)
# ==============================================================================
@st.cache_data(ttl=600)
def load_athlete_data(sheet_name: str = Config.MAIN_SHEET_NAME, athletes_tab_name: str = Config.ATHLETES_TAB_NAME) -> pd.DataFrame:
    """
    Carrega os dados dos atletas da planilha, aplicando filtros e normalizações.
    Args:
        sheet_name (str): Nome da planilha principal.
        athletes_tab_name (str): Nome da aba com dados dos atletas.
    Returns:
        pd.DataFrame: DataFrame com dados dos atletas.
    """
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, athletes_tab_name)
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(col).strip().lower().replace(' ', '_') for col in df.columns]

        # Usar constantes para nomes de colunas
        if Config.COL_ROLE not in df.columns or Config.COL_INACTIVE not in df.columns:
            st.error(f"Colunas '{Config.COL_ROLE.upper()}'/'{Config.COL_INACTIVE.upper()}' não encontradas em '{athletes_tab_name}'.", icon="🚨")
            return pd.DataFrame()

        if df[Config.COL_INACTIVE].dtype == 'object':
            df[Config.COL_INACTIVE] = df[Config.COL_INACTIVE].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        elif pd.api.types.is_numeric_dtype(df[Config.COL_INACTIVE]):
            df[Config.COL_INACTIVE] = df[Config.COL_INACTIVE].map({0: False, 1: True}).fillna(True)

        df = df[(df[Config.COL_ROLE] == "1 - Fighter") & (df[Config.COL_INACTIVE] == False)].copy()

        df[Config.COL_EVENT] = df[Config.COL_EVENT].fillna(Config.DEFAULT_EVENT_PLACEHOLDER) if Config.COL_EVENT in df.columns else Config.DEFAULT_EVENT_PLACEHOLDER
        for col_check in [Config.COL_IMAGE, Config.COL_MOBILE, Config.COL_FIGHT_NUMBER, Config.COL_CORNER, Config.COL_PASSPORT_IMAGE, Config.COL_ROOM]:
            if col_check not in df.columns:
                df[col_check] = ""
            else:
                df[col_check] = df[col_check].fillna("")

        if Config.COL_NAME not in df.columns:
            st.error(f"'{Config.COL_NAME.upper()}' não encontrada em '{athletes_tab_name}'.", icon="🚨")
            return pd.DataFrame()

        return df.sort_values(by=[Config.COL_EVENT, Config.COL_NAME]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar atletas (gspread): {e}", icon="🚨")
        return pd.DataFrame()


@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = Config.MAIN_SHEET_NAME, attendance_tab_name: str = Config.ATTENDANCE_TAB_NAME) -> pd.DataFrame:
    """
    Carrega os dados de presença da planilha.
    Args:
        sheet_name (str): Nome da planilha principal.
        attendance_tab_name (str): Nome da aba com dados de presença.
    Returns:
        pd.DataFrame: DataFrame com dados de presença.
    """
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty:
            return pd.DataFrame(columns=[
                Config.ATT_COL_ID, Config.ATT_COL_EVENT, Config.ATT_COL_NAME, Config.ATT_COL_FIGHTER,
                Config.ATT_COL_TASK, Config.ATT_COL_STATUS, Config.ATT_COL_USER,
                Config.ATT_COL_TIMESTAMP, Config.ATT_COL_TIMESTAMP_ALT, Config.ATT_COL_NOTES
            ])
        # Garantir que todas as colunas esperadas existam
        for col in [
            Config.ATT_COL_ID, Config.ATT_COL_EVENT, Config.ATT_COL_NAME, Config.ATT_COL_FIGHTER,
            Config.ATT_COL_TASK, Config.ATT_COL_STATUS, Config.ATT_COL_USER,
            Config.ATT_COL_TIMESTAMP, Config.ATT_COL_TIMESTAMP_ALT, Config.ATT_COL_NOTES
        ]:
            if col not in df_att.columns:
                df_att[col] = pd.NA
        return df_att
    except Exception as e:
        st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨")
        return pd.DataFrame()


# ==============================================================================
# FUNÇÕES DE PROCESSAMENTO DE DADOS
# ==============================================================================
@st.cache_data(ttl=120)
def preprocess_attendance(df_attendance: pd.DataFrame) -> pd.DataFrame:
    """
    Pré-processa o DataFrame de presença: normaliza colunas e tenta converter timestamps.
    Args:
        df_attendance (pd.DataFrame): DataFrame bruto de presença.
    Returns:
        pd.DataFrame: DataFrame pré-processado.
    """
    if df_attendance is None or df_attendance.empty:
        return pd.DataFrame()
    df = df_attendance.copy()
    df["fighter_norm"] = df.get(Config.ATT_COL_FIGHTER, "").astype(str).apply(clean_and_normalize)
    df["event_norm"]   = df.get(Config.ATT_COL_EVENT, "").astype(str).apply(clean_and_normalize)
    df["task_norm"]    = df.get(Config.ATT_COL_TASK, "").astype(str).str.strip().str.lower()
    df["status_norm"]  = df.get(Config.ATT_COL_STATUS, "").astype(str).str.strip().str.lower()

    # Prioriza 'TimeStamp' e usa 'Timestamp' como fallback
    t2 = df.get(Config.ATT_COL_TIMESTAMP_ALT)
    t1 = df.get(Config.ATT_COL_TIMESTAMP)
    if t2 is None and t1 is None:
        df["TS_raw"] = ""
    else:
        s2 = _clean_str_series(t2) if t2 is not None else pd.Series([""]*len(df))
        s1 = _clean_str_series(t1) if t1 is not None else pd.Series([""]*len(df))
        df["TS_raw"] = s2.where(s2 != "", s1)

    df["TS_dt"] = parse_ts_series(df["TS_raw"])
    return df


def get_all_athletes_status(df_athletes: pd.DataFrame, df_attendance: pd.DataFrame, fixed_task: str) -> pd.DataFrame:
    """
    Obtém o status atual da tarefa fixa para todos os atletas, processando em massa.
    Args:
        df_athletes (pd.DataFrame): DataFrame de atletas.
        df_attendance (pd.DataFrame): DataFrame de presença pré-processado.
        fixed_task (str): Nome da tarefa fixa (ex: "Photoshoot").
    Returns:
        pd.DataFrame: DataFrame com colunas de status adicionadas.
    """
    if df_athletes is None or df_athletes.empty:
        return pd.DataFrame(columns=[
            Config.COL_NAME, Config.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp'
        ])

    base = df_athletes.copy()
    base['name_norm'] = base[Config.COL_NAME].apply(clean_and_normalize)
    base['event_norm'] = base[Config.COL_EVENT].apply(clean_and_normalize)

    if df_attendance is None or df_attendance.empty:
        base['current_task_status'] = Config.STATUS_PENDING
        base['latest_task_user'] = 'N/A'
        base['latest_task_timestamp'] = 'N/A'
        return base[[Config.COL_NAME, Config.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]

    task_mask = make_task_mask(df_attendance["task_norm"], fixed_task, Config.TASK_ALIASES)
    df_task = df_attendance[task_mask].copy()

    if df_task.empty:
        base['current_task_status'] = Config.STATUS_PENDING
        base['latest_task_user'] = 'N/A'
        base['latest_task_timestamp'] = 'N/A'
        return base[[Config.COL_NAME, Config.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]

    df_task["__idx__"] = np.arange(len(df_task))

    merged = pd.merge(
        base[[Config.COL_NAME, Config.COL_EVENT, 'name_norm', 'event_norm']],
        df_task,
        left_on=['name_norm', 'event_norm'],
        right_on=['fighter_norm', 'event_norm'],
        how='left'
    )

    merged = merged.sort_values(
        by=['name_norm', 'event_norm', 'TS_dt', '__idx__'],
        ascending=[True, True, False, False]
    )

    latest_records = merged.drop_duplicates(subset=['name_norm', 'event_norm'], keep='first')

    # Usar o método estático da Config para mapear o status
    latest_records['current_task_status'] = latest_records[Config.ATT_COL_STATUS].apply(Config.map_raw_status_to_config)
    latest_records['latest_task_timestamp'] = latest_records.apply(
        lambda row: row['TS_dt'].strftime("%d/%m/%Y") if pd.notna(row.get('TS_dt', pd.NaT))
        else _fmt_date_from_text(row.get('TS_raw', row.get(Config.ATT_COL_TIMESTAMP_ALT, row.get(Config.ATT_COL_TIMESTAMP, '')))),
        axis=1
    )
    latest_records['latest_task_user'] = latest_records[Config.ATT_COL_USER].fillna('N/A')

    return latest_records[[Config.COL_NAME, Config.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]


@st.cache_data(ttl=600)
def last_task_other_event_by_name(
    df_attendance: pd.DataFrame,
    athlete_name: str,
    current_event: str,
    fixed_task: str,
    aliases: list[str],
    fallback_any_event: bool = True
) -> tuple[str, str]:
    """
    Retorna a data e o evento do último registro (Done) da tarefa fixa em OUTRO evento.
    Args:
        df_attendance (pd.DataFrame): DataFrame de presença pré-processado.
        athlete_name (str): Nome do atleta.
        current_event (str): Evento atual do atleta.
        fixed_task (str): Nome da tarefa fixa.
        aliases (list[str]): Aliases da tarefa fixa.
        fallback_any_event (bool): Se True, busca em qualquer evento se não encontrar em outro.
    Returns:
        tuple[str, str]: Data formatada e nome do evento.
    """
    if df_attendance is None or df_attendance.empty:
        return "N/A", ""

    name_n = clean_and_normalize(athlete_name)
    evt_n  = clean_and_normalize(current_event)

    task_is = make_task_mask(df_attendance["task_norm"], fixed_task, aliases)
    # Usar o status normalizado para 'Done'
    status_done = df_attendance["status_norm"].str.fullmatch(Config.STATUS_DONE.lower(), case=False, na=False)
    base_mask = (df_attendance["fighter_norm"] == name_n) & task_is & status_done

    cand = df_attendance[base_mask & (df_attendance["event_norm"] != evt_n)].copy()
    if not cand.empty:
        cand["__idx__"] = np.arange(len(cand))
        cand = cand.sort_values(by=["TS_dt", "__idx__"], ascending=[False, False])

    if cand.empty and fallback_any_event:
        cand = df_attendance[base_mask].copy()
        if not cand.empty:
            cand["__idx__"] = np.arange(len(cand))
            cand = cand.sort_values(by=["TS_dt", "__idx__"], ascending=[False, False])

    if cand.empty:
        return "N/A", ""

    row = cand.iloc[0]
    ev_label = str(row.get(Config.ATT_COL_EVENT, "")).strip()
    if pd.notna(row.get("TS_dt", pd.NaT)):
        dt_str = row["TS_dt"].strftime("%d/%m/%Y")
    else:
        dt_str = _fmt_date_from_text(row.get("TS_raw", row.get(Config.ATT_COL_TIMESTAMP_ALT, row.get(Config.ATT_COL_TIMESTAMP, ""))))
    return dt_str, ev_label


# ==============================================================================
# FUNÇÕES DE RENDERIZAÇÃO DE UI
# ==============================================================================
def render_athlete_card(row: pd.Series, last_info: tuple[str, str], badges_html: str) -> str:
    """
    Gera o HTML para o card de um atleta.
    Args:
        row (pd.Series): Linha do DataFrame com dados do atleta.
        last_info (tuple[str, str]): Tuple (data, evento) do último registro da tarefa.
        badges_html (str): HTML com os badges de outras tarefas.
    Returns:
        str: String HTML do card.
    """
    ath_id_d = str(row.get(Config.COL_ID, ""))
    ath_name_d = str(row.get(Config.COL_NAME, ""))
    ath_event_d = str(row.get(Config.COL_EVENT, ""))
    ath_fight_number = str(row.get(Config.COL_FIGHT_NUMBER, ""))
    ath_corner_color = str(row.get(Config.COL_CORNER, ""))
    mobile_number = str(row.get(Config.COL_MOBILE, ""))
    passport_image_url = str(row.get(Config.COL_PASSPORT_IMAGE, ""))
    room_number = str(row.get(Config.COL_ROOM, ""))
    curr_ath_task_stat = row.get('current_task_status', Config.STATUS_PENDING)
    card_bg_col = Config.STATUS_COLOR_MAP.get(curr_ath_task_stat, Config.STATUS_COLOR_MAP[Config.STATUS_PENDING])

    # Label do canto (luta/cor/evento)
    corner_color_map = {'red': '#d9534f', 'blue': '#428bca'}
    label_color = corner_color_map.get(ath_corner_color.lower(), '#4A4A4A')
    info_parts = []
    if ath_event_d != Config.DEFAULT_EVENT_PLACEHOLDER: info_parts.append(html.escape(ath_event_d))
    if ath_fight_number:   info_parts.append(f"LUTA {html.escape(ath_fight_number)}")
    if ath_corner_color:   info_parts.append(html.escape(ath_corner_color.upper()))
    fight_info_text = " | ".join(info_parts)
    fight_info_label_html = (
        f"<span style='background-color: {label_color}; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>{fight_info_text}</span>"
        if fight_info_text else ""
    )

    # Ações rápidas
    whatsapp_tag_html = ""
    if mobile_number:
        phone_digits = "".join(filter(str.isdigit, mobile_number))
        if phone_digits.startswith('00'):
            phone_digits = phone_digits[2:]
        if phone_digits:
            escaped_phone = html.escape(phone_digits, True)
            whatsapp_tag_html = (
                f"<a href='https://wa.me/{escaped_phone}' target='_blank' style='text-decoration: none;'>"
                f"<span style='background-color: #25D366; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>📞 WhatsApp</span>"
                f"</a>"
            )

    passport_tag_html = (
        f"<a href='{html.escape(passport_image_url, True)}' target='_blank' style='text-decoration: none;'>"
        f"<span style='background-color: #007BFF; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>🛂 Passaporte</span>"
        f"</a>"
        if passport_image_url and passport_image_url.startswith("http") else ""
    )

    # Labels dinâmicos com a tarefa fixa
    task_label = html.escape(Config.FIXED_TASK)
    # Mostrar texto para pendente de maneira clara
    stat_text = curr_ath_task_stat if curr_ath_task_stat not in [Config.STATUS_PENDING, None] else "Pending"
    task_status_html = f"<small style='color:#ccc;'>{task_label}: <b>{html.escape(stat_text)}</b></small>"

    arrival_status_html = (
        f"<small style='color:#ccc;'>Arrival Status: <b>{html.escape(room_number)}</b></small>"
        if room_number else ""
    )

    # Último registro da tarefa fixa em outro evento
    last_dt_str, last_event_str = last_info
    last_label = f"Last {task_label}"
    last_html = (
        f"<span class='event-badge'>{html.escape(last_event_str)} | {html.escape(last_dt_str)}</span>"
        if last_dt_str != 'N/A' and last_event_str else "N/A"
    )

    card_html = f"""<div class='card-container' style='background-color:{card_bg_col};'>
        <img src='{html.escape(row.get(Config.COL_IMAGE,"https://via.placeholder.com/60?text=NA"), True)}' class='card-img'>
        <div class='card-info'>
            <div class='info-line'><span class='fighter-name'>{html.escape(ath_name_d)} | {html.escape(ath_id_d)}</span></div>
            <div class='info-line'>{fight_info_label_html}</div>
            <div class='info-line'>{whatsapp_tag_html}{passport_tag_html}</div>
            <div class='info-line'>{task_status_html}</div>
            <div class='info-line'>{arrival_status_html}</div>
            <hr style='border-color: #444; margin: 5px 0; width: 100%;'>
            <div class='task-badges'>{badges_html}</div>
            <div class='info-line' style='margin-top:6px;'>
                <small style='color:#ccc;'>{html.escape(last_label)}: <b>{last_html}</b></small>
            </div>
        </div>
    </div>"""
    return card_html


# ==============================================================================
# FUNÇÕES DE REGISTRO (LOG)
# ==============================================================================
def registrar_log(
    ath_name: str,
    ath_event: str,
    task: str,
    status: str,
    notes: str,
    user_log_id: str,
    sheet_name: str = Config.MAIN_SHEET_NAME,
    att_tab_name: str = Config.ATTENDANCE_TAB_NAME
) -> bool:
    """
    Registra um log na planilha de presença.
    Args:
        ath_name (str): Nome do atleta.
        ath_event (str): Nome do evento.
        task (str): Tarefa registrada.
        status (str): Status da tarefa (ex: "Done", "Requested", "---", "").
        notes (str): Notas adicionais para o registro.
        user_log_id (str): ID do usuário que registrou a ação.
        sheet_name (str): Nome da planilha principal.
        att_tab_name (str): Nome da aba de attendance.
    Returns:
        bool: True se o registro foi bem-sucedido, False caso contrário.
    """
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)

        # Buscar o maior ID existente para garantir unicidade, se a coluna ID for numérica
        # Ou simplesmente contar as linhas se o ID for apenas um contador
        existing_rows = log_ws.get_all_values()
        next_num = len(existing_rows) + 1 # Assumindo que '#' é apenas um contador de linhas

        # Alinha com as colunas esperadas:
        # ["#", "Event", "Name", "Fighter", "Task", "Status", "User", "Timestamp", "TimeStamp", "Notes"]
        new_row_data = [
            str(next_num),
            ath_event,
            ath_name,
            ath_name,
            task,
            status,
            user_ident,
            ts, # Usar Timestamp
            ts, # Usar TimeStamp (para compatibilidade)
            notes
        ]

        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        lbl = "(vazio/pending)" if status == Config.STATUS_PENDING else (
              "Não precisa" if status == Config.STATUS_NOT_NEEDED else status)
        st.success(f"'{task}' para {ath_name} registrado como '{lbl}'.", icon="✍️")
        load_attendance_data.clear()  # Limpa cache para forçar recarregamento
        return True
    except Exception as e:
        st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨")
        return False


# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA E AUTENTICAÇÃO
# ==============================================================================
check_authentication()

# CSS
st.markdown("""
<style>
    .card-container {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        display: flex;
        align-items: flex-start;
        gap: 15px;
    }
    .card-img {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        object-fit: cover;
        flex-shrink: 0;
    }
    .card-info {
        width: 100%;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .info-line {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
    }
    .fighter-name {
        font-size: 1.25rem;
        font-weight: bold;
        margin: 0;
        color: white;
    }
    .task-badges { display: flex; flex-wrap: wrap; gap: 8px; }
    .event-badge {
        background-color: #428bca;
        color: #fff;
        padding: 3px 8px;
        border-radius: 8px;
        font-size: 0.75rem;
        font-weight: bold;
        display: inline-block;
    }
    /* Estilos para botões para garantir responsividade em linha */
    .button-group-row {
        display: flex;
        gap: 10px;
        margin-top: 10px; /* Ajuste para espaçamento */
        width: 100%;
    }
    .button-group-row > div {
        flex: 1; /* Faz com que os botões ocupem o espaço igualmente */
    }
    div.stButton > button { width: 100%; }
    .green-button button { background-color: #28a745; color: white !important; border: 1px solid #28a745; }
    .green-button button:hover { background-color: #218838; color: white !important; border: 1px solid #218838; }
    .red-button button { background-color: #dc3545; color: white !important; border: 1px solid #dc3545; }
    .red-button button:hover { background-color: #c82333; color: white !important; border: 1px solid #c82333; }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# LÓGICA PRINCIPAL DO APLICATIVO
# ==============================================================================
st.title("Photoshoot")
display_user_sidebar()

# Estado inicial da sessão
default_ss = {
    "selected_status": "Todos",
    "selected_event": "Todos os Eventos",
    "fighter_search_query": "",
    "sort_by": "Nome",
    "notes_input": "" # Adicionar estado para a caixa de notas
}
for k, v in default_ss.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Carregar dados
with st.spinner("Carregando dados..."):
    df_athletes = load_athlete_data()
    df_attendance_raw = load_attendance_data()
    tasks_raw, _ = load_config_data()
    tasks_raw = [str(x) for x in (tasks_raw or [])]

# Pré-processar dados de presença
df_attendance = preprocess_attendance(df_attendance_raw)

# Obter status atual da tarefa fixa para todos os atletas
if not df_athletes.empty:
    athletes_status = get_all_athletes_status(df_athletes, df_attendance, Config.FIXED_TASK)
    df_athletes = pd.merge(df_athletes, athletes_status, on=[Config.COL_NAME, Config.COL_EVENT], how='left')
    df_athletes.fillna({
        'current_task_status': Config.STATUS_PENDING,
        'latest_task_user': 'N/A',
        'latest_task_timestamp': 'N/A'
    }, inplace=True)

# Filtros e ordenação
with st.expander("Settings", expanded=True):
    col_status, col_sort = st.columns(2)
    with col_status:
        STATUS_FILTER_LABELS = {
            "Todos": "Todos",
            Config.STATUS_PENDING: "Pendente",
            Config.STATUS_REQUESTED: "Requisitado",
            Config.STATUS_DONE: "Concluído",
            Config.STATUS_NOT_NEEDED: "Não precisa (---)"
        }
        st.segmented_control(
            "Filtrar por Status:",
            options=["Todos", Config.STATUS_PENDING, Config.STATUS_REQUESTED, Config.STATUS_DONE, Config.STATUS_NOT_NEEDED],
            format_func=lambda x: STATUS_FILTER_LABELS.get(x, x if x else "Pendente"),
            key="selected_status"
        )
    with col_sort:
        st.segmented_control(
            "Ordenar por:",
            options=["Nome", "Ordem de Luta"],
            key="sort_by",
            help="Escolha como ordenar a lista de atletas."
        )
    event_options = ["Todos os Eventos"] + (
        sorted([evt for evt in df_athletes[Config.COL_EVENT].unique() if evt != Config.DEFAULT_EVENT_PLACEHOLDER])
        if not df_athletes.empty else []
    )
    st.selectbox("Filtrar Evento:", options=event_options, key="selected_event")
    st.text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID do lutador...", key="fighter_search_query")

# Aplicar filtros
df_filtered = df_athletes.copy()
if not df_filtered.empty:
    if st.session_state.selected_event != "Todos os Eventos":
        df_filtered = df_filtered[df_filtered[Config.COL_EVENT] == st.session_state.selected_event]

    search_term = st.session_state.fighter_search_query.strip().lower()
    if search_term:
        df_filtered = df_filtered[
            df_filtered[Config.COL_NAME].str.lower().str.contains(search_term, na=False) |
            df_filtered[Config.COL_ID].astype(str).str.contains(search_term, na=False)
        ]

    if st.session_state.selected_status != "Todos":
        df_filtered = df_filtered[df_filtered['current_task_status'] == st.session_state.selected_status]

    if st.session_state.get('sort_by', 'Nome') == 'Ordem de Luta':
        df_filtered['FIGHT_NUMBER_NUM'] = pd.to_numeric(df_filtered[Config.COL_FIGHT_NUMBER], errors='coerce').fillna(999)
        df_filtered['CORNER_SORT'] = df_filtered[Config.COL_CORNER].str.lower().map({'blue': 0, 'red': 1}).fillna(2)
        df_filtered = df_filtered.sort_values(by=['FIGHT_NUMBER_NUM', 'CORNER_SORT'], ascending=[True, True])
    else:
        df_filtered = df_filtered.sort_values(by=Config.COL_NAME, ascending=True)

# Resumo de status
if not df_filtered.empty:
    done_count = (df_filtered['current_task_status'] == Config.STATUS_DONE).sum()
    requested_count = (df_filtered['current_task_status'] == Config.STATUS_REQUESTED).sum()
    pending_count = (df_filtered['current_task_status'] == Config.STATUS_PENDING).sum()
    not_needed_count = (df_filtered['current_task_status'] == Config.STATUS_NOT_NEEDED).sum()
    summary_html = f'''<div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin-bottom: 10px; margin-top: 10px;">
        <span style="font-weight: bold;">Exibindo {len(df_filtered)} de {len(df_athletes)} atletas:</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_DONE]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Done: {done_count}</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_REQUESTED]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Requested: {requested_count}</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_PENDING]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Pending: {pending_count}</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_NOT_NEEDED]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Not Needed: {not_needed_count}</span>
    </div>'''
    st.markdown(summary_html, unsafe_allow_html=True)

st.divider()

# Renderizar cards dos atletas
for i_l, row in df_filtered.iterrows():
    # Obter informações do último registro da tarefa fixa em outro evento
    last_dt_str, last_event_str = last_task_other_event_by_name(
        df_attendance, row[Config.COL_NAME], row[Config.COL_EVENT], Config.FIXED_TASK, Config.TASK_ALIASES, fallback_any_event=True
    )

    # Gerar badges para outras tarefas
    badges_html = ""
    if tasks_raw:
        status_color_map_badge = {
            Config.STATUS_REQUESTED: "#D35400",
            Config.STATUS_DONE: "#1E8449",
            Config.STATUS_NOT_NEEDED: "#6c757d",
            Config.STATUS_PENDING: "#34495E"
        }
        default_color = "#34495E"
        name_n = clean_and_normalize(row[Config.COL_NAME])
        evt_n  = clean_and_normalize(row[Config.COL_EVENT])
        for task_name in tasks_raw:
            if str(task_name).strip().lower() == Config.FIXED_TASK.lower():
                continue
            status_for_badge = Config.STATUS_PENDING
            if not df_attendance.empty:
                t_norm = str(task_name).strip().lower()
                mask_t = (df_attendance["task_norm"] == t_norm)
                mask = (df_attendance["fighter_norm"] == name_n) & (df_attendance["event_norm"] == evt_n) & mask_t
                task_records = df_attendance.loc[mask].copy()
                if not task_records.empty:
                    task_records["__idx__"] = np.arange(len(task_records))
                    task_records = task_records.sort_values(by=["TS_dt", "__idx__"], ascending=[False, False])
                    # Usar o mapeamento de status da Config
                    status_for_badge = Config.map_raw_status_to_config(str(task_records.iloc[0].get(Config.ATT_COL_STATUS, Config.STATUS_PENDING)))

            color = status_color_map_badge.get(status_for_badge, default_color)
            badges_html += (
                f"<span style='background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; "
                f"font-size: 12px; font-weight: bold;'>{html.escape(task_name)}</span>"
            )

    # Renderizar card
    card_html = render_athlete_card(row, (last_dt_str, last_event_str), badges_html)
    col_card, col_buttons = st.columns([2.5, 1])
    with col_card:
        st.markdown(card_html, unsafe_allow_html=True)

    with col_buttons:
        uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
        curr = row.get('current_task_status', Config.STATUS_PENDING)

        st.text_area("Notes", value=st.session_state.notes_input, key=f"notes_input_{i_l}", placeholder="Adicione notas aqui...", height=50)
        current_notes = st.session_state[f"notes_input_{i_l}"]

        st.markdown("<div class='button-group-row'>", unsafe_allow_html=True) # Usar a nova classe CSS
        
        if curr == Config.STATUS_REQUESTED:
            # Fluxo quando já foi requisitado
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                st.markdown("<div class='green-button'>", unsafe_allow_html=True)
                if st.button("✅ Done", key=f"done_{row[Config.COL_NAME]}_{i_l}", use_container_width=True):
                    if registrar_log(row[Config.COL_NAME], row[Config.COL_EVENT], Config.FIXED_TASK, Config.STATUS_DONE, current_notes, uid_l):
                        time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with btn_c2:
                st.markdown("<div class='red-button'>", unsafe_allow_html=True)
                if st.button("❌ Cancel", key=f"cancel_{row[Config.COL_NAME]}_{i_l}", use_container_width=True):
                    # Cancel volta para pendente -> status ""
                    if registrar_log(row[Config.COL_NAME], row[Config.COL_EVENT], Config.FIXED_TASK, Config.STATUS_PENDING, current_notes, uid_l):
                        time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        else:
            # Fluxo padrão: permitir REQUISITAR e marcar como NÃO PRECISA
            btn_l, btn_r = st.columns(2)

            with btn_l:
                btn_label = "📝 Request Again" if curr == Config.STATUS_DONE else "📝 Request"
                btn_type = "secondary" if curr == Config.STATUS_DONE else "primary"
                if st.button(btn_label, key=f"request_{row[Config.COL_NAME]}_{i_l}", type=btn_type, use_container_width=True):
                    if registrar_log(row[Config.COL_NAME], row[Config.COL_EVENT], Config.FIXED_TASK, Config.STATUS_REQUESTED, current_notes, uid_l):
                        time.sleep(1); st.rerun()

            with btn_r:
                # Marca como não precisa (---)
                if st.button("🚫 Not Needed", key=f"notneeded_{row[Config.COL_NAME]}_{i_l}", use_container_width=True):
                    if registrar_log(row[Config.COL_NAME], row[Config.COL_EVENT], Config.FIXED_TASK, Config.STATUS_NOT_NEEDED, current_notes, uid_l):
                        time.sleep(1); st.rerun()

        st.markdown("</div>", unsafe_allow_html=True) # Fechar a div do button-group-row

    st.divider()

# Limpar a caixa de notas após a renderização para a próxima iteração
st.session_state.notes_input = ""