# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Stats Control", layout="wide")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
STATS_TAB_NAME = "df [Stats]"
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance"
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"

T_SHIRT_SIZES = ["-- Selecione --", "S", "M", "L", "XL", "XXL", "3XL"]
COUNTRY_LIST = [
    "-- Selecione --", "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia",
    "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan",
    "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde",
    "Cambodia", "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros",
    "Congo, Democratic Republic of the", "Congo, Republic of the", "Costa Rica", "Cote d'Ivoire", "Croatia", "Cuba", "Cyprus",
    "Czechia", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea",
    "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany",
    "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary", "Iceland",
    "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya",
    "Kiribati", "Kosovo", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein",
    "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania",
    "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar",
    "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia",
    "Norway", "Oman", "Pakistan", "Palau", "Palestine State", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines",
    "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia",
    "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea",
    "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan",
    "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan",
    "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States of America", "Uruguay", "Uzbekistan",
    "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
]

# --- 2. Google Sheets Connection ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e: st.error(f"Erro API Google: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except gspread.exceptions.SpreadsheetNotFound: st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound: st.error(f"Erro: Aba '{tab_name}' não encontrada.", icon="🚨"); st.stop()
    except Exception as e: st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨"); st.stop()

# --- 3. Data Loading ---
@st.cache_data(ttl=600)
def load_athlete_data(sheet_name: str = MAIN_SHEET_NAME, athletes_tab_name: str = ATHLETES_TAB_NAME):
    try:
        gspread_client = get_gspread_client(); worksheet = connect_gsheet_tab(gspread_client, sheet_name, athletes_tab_name); data = worksheet.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data);
        if df.empty: return pd.DataFrame()
        if "ROLE" not in df.columns or "INACTIVE" not in df.columns: st.error(f"Colunas 'ROLE'/'INACTIVE' não encontradas.", icon="🚨"); return pd.DataFrame()
        df.columns = df.columns.str.strip()
        df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        df["EVENT"] = df["EVENT"].fillna("Z")
        for col in ["DOB", "PASSPORT EXPIRE DATE", "BLOOD TEST"]:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
        for col_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE", "GENDER"]:
            if col_check in df.columns: df[col_check] = df[col_check].fillna("")
            else: df[col_check] = ""
        if "NAME" not in df.columns: st.error(f"'NAME' não encontrada.", icon="🚨"); return pd.DataFrame()
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e: st.error(f"Erro ao carregar atletas: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_stats_data(sheet_name: str = MAIN_SHEET_NAME, stats_tab_name: str = STATS_TAB_NAME):
    try: gspread_client = get_gspread_client(); worksheet = connect_gsheet_tab(gspread_client, sheet_name, stats_tab_name); return pd.DataFrame(worksheet.get_all_records())
    except Exception as e: st.error(f"Erro ao carregar estatísticas: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=300)
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    try: gspread_client = get_gspread_client(); worksheet = connect_gsheet_tab(gspread_client, sheet_name, users_tab_name); return worksheet.get_all_records() or []
    except Exception as e: st.error(f"Erro ao carregar usuários: {e}", icon="🚨"); return []

def get_valid_user_info(user_input: str, sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    if not user_input: return None
    all_users = load_users_data(sheet_name, users_tab_name)
    proc_input = user_input.strip().upper()
    for record in all_users:
        ps_sheet = str(record.get("PS", "")).strip(); name_sheet = str(record.get("USER", "")).strip().upper()
        if ps_sheet == proc_input or name_sheet == proc_input: return record
    return None

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client(); worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name); df_att = pd.DataFrame(worksheet.get_all_records())
        expected_cols = ["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes"]
        for col in expected_cols:
            if col not in df_att.columns: df_att[col] = None
        return df_att
    except Exception as e: st.error(f"Erro ao carregar presença: {e}", icon="🚨"); return pd.DataFrame()

def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str, sheet_name: str = MAIN_SHEET_NAME, att_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client(); log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name); all_vals = log_ws.get_all_values()
        next_num = int(all_vals[-1][0]) + 1 if len(all_vals) > 1 and str(all_vals[-1][0]).isdigit() else len(all_vals) + 1
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)
        new_row = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        log_ws.append_row(new_row, value_input_option="USER_ENTERED")
        st.toast(f"'{task}' para {ath_name} registrada como '{status}'.", icon="✍️"); load_attendance_data.clear(); return True
    except Exception as e: st.error(f"Erro ao registrar log de presença: {e}", icon="🚨"); return False

