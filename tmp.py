import pandas as pd
from ml.forecast import simulate_forecast
from ml.alerts import generate_alerts
from ml.planner import get_recommendations
df_preds = pd.read_csv('data/predictions.csv')
df_master = pd.read_csv('data/aircraft_master.csv')
df_parts = pd.read_csv('data/parts_catalog.csv')
df_spares = pd.read_csv('data/spares_inventory.csv')
df_ws = pd.read_csv('data/workshops.csv')
df_sched = pd.read_csv('data/flight_schedule.csv')
alerts = generate_alerts(df_preds, df_master, df_parts, df_spares, df_ws)
recs = get_recommendations(alerts, df_ws, df_sched, df_master)
fc = simulate_forecast(df_master, df_preds, recs)
plan = fc['Plan'].mean()
noact = fc['No Action'].mean()
print(f'Plan: {plan:.1f} | No Action: {noact:.1f}')
