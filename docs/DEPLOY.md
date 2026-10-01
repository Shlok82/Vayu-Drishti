# Deployment Guide

## Streamlit Community Cloud (Recommended)
1. Push this repository to GitHub. Ensure the `data/raw` folder is ignored and only the small CSVs (like `data/demo/fleet_history.csv`) are committed.
2. Log in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **New app**.
4. Fill in the details:
   - **Repository:** `<your-username>/Vayu-Drishti`
   - **Branch:** `main`
   - **Main file path:** `app/main.py`
5. Click **Advanced settings**:
   - Select **Python 3.13**.
6. Click **Deploy**.

## Render (Backup)
1. Create a `render.yaml` or connect Render directly to the GitHub repo as a Web Service.
2. **Build Command:** `pip install -r requirements.txt`
3. **Start Command:** `streamlit run app/main.py --server.port $PORT`
4. Set the environment variable `PYTHON_VERSION` to `3.13.5`.

## Wake-the-app Checklist (Before Demo)
- [ ] Free hosting tiers often spin down apps after inactivity. Open your deployed link at least 15 minutes before the demonstration.
- [ ] Wait for it to say "Waking up app..." and fully load the Fleet Overview page.
- [ ] Run through the "Play Simulation" button on the Digital Twin once to cache data and warm up the instance.
