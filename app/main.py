import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import streamlit as st
from app.auth import verify, allowed_pages, logout, set_current_user, GUEST_ROLE

st.set_page_config(page_title="Vayu Drishti", layout="wide")

auth_user = st.session_state.get("auth_user")

if not auth_user:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.title("Vayu Drishti")
        st.subheader("Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Login")
            if login_btn:
                role = verify(username, password)
                if role:
                    set_current_user(username, role)
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        if st.button("Continue as guest viewer"):
            set_current_user("guest", GUEST_ROLE)
            st.rerun()

        demo_file = _root / "docs" / "DEMO_ACCESS.md"
        if demo_file.exists():
            with open(demo_file, "r", encoding="utf-8") as f:
                demo_text = f.read()
            st.markdown(demo_text)

        st.caption("Demo access control, not production security.")

    st.stop()

# Build navigation from allowed_pages(role) only
role = st.session_state.get("role", GUEST_ROLE)

with st.sidebar:
    st.write(f"Logged in as {auth_user} ({role})")
    if st.button("Logout", key="logout_btn"):
        logout()
        st.rerun()

PAGE_DEFS = {
    "Fleet Overview": st.Page("pages/0_Fleet_Overview.py", title="Fleet Overview"),
    "Aircraft Detail": st.Page("pages/1_Aircraft_Detail.py", title="Aircraft Detail"),
    "Digital Twin": st.Page("pages/2_Digital_Twin.py", title="Digital Twin"),
    "Planner": st.Page("pages/3_Planner.py", title="Planner"),
    "Results": st.Page("pages/4_Results.py", title="Results"),
    "Methodology": st.Page("pages/5_Method.py", title="Methodology"),
}

user_pages = [PAGE_DEFS[name] for name in allowed_pages(role) if name in PAGE_DEFS]
pages = {"Dashboards": user_pages}

pg = st.navigation(pages)
pg.run()


