import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import pandas as pd
from ml.config import DATA_DIR
from ml.alerts import generate_alerts
from ml.planner import get_recommendations
from ml.forecast import simulate_forecast

def precompute():
    print("Precomputing planner and forecast data...")
    df_preds = pd.read_csv(DATA_DIR / 'predictions.csv')
    df_master = pd.read_csv(DATA_DIR / 'aircraft_master.csv')
    df_parts = pd.read_csv(DATA_DIR / 'parts_catalog.csv')
    df_spares = pd.read_csv(DATA_DIR / 'spares_inventory.csv')
    df_ws = pd.read_csv(DATA_DIR / 'workshops.csv')
    df_sched = pd.read_csv(DATA_DIR / 'flight_schedule.csv')
    
    alerts_df = generate_alerts(df_preds, df_master, df_parts, df_spares, df_ws)
    recs = get_recommendations(alerts_df, df_ws, df_sched, df_master)
    recs.to_csv(DATA_DIR / 'planner_recommendations.csv', index=False)
    
    fc, _ = simulate_forecast(df_master, df_preds, recs, return_details=True)
    fc.to_csv(DATA_DIR / 'forecast_30d.csv', index=False)
    print("Precomputation done.")

if __name__ == '__main__':
    precompute()
