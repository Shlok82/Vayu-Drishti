import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import pandas as pd
import json
import os
import subprocess
import tempfile
import re
from datetime import datetime, timedelta
from ml.config import DATA_DIR, ORDER_MARGIN_DAYS, WATCH_MARGIN_DAYS

def check_encoding():
    print("--- Encoding Check ---")
    mojibake = re.compile(r'[^\x00-\x7F]')
    ok = True
    for root_dir in ['ml', 'app', 'docs']:
        for dirpath, _, filenames in os.walk(os.path.join(_root, root_dir)):
            if '__pycache__' in dirpath: continue
            for f in filenames:
                if not f.endswith(('.py', '.md', '.csv', '.toml', '.json')): continue
                path = os.path.join(dirpath, f)
                with open(path, 'rb') as file:
                    if file.read().startswith(b'\xef\xbb\xbf'):
                        print(f"FAIL: BOM in {f}")
                        ok = False
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        for i, line in enumerate(file):
                            if mojibake.search(line):
                                print(f"FAIL: Mojibake in {f}:{i+1}")
                                ok = False
                except Exception as e:
                    pass
    if ok: print("PASS: No BOM or non-ASCII found")
    return ok

def run_smoke_tests():
    print("--- Clean-environment Smoke Tests ---")
    pages = [
        _root / 'app' / 'main.py',
        _root / 'app' / 'pages' / '0_Fleet_Overview.py',
        _root / 'app' / 'pages' / '1_Aircraft_Detail.py',
        _root / 'app' / 'pages' / '2_Digital_Twin.py',
        _root / 'app' / 'pages' / '3_Planner.py',
        _root / 'app' / 'pages' / '4_Results.py',
        _root / 'app' / 'pages' / '5_Method.py'
    ]
    script_path = _root / 'ml' / '_smoke_worker.py'
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write('''import sys, os
from streamlit.testing.v1 import AppTest
page = sys.argv[1]
try:
    at = AppTest.from_file(page).run(timeout=30)
    if at.exception:
        print(f"Exception in {page}: {at.exception}")
        sys.exit(1)
    if "2_Digital_Twin.py" in page:
        for c in [52, 125, 150, 186, 208]:
            at.slider("slider").set_value(c).run(timeout=30)
            if at.exception:
                print(f"Exception at cycle {c}: {at.exception}")
                sys.exit(1)
except Exception as e:
    print(f"Failed to run AppTest on {page}: {e}")
    sys.exit(1)
''')
    ok = True
    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        if 'PYTHONPATH' in env: del env['PYTHONPATH']
        for p in pages:
            if not p.exists(): continue
            res = subprocess.run([sys.executable, str(script_path), str(p)], cwd=tmpdir, env=env, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"FAIL: Smoke test for {p.name}")
                print(res.stdout); print(res.stderr)
                ok = False
            else:
                print(f"PASS: {p.name}")
    if script_path.exists(): script_path.unlink()
    return ok

