
import pandas as pd
import streamlit as st
from utils import get_gspread_client, connect_gsheet_tab

DASHBOARD_STATUS_TAB = "dashboard_status"
KEY_COL = "Key"
VAL_COL = "Value"

def _get_status_ws(sheet_name: str):
    """Connects to the dashboard_status tab, creating headers if empty."""
    gc = get_gspread_client()
    ws = connect_gsheet_tab(gc, sheet_name, DASHBOARD_STATUS_TAB)
    
    # Ensure headers exist
    headers = ws.row_values(1)
    if not headers:
        ws.append_row([KEY_COL, VAL_COL])
        
    return ws

def load_dashboard_config(sheet_name: str) -> dict:
    """
    Loads configuration as a dictionary {Key: Value}.
    Returns empty dict on error.
    """
    try:
        ws = _get_status_ws(sheet_name)
        data = ws.get_all_records() # returns list of dicts based on headers
        
        config = {}
        for row in data:
            k = str(row.get(KEY_COL, "")).strip()
            v = str(row.get(VAL_COL, "")).strip()
            if k:
                config[k] = v
        return config
    except Exception as e:
        print(f"Error loading dashboard config: {e}")
        return {}

def save_dashboard_config(sheet_name: str, config_dict: dict):
    """
    Overwrites the dashboard configuration in the sheet.
    Uses clear() + append_rows() for simplicity since volume is small.
    """
    try:
        ws = _get_status_ws(sheet_name)
        
        # Prepare rows
        rows = [[KEY_COL, VAL_COL]]
        for k, v in config_dict.items():
            rows.append([str(k), str(v)])
            
        # Atomic-ish update: clear and write
        ws.clear()
        ws.update("A1", rows)
        
    except Exception as e:
        print(f"Error saving dashboard config: {e}")
        st.error(f"Failed to save configuration: {e}")
