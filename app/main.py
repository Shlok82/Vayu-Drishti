import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import streamlit as st

st.set_page_config(page_title="Vayu Drishti", layout="wide")

pages = {
    "Dashboards": [
        st.Page("pages/0_Fleet_Overview.py", title="Fleet Overview"),
        st.Page("pages/1_Aircraft_Detail.py", title="Aircraft Detail"),
        st.Page("pages/2_Digital_Twin.py", title="Digital Twin"),
        st.Page("pages/3_Planner.py", title="Planner"),
        st.Page("pages/4_Results.py", title="Results"),
        st.Page("pages/5_Method.py", title="Methodology"),
    ]
}

pg = st.navigation(pages)
pg.run()