def add_stats_record(data: dict, sheet_name: str = MAIN_SHEET_NAME, stats_tab_name: str = STATS_TAB_NAME):
    try:
        gspread_client = get_gspread_client(); stats_ws = connect_gsheet_tab(gspread_client, sheet_name, stats_tab_name); all_vals = stats_ws.get_all_values()
        next_id = int(all_vals[-1][0]) + 1 if len(all_vals) > 1 and str(all_vals[-1][0]).isdigit() else len(all_vals) + 1
        headers = ['stats_record_id', 'fighter_id', 'fighter_event_name', 'gender', 'weight_kg', 'height_cm', 'reach_cm','fight_style', 'country_of_representation', 'residence_city', 'team_name', 'tshirt_size','updated_by_user', 'updated_at', 'event', 'tshirt_size_c1', 'tshirt_size_c2', 'tshirt_size_c3', 'operation']
        data['stats_record_id'] = next_id
        new_row = [data.get(h, "") for h in headers]
        stats_ws.append_row(new_row, value_input_option="USER_ENTERED")
        st.toast(f"Estatísticas para {data.get('fighter_event_name')} salvas!", icon="💾"); load_stats_data.clear(); return True
    except Exception as e: st.error(f"Erro ao salvar estatísticas: {e}", icon="🚨"); return False

# --- Main Application Logic ---
st.title("UAEW | Stats Control")
default_ss = { "warning_message": None, "user_confirmed": False, "current_user_id": "", "current_user_name": "User", "current_user_image_url": "", "show_personal_data": False, "selected_event": "Todos os Eventos", "fighter_search_query": "" }
for k,v in default_ss.items():
    if k not in st.session_state: st.session_state[k]=v
if 'user_id_input' not in st.session_state: st.session_state['user_id_input']=st.session_state['current_user_id']

with st.container(border=True):
    st.subheader("User"); col1, col2 = st.columns([0.6, 0.4])
    with col1:
        st.session_state['user_id_input'] = st.text_input("PS Number", value=st.session_state['user_id_input'], max_chars=50, key="uid_w", label_visibility="collapsed", placeholder="Typer 4 digits of your PS")
        if st.button("Login", key="confirm_b_w", use_container_width=True, type="primary"):
            u_in=st.session_state['user_id_input'].strip()
            if u_in:
                u_inf=get_valid_user_info(u_in)
                if u_inf: st.session_state.update(current_user_ps_id_internal=str(u_inf.get("PS",u_in)).strip(), current_user_id=u_in, current_user_name=str(u_inf.get("USER",u_in)).strip(), current_user_image_url=str(u_inf.get("USER_IMAGE","")).strip(), user_confirmed=True, warning_message=None)
                else: st.session_state.update(user_confirmed=False,current_user_image_url="",warning_message=f"⚠️ Usuário '{u_in}' não encontrado.")
            else: st.session_state.update(warning_message="⚠️ ID/Nome do usuário vazio.",user_confirmed=False,current_user_image_url="")
    with col2:
        if st.session_state.user_confirmed and st.session_state.current_user_name != "Usuário":
            un, ui, uim = html.escape(st.session_state.current_user_name), html.escape(st.session_state.get("current_user_ps_id_internal", "")), st.session_state.get('current_user_image_url', "")
            img_html = f'<img src="{html.escape(uim, True)}" style="width:50px;height:50px;border-radius:50%;object-fit:cover;border:1px solid #555;vertical-align:middle;margin-right:10px;">' if uim and uim.startswith("http") else "<div style='width:50px;height:50px;border-radius:50%;background-color:#333;margin-right:10px;display:inline-block;vertical-align:middle;'></div>"
            st.markdown(f'<div style="display:flex;align-items:center;height:50px;">{img_html}<div style="line-height:1.2;"><b>{un}</b><br><span style="font-size:0.9em;color:#ccc;">PS: {ui}</span></div></div>', unsafe_allow_html=True)
        elif st.session_state.get('warning_message'): st.warning(st.session_state.warning_message, icon="🚨")
    if st.session_state.user_confirmed and st.session_state.current_user_id.strip().upper() != st.session_state.user_id_input.strip().upper():
        st.session_state.update(user_confirmed=False,warning_message="⚠️ ID/Nome alterado. Confirme.",current_user_image_url=""); st.rerun()

