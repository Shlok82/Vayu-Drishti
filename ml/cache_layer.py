import streamlit as st
import pandas as pd
import json
import os
from ml.config import DATA_DIR
from ml.alerts import generate_alerts
from ml.planner import get_recommendations
from ml.forecast import simulate_forecast

@st.cache_data
def load_all_csvs():
    df_preds = pd.read_csv(DATA_DIR / 'predictions.csv')
    df_master = pd.read_csv(DATA_DIR / 'aircraft_master.csv')
    df_parts = pd.read_csv(DATA_DIR / 'parts_catalog.csv')
    df_spares = pd.read_csv(DATA_DIR / 'spares_inventory.csv')
    df_ws = pd.read_csv(DATA_DIR / 'workshops.csv')
    df_sched = pd.read_csv(DATA_DIR / 'flight_schedule.csv')
    from pathlib import Path
    _root = Path(__file__).resolve().parents[1]
    with open(_root / 'docs' / 'metrics.json', 'r') as f:
        metrics = json.load(f)
    return df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics

@st.cache_data
def cached_generate_alerts():
    df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics = load_all_csvs()
    return generate_alerts(df_preds, df_master, df_parts, df_spares, df_ws)

@st.cache_data
def cached_get_recommendations():
    if os.path.exists(DATA_DIR / 'planner_recommendations.csv'):
        return pd.read_csv(DATA_DIR / 'planner_recommendations.csv')
    alerts_df = cached_generate_alerts()
    df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics = load_all_csvs()
    return get_recommendations(alerts_df, df_ws, df_sched, df_master)

@st.cache_data
def cached_simulate_forecast():
    if os.path.exists(DATA_DIR / 'forecast_30d.csv'):
        return pd.read_csv(DATA_DIR / 'forecast_30d.csv')
    df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics = load_all_csvs()
    recs = cached_get_recommendations()
    fc, _ = simulate_forecast(df_master, df_preds, recs, return_details=True)
    return fc