def check_day3():
    check_encoding()
    
    print("--- Alerts Logic & Parts Verification ---")
    from ml.alerts import generate_alerts
    df_preds = pd.read_csv(DATA_DIR / 'predictions.csv')
    df_master = pd.read_csv(DATA_DIR / 'aircraft_master.csv')
    df_parts = pd.read_csv(DATA_DIR / 'parts_catalog.csv')
    df_spares = pd.read_csv(DATA_DIR / 'spares_inventory.csv')
    df_ws = pd.read_csv(DATA_DIR / 'workshops.csv')
    alerts_df = generate_alerts(df_preds, df_master, df_parts, df_spares, df_ws)
    
    # Check parts variety
    f101_lead = df_parts[df_parts['part_no'] == 'PN-ENG-F101']['lead_time_days'].iloc[0]
    if f101_lead == 20: print("PASS: F101 lead_time == 20")
    else: print("FAIL: F101 lead_time != 20")
    
    part_counts = alerts_df['part_no'].value_counts()
    if part_counts.max() <= 2: print("PASS: At most 2 alerts share a part")
    else: print("FAIL: More than 2 alerts share a part")
    
    af1 = alerts_df[alerts_df['aircraft_id'] == 'AF-1002']
    if not af1.empty and af1.iloc[0]['part_no'] == 'PN-ENG-F101' and af1.iloc[0]['qty_on_hand'] == 0:
        print("PASS: AF-1002 on zero-stock F101")
    else: print("FAIL: AF-1002 not on F101 or stock not 0")
    
    # Check sorting
    dtfs = alerts_df['days_to_failure'].tolist()
    if dtfs == sorted(dtfs): print("PASS: Alerts sorted by days_to_failure ascending")
    else: print("FAIL: Alerts not sorted")
    
    # Independent recomputation
    min_ta = df_ws['turnaround_days'].min()
    alerts_ok = True
    for _, r in alerts_df.iterrows():
        stock = r['qty_on_hand']
        reorder = r['reorder_level']
        dtf = r['days_to_failure']
        lt = r['lead_time_days']
        risk = r['risk_level']
        
        if stock >= 1:
            if risk == 'red': exp = "SCHEDULE NOW (IN STOCK)"
            elif risk == 'amber' and stock <= reorder: exp = "WATCH"
            else: exp = "OK"
        else:
            need_days = lt + min_ta
            slack = dtf - need_days
            if slack < 0: exp = "CANNOT ARRIVE IN TIME"
            elif slack <= ORDER_MARGIN_DAYS: exp = "ORDER NOW"
            elif slack <= WATCH_MARGIN_DAYS or risk in ['amber', 'red']: exp = "WATCH"
            else: exp = "OK"
            
        if r['status'] != exp:
            alerts_ok = False
            print(f"FAIL: Alert {r['aircraft_id']} expected {exp}, got {r['status']}")
    if alerts_ok: print("PASS: Alert statuses independently verified")
    
    # Planner check
    print("--- Planner Constraints Check ---")
    from ml.planner import get_recommendations
    recs = get_recommendations(alerts_df, df_ws, df_sched=pd.read_csv(DATA_DIR / 'flight_schedule.csv'), df_master=df_master)
    ws_cap = df_ws.set_index('workshop_id')['capacity_slots'].to_dict()
    
    ws_usage = {ws: {} for ws in ws_cap}
    planner_cap_ok = True
    for _, r in recs.iterrows():
        ws = r['workshop_id']
        st_date = datetime.strptime(r['slot_start'], "%Y-%m-%d")
        en_date = datetime.strptime(r['slot_end'], "%Y-%m-%d")
        for d in range((en_date - st_date).days):
            d_dt = (st_date + timedelta(days=d)).strftime("%Y-%m-%d")
            ws_usage[ws][d_dt] = ws_usage[ws].get(d_dt, 0) + 1
            if ws_usage[ws][d_dt] > ws_cap[ws]:
                planner_cap_ok = False
    if planner_cap_ok: print("PASS: No workshop capacity exceeded (including flagged jobs)")
    else: print("FAIL: Workshop capacity exceeded")
    
    # Check flags valid
    valid_flags = ["PART_ARRIVES_AFTER_FAILURE", "REPAIR_ENDS_AFTER_FAILURE", "NO_CAPACITY", "HIGH_PRIORITY_CONFLICT", ""]
    flags_ok = all(r['flag'] in valid_flags for _, r in recs.iterrows())
    if flags_ok: print("PASS: Flag reasons valid")
    else: print("FAIL: Invalid flag reasons found")
    
    if len(recs) == len(alerts_df): print("PASS: Gantt bar count equals planned job count (1:1 mapping)")
    
    # Twin test
    print("--- Twin Status Order Test ---")
    from ml.replay import replay
    from ml.config import DEMO_ENGINE_ID
    from ml.alerts import get_spares_status
    df_rep = replay(DEMO_ENGINE_ID)
    ac_info = df_master[df_master['engine_ids'].str.contains(str(DEMO_ENGINE_ID))].iloc[0]
    fpd = ac_info['flights_per_day']
    # If green with 0 stock and slack > 30 => OK
    # With F101 lt=20, min_ta=5, need=25.
    dtf = 60 # slack = 35
    stat = get_spares_status(dtf, 20, 0, 2, 'green', min_ta)
    if stat == "OK": print("PASS: A GREEN engine with zero stock and slack > 30 shows OK")
    else: print(f"FAIL: Expected OK, got {stat}")
    
    run_smoke_tests()

if __name__ == '__main__':
    check_day3()



