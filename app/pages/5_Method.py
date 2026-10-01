import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import streamlit as st
import os

def main():
    st.title("Methodology & Disclaimers")
    
    method_path = 'docs/methodology.md'
    if os.path.exists(method_path):
        with open(method_path, 'r') as f:
            content = f.read()
        st.markdown(content)
    else:
        st.error("docs/methodology.md not found.")

if __name__ == '__main__':
    main()


