streamlit.errors.StreamlitAPIException: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).

Traceback:
File "/mount/src/uaewapp_1/pages/transfers.py", line 165, in <module>
    st.session_state["arrdep_mode"] = st.segmented_control(
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/runtime/metrics_util.py", line 443, in wrapped_func
    result = non_optional_func(*args, **kwargs)
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/runtime/state/session_state_proxy.py", line 114, in __setitem__
    get_session_state()[key] = value
    ~~~~~~~~~~~~~~~~~~~^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/runtime/state/safe_session_state.py", line 109, in __setitem__
    self._state[key] = value
    ~~~~~~~~~~~^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/streamlit/runtime/state/session_state.py", line 533, in __setitem__
    raise StreamlitAPIException(
    ...<2 lines>...
    )
