import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(page_title="Live Dashboard", layout="wide")

# --- Auto-Refresh ---
# Refresh the dashboard every 5 seconds to get the latest data
st_autorefresh(interval=5000, key="dashboard_refresh")

# --- Dynamic CSS (Copied from the main page for consistency) ---
# We retrieve styles from session_state if they exist, otherwise use defaults.
name_font_size = st.session_state.get('name_font_size', 18)
number_font_size = st.session_state.get('number_font_size', 48)
photo_size = st.session_state.get('photo_size', 60)

st.markdown(f"""
<style>
    div[data-testid="stToolbar"], #MainMenu, header {{ visibility: hidden; }}
    div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] {{ align-items: center; }}
    
    .next-in-queue {{ background-color: #1c2833; border: 1px solid #00BFFF; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; }}
    .athlete-photo {{ width: {photo_size}px; height: {photo_size}px; border-radius: 50%; object-fit: cover; border: 2px solid #4F4F4F; }}
    .finished-photo {{ width: {int(photo_size * 0.7)}px; height: {int(photo_size * 0.7)}px; border-radius: 50%; object-fit: cover; filter: grayscale(100%); opacity: 0.6; }}
    .athlete-name {{ font-size: {name_font_size}px !important; font-weight: bold; line-height: 1.2; margin-bottom: 5px; }}
    .call-number {{ font-size: {number_font_size}px !important; font-weight: bold; text-align: center; color: #808495; }}
    .eta-text {{ font-size: 0.8em; color: #A0A0A0; }}
</style>
""", unsafe_allow_html=True)


# --- Main Dashboard Interface ---
st.title("Live Queue Dashboard")

# --- Check if any tasks have been started on the main page ---
if 'tasks' not in st.session_state or not st.session_state.tasks:
    st.info("No tasks are currently active. Please go to the 'Task Control' page to start a queue.")
    st.stop()

# --- Task Selector ---
# The user selects which active task they want to view on the dashboard.
available_tasks = list(st.session_state.tasks.keys())
selected_task = st.selectbox("Select a Task to Display:", options=available_tasks)

st.divider()

if selected_task:
    task_data = st.session_state.tasks[selected_task]

    # --- Data Processing for Display ---
    checked_in_list, finished_list = [], []
    for athlete_id, athlete_data in task_data['athletes'].items():
        if athlete_data['status'] == 'na fila':
            checked_in_list.append((athlete_id, athlete_data))
        elif athlete_data['status'] == 'finalizado':
            finished_list.append((athlete_id, athlete_data))
    
    # Sort the queue by check-in number
    checked_in_list.sort(key=lambda item: item[1]['checkin_number'])

    # --- Display Columns ---
    col1, col2 = st.columns(2)

    # --- "On Queue" Column (Read-Only) ---
    with col1:
        st.header(f"On Queue ({len(checked_in_list)})")
        for index, (athlete_id, athlete) in enumerate(checked_in_list):
            is_next = index == 0
            card_class = "next-in-queue" if is_next else ""
            
            with st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True) if is_next else st.container(border=True):
                st.markdown('<div class="card-content-wrapper">', unsafe_allow_html=True)
                num_col, pic_col, name_col = st.columns([1, 1, 2])
                with num_col:
                    st.markdown(f"<p class='call-number' style='color:{'#00BFFF' if is_next else '#808495'};'>{athlete['checkin_number']}</p>", unsafe_allow_html=True)
                with pic_col:
                    st.markdown(f'<img class="athlete-photo" style="border-color:{"#00BFFF" if is_next else "#808495"};" src="{athlete["pic"]}">', unsafe_allow_html=True)
                with name_col:
                    st.markdown(f"<p class='athlete-name'>{athlete['name']}</p>", unsafe_allow_html=True)
                    if is_next:
                        st.markdown("⭐ **NEXT!**")
                st.markdown('</div>', unsafe_allow_html=True)
            if is_next: st.markdown('</div>', unsafe_allow_html=True)

    # --- "Finished" Column (Read-Only) ---
    with col2:
        st.header(f"Finished ({len(finished_list)})")
        for athlete_id, athlete in finished_list:
             with st.container(border=True):
                st.markdown('<div class="card-content-wrapper">', unsafe_allow_html=True)
                pic_col, name_col = st.columns([1, 4])
                with pic_col:
                    st.markdown(f'<img class="finished-photo" src="{athlete["pic"]}">', unsafe_allow_html=True)
                with name_col:
                    st.markdown(f"<p class='athlete-name' style='text-decoration: line-through; color: #808495;'>{athlete['name']}</p>", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
