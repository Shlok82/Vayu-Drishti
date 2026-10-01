import pandas as pd
from ml.config import DATA_DIR
from ml.alerts import generate_alerts
from ml.planner import get_recommendations
df_ws = pd.read_csv(DATA_DIR / 'workshops.csv')
print(df_ws)
alerts_df = generate_alerts(pd.read_csv(DATA_DIR / 'predictions.csv'), pd.read_csv(DATA_DIR / 'aircraft_master.csv'), pd.read_csv(DATA_DIR / 'parts_catalog.csv'), pd.read_csv(DATA_DIR / 'spares_inventory.csv'), df_ws)
recs = get_recommendations(alerts_df, df_ws, pd.read_csv(DATA_DIR / 'flight_schedule.csv'), pd.read_csv(DATA_DIR / 'aircraft_master.csv'))
for _, r in recs[recs['flag'] != ''].iterrows():
    print(f"Job {r['aircraft_id']} for {r['component']}: flag={r['flag']}, workshop={r['workshop_id']}")
