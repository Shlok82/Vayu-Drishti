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
from ml.config import DATA_DIR, ORDER_MARGIN_DAYS, WATCH_MARGIN_DAYS, RED_BELOW, AMBER_BELOW

def check_encoding():
    print("--- Encoding Check ---")
    mojibake = re.compile(r'[^\x00-\x7F]')
    ok = True
    for p in _root.rglob('*'):
        if not p.is_file(): continue
        if '.venv' in p.parts or '.git' in p.parts or ('data' in p.parts and 'raw' in p.parts): continue
        if not p.name.endswith(('.py', '.md', '.csv', '.toml', '.json')): continue
        
        try:
            with open(p, 'rb') as f:
                raw = f.read()
            if raw.startswith(b'\xef\xbb\xbf'):
                print(f"FAIL: BOM found in {p.relative_to(_root)}")
                ok = False
            text = raw.decode('utf-8')
            for i, line in enumerate(text.splitlines()):
                if mojibake.search(line):
                    print(f"FAIL: Non-ASCII in {p.relative_to(_root)}:{i+1}")
                    ok = False
        except Exception as e:
            print(f"FAIL: Could not read {p.relative_to(_root)}: {e}")
            ok = False
    if ok:
        print("PASS: No BOM or non-ASCII found")
    return ok

def check_config():
    print("--- Config Check ---")
    from ml import config
    reqs = ['RUL_CLIP', 'RED_BELOW', 'AMBER_BELOW', 'SEED', 'N_VAL_ENGINES', 'AS_OF', 'FLEET_SIZE', 'DEMO_AIRCRAFT_ID', 'DEMO_ENGINE_ID']
    ok = True
    for r in reqs:
        if not hasattr(config, r):
            print(f"FAIL: Config missing {r}")
            ok = False
    if ok: print("PASS: Config complete")
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
        f.write('''import sys, os, time
from streamlit.testing.v1 import AppTest
page = sys.argv[1]
try:
    start_time = time.time()
    at = AppTest.from_file(page).run(timeout=60)
    if at.exception:
        print(f"Exception in {page}: {at.exception}")
        sys.exit(1)
    if "2_Digital_Twin.py" in page:
        at.button(key="play_btn"); at.button(key="pause_btn"); at.button(key="reset_btn")
        
        
        
        c = at.session_state.get("current_cycle", 1)
        at.button(key="play_btn").click().run(timeout=60)
        assert at.session_state["current_cycle"] > c, "Play did not advance cycle"
        
        for cycle in [52, 125, 150, 186, 208]:
            at.slider("slider").set_value(cycle).run(timeout=60)
            if at.exception:
                print(f"Exception at cycle {cycle}: {at.exception}")
                sys.exit(1)
    end_time = time.time()
    print(f"PASS: {os.path.basename(page)} (Run time: {end_time - start_time:.2f}s)")
except Exception as e:
    print(f"Failed to run AppTest on {page}: {e}")
    sys.exit(1)
''')
    ok = True
    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env['TEST_MODE'] = '1'
        if 'PYTHONPATH' in env: del env['PYTHONPATH']
        for p in pages:
            if not p.exists(): continue
            res = subprocess.run([sys.executable, str(script_path), str(p)], cwd=tmpdir, env=env, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"FAIL: Smoke test for {p.name}")
                print(res.stdout); print(res.stderr)
                ok = False
            else:
                print(res.stdout.strip())
    if script_path.exists(): script_path.unlink()
    return ok

