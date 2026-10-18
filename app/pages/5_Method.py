import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import streamlit as st
from app.auth import check_access

if not check_access("Methodology"):
    st.error("Access denied. Please log in with an authorized account.")
    st.stop()

import os

from ml.config import DOCS_DIR

def main():
    st.title("Methodology & Disclaimers")
    
    method_path = DOCS_DIR / 'methodology.md'
    if method_path.exists():
        with open(method_path, 'r', encoding='utf-8') as f:
            content = f.read()
        st.markdown(content)
    else:
        st.error("Methodology document not found.")

if __name__ == '__main__':
    main()


