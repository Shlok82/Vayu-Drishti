# Deployment Guide

> **Note on Real-World Architecture:** intended real deployment: on-prem/offline

## Streamlit Community Cloud (Recommended)
1. Push this repository as a **public GitHub repository**. Ensure `data/raw/` is ignored and tracked runtime CSVs/demo files are committed.
2. Log in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **New app**.
4. Configure application settings:
   - **Repository:** `<your-username>/Vayu-Drishti` (public GitHub repo)
   - **Branch:** `main`
   - **Main file path:** `app/main.py`
5. Under **Advanced settings**:
   - Set **Python version** to `3.13` (matching the local development environment Python 3.13.5).
6. Click **Deploy**.

## Wake-the-App Checklist (Before Demo)
- Free tier hosting platforms (such as Streamlit Community Cloud or Render) automatically sleep after a period of inactivity.
- Open the deployed app URL a few minutes before any live presentation or evaluation to wake the container from sleep.
- Allow the initial landing page (Fleet Overview) to load completely and cache data before demoing.
- Click into the Digital Twin page to ensure all cached visualizations are pre-warmed.

## Render Fallback (Alternative Web Service)
1. Connect Render directly to the GitHub repository as a new Web Service.
2. **Environment:** Python
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `streamlit run app/main.py --server.port $PORT --server.address 0.0.0.0`
5. Under Environment Variables, set `PYTHON_VERSION` to `3.13.5`.
