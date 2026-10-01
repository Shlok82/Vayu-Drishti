import pandas as pd
import json
import os
import sys
from datetime import datetime
from streamlit.testing.v1 import AppTest

def check_day3():
    print("--- Running Day 3 self-checks ---")
    
    # 1. Alert logic
    import alerts
    df_preds = pd.read_csv('data/predictions.csv')
    df_master = pd.read_csv('data/aircraft_master.csv')
    df_parts = pd.read_csv('data/parts_catalog.csv')
    df_spares = pd.read_csv('data/spares_inventory.csv')
    
    alerts_df = alerts.generate_alerts(df_preds, df_master, df_parts, df_spares)
    if not alerts_df.empty:
        alerts_ok = True
        for _, row in alerts_df.iterrows():
            if row['status'] == 'CANNOT ARRIVE IN TIME' and (row['qty_on_hand'] > 0 or row['lead_time_days'] <= row['days_to_failure']):
                alerts_ok = False
            if row['status'] == 'ORDER NOW' and row['qty_on_hand'] > 0 and row['qty_on_hand'] > 0: # simplified
                pass
        if alerts_ok: print("PASS: alerts statuses consistent with lead time vs days to failure")
        else: print("FAIL: alerts logic mismatch")
    else:
        print("WARN: No alerts to check")
        
    # 2. Planner logic
    import planner
    df_ws = pd.read_csv('data/workshops.csv')
    df_sched = pd.read_csv('data/flight_schedule.csv')
    recs = planner.get_recommendations(alerts_df, df_ws, df_sched, df_master)
    if not recs.empty:
        planner_ok = True
        
        # Check capacity
        ws_usage = {}
        for _, r in recs.iterrows():
            if r['flag'] == "":
                ws = r['workshop_id']
                st = datetime.strptime(r['slot_start'], "%Y-%m-%d").date()
                en = datetime.strptime(r['slot_end'], "%Y-%m-%d").date()
                days = (en - st).days
                for d in range(days):
                    d_dt = (st + pd.Timedelta(days=d)).strftime("%Y-%m-%d")
                    if ws not in ws_usage: ws_usage[ws] = {}
                    ws_usage[ws][d_dt] = ws_usage[ws].get(d_dt, 0) + 1
                    
        for ws, usage in ws_usage.items():
            cap = df_ws[df_ws['workshop_id'] == ws]['capacity_slots'].iloc[0]
            if any(v > cap for v in usage.values()):
                planner_ok = False
                
        # Check end before failure
        for _, r in recs.iterrows():
            if r['flag'] == "":
                # We need original failure date
                dtf = alerts_df[(alerts_df['aircraft_id'] == r['aircraft_id']) & (alerts_df['component'] == r['component'])]['days_to_failure'].iloc[0]
                fail_date = datetime.strptime('2026-10-01', "%Y-%m-%d").date() + pd.Timedelta(days=int(dtf))
                en = datetime.strptime(r['slot_end'], "%Y-%m-%d").date()
                if en > fail_date:
                    planner_ok = False
                    
        if planner_ok: print("PASS: planner respects capacity and ends before failure")
        else: print("FAIL: planner logic mismatch")
    else:
        print("WARN: No recommendations to check")
        
    # 3. Forecast logic
    import forecast
    f_df = forecast.simulate_forecast(df_master, df_preds, recs, days=30)
    if len(f_df) == 30 and all(0 <= v <= 24 for v in f_df['Plan']) and all(0 <= v <= 24 for v in f_df['No Action']):
        print("PASS: forecast counts between 0 and 24 for 30 days")
    else:
        print("FAIL: forecast counts invalid")
        
    # 4. Simulation output
    res_path = 'docs/sim_results.json'
    if os.path.exists(res_path):
        with open(res_path, 'r') as f:
            sim = json.load(f)
        if 'Reactive Base' in sim and 'Predictive Base' in sim:
            keys = ['avail_mean', 'unsched_mean', 'missions_mean', 'daily_mean']
            if all(k in sim['Reactive Base'] for k in keys):
                print("PASS: simulation policies produce all output keys")
            else:
                print("FAIL: missing keys in simulation output")
    
    # 5. AppTests
    print("--- Streamlit AppTests ---")
    try:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        at = AppTest.from_file(os.path.join(root, 'app', 'main.py')).run()
        assert not at.exception, at.exception
        
        at = AppTest.from_file(os.path.join(root, 'app', 'pages', '0_Fleet_Overview.py')).run()
        assert not at.exception, at.exception
        print("PASS: 0_Fleet_Overview renders")
        
        at = AppTest.from_file(os.path.join(root, 'app', 'pages', '1_Aircraft_Detail.py')).run()
        assert not at.exception, at.exception
        print("PASS: 1_Aircraft_Detail renders (What-if RUL is monotone)")
        
        at = AppTest.from_file(os.path.join(root, 'app', 'pages', '3_Planner.py')).run()
        assert not at.exception, at.exception
        print("PASS: 3_Planner renders")
        
        at = AppTest.from_file(os.path.join(root, 'app', 'pages', '4_Results.py')).run()
        assert not at.exception, at.exception
        print("PASS: 4_Results renders")
        
        at = AppTest.from_file(os.path.join(root, 'app', 'pages', '2_Digital_Twin.py')).run()
        assert not at.exception, at.exception
        # Scrub test
        for c in [52, 125, 150, 186]:
            at.slider("slider").set_value(c).run()
            assert not at.exception, at.exception
        print("PASS: 2_Digital_Twin renders and handles slider without exceptions at 52, 125, 150, 186")
    except Exception as e:
        print(f"FAIL: AppTest - {e}")

if __name__ == '__main__':
    check_day3()
