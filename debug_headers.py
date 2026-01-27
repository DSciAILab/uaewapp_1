
import streamlit as st
from utils import get_gspread_client, connect_gsheet_tab
from task_logic import BaseConfig

try:
    cfg = BaseConfig()
    gc = get_gspread_client()
    ws = connect_gsheet_tab(gc, cfg.MAIN_SHEET_NAME, cfg.ATTENDANCE_TAB_NAME)
    headers = ws.row_values(1)
    print(f"ACTUAL HEADERS: {headers}")
except Exception as e:
    print(f"Error: {e}")
