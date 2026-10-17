import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import os
import json
import pandas as pd
from datetime import datetime

def check_day2():
    print("--- Running Day 2 self-checks ---")
    passed = 0
    failed = 0

    def check(condition, pass_msg, fail_msg=None):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"PASS: {pass_msg}")
        else:
            failed += 1
            print(f"FAIL: {fail_msg or pass_msg}")
    
    # Tables existence
    tables = {
        'aircraft_master': ['aircraft_id', 'type', 'base', 'flights_per_day', 'total_flight_hours', 'engine_ids'],
        'maintenance_logs': ['log_id', 'aircraft_id', 'component', 'date', 'kind', 'action', 'downtime_days'],
        'parts_catalog': ['component', 'part_no', 'lead_time_days'],
        'spares_inventory': ['part_no', 'depot', 'qty_on_hand', 'reorder_level'],
        'workshops': ['workshop_id', 'location', 'capacity_slots', 'turnaround_days', 'specialisation'],
        'flight_schedule': ['date', 'aircraft_id', 'mission_id', 'priority']
    }
    
    dfs = {}
    for table, cols in tables.items():
        path = f'data/{table}.csv'
        if os.path.exists(path):
            df = pd.read_csv(path)
            dfs[table] = df
            check(all(c in df.columns for c in cols) and len(df) > 0,
                  f"{table} exists, has correct columns and rows",
                  f"{table} columns or rows incorrect")
        else:
            failed += 1
            print(f"FAIL: {table} missing")
            
    # flight_schedule covers 60 days
    if 'flight_schedule' in dfs:
        fs = dfs['flight_schedule']
        dates = pd.to_datetime(fs['date']).dt.date
        span = (dates.max() - dates.min()).days
        check(span >= 59, f"flight_schedule spans {span+1} days", f"flight_schedule spans only {span} days")
    else:
        failed += 1
        print("FAIL: flight_schedule missing")
            
    # IDs match
    if 'aircraft_master' in dfs:
        master_ids = set(dfs['aircraft_master']['aircraft_id'])
        ok = True
        for table in ['maintenance_logs', 'flight_schedule']:
            t_ids = set(dfs[table]['aircraft_id'])
            if not t_ids.issubset(master_ids):
                ok = False
        check(ok, "all aircraft_ids valid", "invalid aircraft_ids found")
    else:
        failed += 1
        print("FAIL: missing tables for aircraft_ids check")
        
    if 'parts_catalog' in dfs and 'spares_inventory' in dfs:
        cat_parts = set(dfs['parts_catalog']['part_no'])
        inv_parts = set(dfs['spares_inventory']['part_no'])
        check(inv_parts.issubset(cat_parts), "all spare part_nos valid", "invalid spare part_nos")
    else:
        failed += 1
        print("FAIL: missing tables for spare part_nos check")
        
    # Red part out of stock with lead time > days to failure
    preds = pd.read_csv('data/predictions.csv')
    reds = preds[preds['risk_level'] == 'red'].copy()
    if not reds.empty and 'parts_catalog' in dfs and 'spares_inventory' in dfs:
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from ml import config
        AS_OF = config.AS_OF
        as_of_dt = pd.to_datetime(AS_OF)
        reds['dtf'] = (pd.to_datetime(reds['predicted_failure_date']) - as_of_dt).dt.days
        reds['type'] = dfs['aircraft_master'].set_index('aircraft_id').loc[reds['aircraft_id']]['type'].values
        merged = reds.merge(dfs['parts_catalog'], on=['aircraft_id', 'component']).merge(dfs['spares_inventory'], on='part_no')
        order_now = merged[(merged['qty_on_hand'] <= 0) & (merged['lead_time_days'] >= merged['dtf'])]
        if not order_now.empty:
            passed += 1
            print("PASS: found RED part with 0 stock and long lead time")
            # print details for the report
            print(f"      -> {order_now['aircraft_id'].iloc[0]} / {order_now['component'].iloc[0]} (Part {order_now['part_no'].iloc[0]})")
        else:
            failed += 1
            print("FAIL: no RED part with 0 stock and long lead time")
            raise AssertionError("No RED part meets Spares ORDER NOW criteria")
            
    # DEMO_ENGINE_ID in held-out
    import json
    with open('docs/metrics.json', 'r') as f:
        metrics = json.load(f)
    
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ml import config
    DEMO_ENGINE_ID = config.DEMO_ENGINE_ID
    check(DEMO_ENGINE_ID in metrics.get('val_engines', []), "DEMO_ENGINE_ID is in held-out set", "DEMO_ENGINE_ID not in held-out set")
        
    # Metrics keys
    new_keys = ['rmse_overall_per_cycle', 'alert_lead_time_first_crossing', 'misses_first']
    check(all(k in metrics for k in new_keys), "metrics.json has Day 2 keys", "metrics.json missing Day 2 keys")
        
    # Replay causality
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ml.replay import replay, engine_for_aircraft
    from ml.config import DEMO_AIRCRAFT_ID
    try:
        r_full = replay(engine_for_aircraft(DEMO_AIRCRAFT_ID))
        # True causality test using truncation on 3 held-out engines, 3 cuts each
        try:
            import ml.replay as rep
            original_data = rep._DATA.copy()
            
            engines_to_test = metrics.get('val_engines', [])[:3]
            causality_ok = True
            for eng in engines_to_test:
                r_full = rep.replay(eng)
                eng_data = original_data[original_data['engine'] == eng].sort_values('cycle')
                cuts = [len(eng_data) // 4, len(eng_data) // 2, 3 * len(eng_data) // 4]
                for k in cuts:
                    if k < 10: continue
                    rep._DATA = original_data.drop(eng_data.index[k:]) # truncate
                    r_trunc = rep.replay(eng)
                    if abs(r_full['predicted_rul'].iloc[k-1] - r_trunc['predicted_rul'].iloc[k-1]) > 1e-5:
                        causality_ok = False
            
            check(causality_ok, "Truncated prediction matches full-run prediction across 3 engines x 3 cuts (causality verified)", "Prediction mismatch on truncation")
                
            # restore
            rep._DATA = original_data
        except Exception as e:
            failed += 1
            print(f"FAIL: Truncation test error - {e}")
            
    except Exception as e:
        failed += 1
        print(f"FAIL: Replay error - {e}")
        
    print("--- Streamlit AppTests ---")
    try:
        from streamlit.testing.v1 import AppTest
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        at_main = AppTest.from_file(os.path.join(root, "app/main.py")).run(timeout=60)
        assert not at_main.exception, f"Exception in app/main.py: {at_main.exception}"
        passed += 1
        print("PASS: app/main.py renders without exceptions")
        
        at_ad = AppTest.from_file(os.path.join(root, "app/pages/1_Aircraft_Detail.py")).run(timeout=60)
        assert not at_ad.exception, f"Exception in 1_Aircraft_Detail.py: {at_ad.exception}"
        passed += 1
        print("PASS: app/pages/1_Aircraft_Detail.py renders without exceptions")
        
        at_dt = AppTest.from_file(os.path.join(root, "app/pages/2_Digital_Twin.py")).run(timeout=60)
        assert not at_dt.exception, f"Exception in 2_Digital_Twin.py: {at_dt.exception}"
        
        # Interact with the slider
        at_dt.slider("slider").set_value(50).run(timeout=60)
        assert not at_dt.exception, f"Exception after slider interaction: {at_dt.exception}"
        passed += 1
        print("PASS: app/pages/2_Digital_Twin.py renders and handles slider without exceptions")
        
    except Exception as e:
        failed += 1
        print(f"FAIL: Streamlit AppTest - {e}")
        
    print(f"{passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)
        
if __name__ == '__main__':
    check_day2()