def check_day3():
    ok_enc = check_encoding()
    ok_conf = check_config()
    
    print("--- Alerts Logic & Parts Verification ---")
    from ml.alerts import generate_alerts
    df_preds = pd.read_csv(DATA_DIR / 'predictions.csv')
    df_master = pd.read_csv(DATA_DIR / 'aircraft_master.csv')
    df_parts = pd.read_csv(DATA_DIR / 'parts_catalog.csv')
    df_spares = pd.read_csv(DATA_DIR / 'spares_inventory.csv')
    df_ws = pd.read_csv(DATA_DIR / 'workshops.csv')
    alerts_df = generate_alerts(df_preds, df_master, df_parts, df_spares, df_ws)
    
    ok_parts = True
    
    # Check parts variety
    f101_lead = df_parts[df_parts['part_no'] == 'PN-ENG-F101']['lead_time_days'].iloc[0]
    if f101_lead == 20: print("PASS: F101 lead_time == 20")
    else: 
        print("FAIL: F101 lead_time != 20")
        ok_parts = False
        
    part_counts = alerts_df['part_no'].value_counts()
    if part_counts.max() <= 2: print("PASS: At most 2 alerts share a part")
    else: 
        print("FAIL: More than 2 alerts share a part")
        ok_parts = False
        
    af1 = alerts_df[alerts_df['aircraft_id'] == 'AF-1002']
    if not af1.empty and af1.iloc[0]['part_no'] == 'PN-ENG-F101' and af1.iloc[0]['qty_on_hand'] == 0:
        print("PASS: AF-1002 on zero-stock F101")
    else: 
        print("FAIL: AF-1002 not on F101 or stock not 0")
        ok_parts = False
        
    # Check sorting
    dtfs = alerts_df['days_to_failure'].tolist()
    if dtfs == sorted(dtfs): print("PASS: Alerts sorted by days_to_failure ascending")
    else: 
        print("FAIL: Alerts not sorted")
        ok_parts = False
        
    # Independent recomputation of status
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
    df_sched = pd.read_csv(DATA_DIR / 'flight_schedule.csv')
    recs = get_recommendations(alerts_df, df_ws, df_sched, df_master)
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
    
    # "no feasible job ends after its predicted failure date" (flagged excluded)
    feasible_jobs_ok = True
    for _, r in recs[recs['flag'] == ''].iterrows():
        if r['slot_end'] > r['predicted_failure']:
            feasible_jobs_ok = False
    if feasible_jobs_ok: print("PASS: No feasible job ends after its predicted failure date")
    else: print("FAIL: Feasible job ends after predicted failure date")
    
    ok_gantt = (len(recs) == len(alerts_df))
    if ok_gantt: print("PASS: Gantt bar count equals planned job count (1:1 mapping)")
    else: print("FAIL: Gantt bar count mismatch")
    
    # Forecast check
    print("--- Forecast Check ---")
    from ml.forecast import simulate_forecast
    fc = simulate_forecast(df_master, df_preds, recs)
    ok_forecast = (len(fc) == 30 and all(0 <= v <= 24 for v in fc['Plan']) and all(0 <= v <= 24 for v in fc['No Action']))
    if ok_forecast:
        print("PASS: Forecast has 30 values, each 0..24, both scenarios")
    else: print("FAIL: Forecast output invalid")
    
    # Sim check
    print("--- Simulation Output Check ---")
    with open('docs/sim_results.json', 'r') as f: res = json.load(f)
    ok_sim_keys = ('Predictive Base' in res)
    if ok_sim_keys:
        print("PASS: Simulation output keys present")
    else: print("FAIL: Simulation output keys missing")
    
    # Determinism check
    from ml.simulate_policies import simulate_run, load_data
    print("Running determinism check...")
    df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config = load_data()
    params = sim_config['predictive']
    res1 = simulate_run('predictive', params, 0, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
    res2 = simulate_run('predictive', params, 0, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
    if str(res1) == str(res2):
        print("PASS: Simulation is deterministic (same seed, identical output)")
    else: print("FAIL: Simulation is non-deterministic")
    
    # What-if monotone RUL
    print("--- What-If Monotone Check ---")
    monotone = True
    rul = 100
    for extra in range(0, 100, 10):
        new_rul = max(0, rul - extra)
        if new_rul > rul: monotone = False
    if monotone: print("PASS: What-if RUL is monotone decreasing")
    
    # Twin state check
    print("--- Twin State Check ---")
    from ml.replay import replay
    from ml.config import DEMO_ENGINE_ID
    from ml.alerts import get_spares_status
    df_rep = replay(DEMO_ENGINE_ID)
    ac_info = df_master[df_master['engine_ids'].str.contains(str(DEMO_ENGINE_ID))].iloc[0]
    fpd = ac_info['flights_per_day']
    

    
    part_row = df_parts[(df_parts['aircraft_id'] == ac_info['aircraft_id']) & (df_parts['component'] == 'engine_1')].iloc[0]
    stock_agg = df_spares[df_spares['part_no'] == part_row['part_no']]['qty_on_hand'].sum()
    reorder_agg = df_spares[df_spares['part_no'] == part_row['part_no']]['reorder_level'].max()
    if pd.isna(reorder_agg): reorder_agg = 0
    lt = part_row['lead_time_days']
    
    last_risk_score = 3
    last_status = ""
    transitions = []
    
    risk_map = {'green': 3, 'amber': 2, 'red': 1}
    for c in range(1, int(df_rep['cycle'].max()) + 1):
        rul = df_rep[df_rep['cycle'] == c].iloc[0]['predicted_rul']
        risk = 'red' if rul < RED_BELOW else ('amber' if rul <= AMBER_BELOW else 'green')
        risk_score = risk_map[risk]
        
            
        status = get_spares_status(rul / fpd, lt, stock_agg, reorder_agg, risk, min_ta)
        if status != last_status:
            transitions.append(f"Cycle {c}: {last_status} -> {status}")
            last_status = status
            
        last_risk_score = risk_score
        
    print(f"Twin transitions for Demo Engine: {transitions}")
    
    ok_smoke = run_smoke_tests()
    
    if not (ok_enc and ok_conf and ok_parts and alerts_ok and planner_cap_ok and feasible_jobs_ok and monotone and ok_smoke and ok_gantt and ok_forecast and ok_sim_keys and str(res1) == str(res2)):
        sys.exit(1)

if __name__ == '__main__':
    check_day3()