if st.session_state.user_confirmed:
    st.markdown("---")
    with st.spinner("Carregando dados..."):
        df_athletes = load_athlete_data()
        df_attendance = load_attendance_data()
        df_stats = load_stats_data()
    
    c1, c2, c3 = st.columns([0.4, 0.4, 0.2])
    with c1: 
        event_list = ["Todos os Eventos"] + sorted([e for e in df_athletes["EVENT"].unique() if e != "Z"]) if not df_athletes.empty else []
        st.selectbox("Filtrar Evento:", options=event_list, key="selected_event")
    with c2: st.text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID do lutador...", key="fighter_search_query")
    with c3: st.markdown("<br>", True); st.button("🔄 Atualizar", key="ref_b_w", help="Recarrega todos os dados.", on_click=lambda:(load_athlete_data.clear(), load_users_data.clear(), load_attendance_data.clear(), load_stats_data.clear(), st.toast("Dados atualizados!", icon="🔄")), use_container_width=True)

    st.toggle("Mostrar Dados Pessoais", key="show_personal_data")
    st.markdown("---")

    if df_athletes.empty: st.info("Nenhum atleta para exibir.")
    else:
        df_filtered = df_athletes.copy()
        if st.session_state.selected_event != "Todos os Eventos": df_filtered = df_filtered[df_filtered["EVENT"] == st.session_state.selected_event]
        if st.session_state.fighter_search_query:
            term = st.session_state.fighter_search_query.strip().lower()
            df_filtered = df_filtered[df_filtered.apply(lambda r: term in str(r['NAME']).lower() or term in str(r['ID']), axis=1)]

        st.markdown(f"Exibindo **{len(df_filtered)}** de **{len(df_athletes)}** atletas.")

        for i_l, row in df_filtered.iterrows():
            ath_id_d, ath_name_d, ath_event_d = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])
            
            stats_status_rec = None
            if not df_attendance.empty:
                stats_records = df_attendance[(df_attendance["Name"].astype(str).str.lower() == ath_name_d.lower()) & (df_attendance["Task"] == "Estatística") & (df_attendance["Event"] == ath_event_d)]
                if not stats_records.empty:
                    stats_status_rec = stats_records.sort_values(by="Timestamp", ascending=False).iloc[0]
            
            card_bg_col = "#143d14" if stats_status_rec is not None and stats_status_rec.get("Status") == "Done" else "#1e1e1e"
            
            pass_img_h=f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte Img:</b></td><td><a href='{html.escape(str(row.get('PASSPORT IMAGE','')),True)}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>" if pd.notna(row.get("PASSPORT IMAGE"))and row.get("PASSPORT IMAGE")else ""
            mob_r=str(row.get("MOBILE","")).strip();wa_h=""
            if mob_r:
                phone_digits="".join(filter(str.isdigit,mob_r));
                if phone_digits.startswith('00'):phone_digits=phone_digits[2:]
                if phone_digits:wa_h=f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{html.escape(phone_digits,True)}' target='_blank' style='color:#00BFFF;'>Msg</a></td></tr>"
            
            pd_tbl_h=f"""<div style='flex-basis:350px;flex-grow:1;'><table style='font-size:14px;color:white;border-collapse:collapse;width:100%;'><tr><td style='padding-right:10px;white-space:nowrap;'><b>Gênero:</b></td><td>{html.escape(str(row.get("GENDER","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nascimento:</b></td><td>{html.escape(str(row.get("DOB","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row.get("NATIONALITY","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte:</b></td><td>{html.escape(str(row.get("PASSPORT","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Expira em:</b></td><td>{html.escape(str(row.get("PASSPORT EXPIRE DATE","")))}</td></tr>{pass_img_h}{wa_h}</table></div>"""if st.session_state.show_personal_data else"<div style='flex-basis:300px;flex-grow:1;font-style:italic;color:#ccc;font-size:13px;text-align:center;'>Dados pessoais ocultos.</div>"
            st.markdown(f"""<div style='background-color:{card_bg_col};padding:20px;border-radius:10px;margin-bottom:15px;box-shadow:2px 2px 5px rgba(0,0,0,0.3);'><div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px;'><div style='display:flex;align-items:center;gap:15px;flex-basis:300px;flex-grow:1;'><img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/80?text=No+Image")if pd.notna(row.get("IMAGE"))and row.get("IMAGE")else"https://via.placeholder.com/80?text=No+Image",True)}' style='width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid white;'><div><h4 style='margin:0;text-align:center;font-size:1.5em;'>{html.escape(ath_name_d)}</h4><p style='margin:0;font-size:14px;color:#cccccc;text-align:center;'>{html.escape(ath_event_d)}</p><p style='margin:0;font-size:13px;color:#cccccc;text-align:center;'>ID: {html.escape(ath_id_d)}</p></div></div>{pd_tbl_h}</div></div>""",True)

            st.markdown("##### Estatísticas do Atleta")
            latest_stats = None
            if not df_stats.empty and 'fighter_event_name' in df_stats.columns:
                athlete_stats_df = df_stats[df_stats['fighter_event_name'].astype(str).str.lower() == ath_name_d.lower()].copy()
                if not athlete_stats_df.empty:
                    athlete_stats_df['timestamp_dt'] = pd.to_datetime(athlete_stats_df['updated_at'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
                    latest_stats = athlete_stats_df.sort_values(by='timestamp_dt', ascending=False).iloc[0]

            editable_fields = ['weight_kg', 'height_cm', 'reach_cm', 'fight_style', 'country_of_representation', 'residence_city', 'team_name', 'tshirt_size', 'tshirt_size_c1', 'tshirt_size_c2', 'tshirt_size_c3']
            
            edit_mode_key = f"edit_mode_{ath_id_d}"
            if edit_mode_key not in st.session_state: st.session_state[edit_mode_key] = False
            is_editing = st.session_state[edit_mode_key]

            if not is_editing:
                for field in editable_fields:
                    key = f"stat_{field}_{ath_id_d}"; value = latest_stats.get(field) if latest_stats is not None else None
                    if value is None or pd.isna(value) or str(value).strip() == '':
                        if field in ['weight_kg', 'height_cm', 'reach_cm']: st.session_state[key] = 0.0
                        elif 'tshirt' in field or 'country' in field: st.session_state[key] = "-- Selecione --"
                        else: st.session_state[key] = ""
                    else:
                        try: st.session_state[key] = float(value) if field in ['weight_kg', 'height_cm', 'reach_cm'] else str(value)
                        except (ValueError, TypeError): st.session_state[key] = str(value)

            btn_cols = st.columns([0.4, 0.3, 0.3])
            with btn_cols[1]:
                if not is_editing and latest_stats is not None:
                    if st.button("✔️ Confirmar Dados", key=f"confirm_stats_{ath_id_d}", use_container_width=True):
                        data_to_confirm = latest_stats.to_dict()
                        data_to_confirm['updated_at'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        data_to_confirm['updated_by_user'] = st.session_state.get('current_user_name', 'System')
                        data_to_confirm['operation'] = "confirmed"
                        if add_stats_record(data_to_confirm):
                            registrar_log(ath_id_d, ath_name_d, ath_event_d, "Estatística", "Done", "Dados confirmados", st.session_state.get('current_user_name', 'System'))
                            st.rerun()

            with btn_cols[2]:
                if st.button("✏️ Alterar Dados" if not is_editing else "✖️ Cancelar", key=f"toggle_edit_{ath_id_d}", use_container_width=True, type="secondary" if not is_editing else "primary"):
                    st.session_state[edit_mode_key] = not st.session_state[edit_mode_key]
                    st.rerun()
            
            c1, c2, c3 = st.columns(3); cols = [c1, c2, c3]; i = 0
            field_labels = {'weight_kg': "Peso (kg)", 'height_cm': "Altura (cm)", 'reach_cm': "Envergadura (cm)", 'fight_style': "Estilo de Luta", 'country_of_representation': "País (Representação)", 'residence_city': "Cidade de Residência", 'team_name': "Nome da Equipe", 'tshirt_size': "Camiseta (Atleta)", 'tshirt_size_c1': "Camiseta (C1)", 'tshirt_size_c2': "Camiseta (C2)", 'tshirt_size_c3': "Camiseta (C3)"}
            for field in editable_fields:
                with cols[i % 3]:
                    label = field_labels.get(field, field); key = f"stat_{field}_{ath_id_d}"
                    if field in ['weight_kg', 'height_cm', 'reach_cm']: st.number_input(label, key=key, disabled=not is_editing, format="%.2f", step=0.10)
                    elif field == 'country_of_representation': st.selectbox(label, options=COUNTRY_LIST, key=key, disabled=not is_editing)
                    elif 'tshirt_size' in field: st.selectbox(label, options=T_SHIRT_SIZES, key=key, disabled=not is_editing)
                    else: st.text_input(label, key=key, disabled=not is_editing)
                i += 1

            if is_editing:
                if st.button(f"💾 Salvar Alterações para {ath_name_d}", key=f"save_stats_{ath_id_d}", type="primary", use_container_width=True):
                    new_data = {
                        'fighter_id': ath_id_d, 'fighter_event_name': ath_name_d, 'gender': row.get("GENDER", ""), 
                        'event': ath_event_d, 'updated_at': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        'updated_by_user': st.session_state.get('current_user_name', 'System'),
                        'operation': "updated" if latest_stats is not None else "created"
                    }
                    for field in editable_fields: new_data[field] = st.session_state.get(f"stat_{field}_{ath_id_d}")
                    
                    if add_stats_record(new_data):
                        registrar_log(ath_id_d, ath_name_d, ath_event_d, "Estatística", "Done", f"Operação: {new_data['operation']}", st.session_state.get('current_user_name', 'System'))
                        st.session_state[edit_mode_key] = False
                        st.rerun()

            st.markdown("<hr style='border-top:1px solid #333;margin-top:10px;margin-bottom:25px;'>", True)
