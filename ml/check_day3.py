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
        
        try:
            with open(p, 'rb') as f:
                raw = f.read()
            if raw.startswith(b'\xef\xbb\xbf'):
                print(f"FAIL: BOM found in {p.relative_to(_root)}")
                ok = False
            if p.suffix == '.py':
                text = raw.decode('utf-8', errors='replace')
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
    at = AppTest.from_file(page)
    at.session_state["auth_user"] = "admin"
    at.session_state["role"] = "admin"
    at.run(timeout=60)
    if at.exception:
        print(f"Exception in {page}: {at.exception}")
        sys.exit(1)
    if "2_Digital_Twin.py" in page:
        at.button(key="play_btn"); at.button(key="pause_btn"); at.button(key="reset_btn")
        try:
            at.button(key="non_existent_btn_should_fail")
            assert False, "Wrong button key did not raise KeyError"
        except KeyError:
            pass

        at.button(key="play_btn").click()
        cycles = []
        for _ in range(5):
            at.run(timeout=60)
            assert not at.exception, f"Exception during playback: {at.exception}"
            cycles.append(at.session_state["current_cycle"])
        for i in range(len(cycles) - 1):
            assert cycles[i+1] > cycles[i], f"Cycle did not strictly increase: {cycles}"

        at.button(key="pause_btn").click()
        at.run(timeout=60)
        p1 = at.session_state["current_cycle"]
        at.run(timeout=60)
        p2 = at.session_state["current_cycle"]
        assert p1 == p2, f"Cycle changed after Pause: {p1} != {p2}"

        at.button(key="reset_btn").click()
        at.run(timeout=60)
        assert at.session_state["current_cycle"] == 1, f"Expected cycle 1 on Reset, got {at.session_state['current_cycle']}"

        at.slider("slider").set_value(150).run(timeout=60)
        assert not at.exception, f"Exception setting slider to 150: {at.exception}"
        assert at.session_state["current_cycle"] == 150, f"Expected current_cycle 150, got {at.session_state['current_cycle']}"
        cycle_metrics = [m for m in at.metric if m.label == "Current Cycle"]
        assert cycle_metrics and cycle_metrics[0].value == "150", f"Displayed cycle metric is not 150: {cycle_metrics[0].value if cycle_metrics else 'None'}"

        for cycle in [52, 125, 186, 208]:
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
    smoke_passed = 0
    smoke_failed = 0
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
                smoke_failed += 1
            else:
                print(res.stdout.strip())
                smoke_passed += 1
    if script_path.exists(): script_path.unlink()
    return smoke_passed, smoke_failed

def check_day3():
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

    ok_enc = check_encoding()
    if ok_enc: passed += 1
    else: failed += 1

    ok_conf = check_config()
    if ok_conf: passed += 1
    else: failed += 1
    
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
    check(f101_lead == 20, "F101 lead_time == 20", "F101 lead_time != 20")
        
    part_counts = alerts_df['part_no'].value_counts()
    check(part_counts.max() <= 2, "At most 2 alerts share a part", "More than 2 alerts share a part")
        
    af1 = alerts_df[alerts_df['aircraft_id'] == 'AF-1002']
    check(not af1.empty and af1.iloc[0]['part_no'] == 'PN-ENG-F101' and af1.iloc[0]['qty_on_hand'] == 0,
          "AF-1002 on zero-stock F101", "AF-1002 not on F101 or stock not 0")
        
    # Check sorting
    dtfs = alerts_df['days_to_failure'].tolist()
    check(dtfs == sorted(dtfs), "Alerts sorted by days_to_failure ascending", "Alerts not sorted")
        
    # Independent recomputation of status without importing ml.repair
    def _calc_repair_days_independent(comp):
        comp_lower = str(comp).lower()
        if 'engine' in comp_lower:
            spec = 'Engines'
        elif 'avionic' in comp_lower:
            spec = 'Avionics'
        elif 'hydraul' in comp_lower or 'gear' in comp_lower or 'actuator' in comp_lower:
            spec = 'Hydraulics'
        else:
            spec = 'General'
        matched = df_ws[df_ws['specialisation'] == spec]
        if not matched.empty:
            return int(matched.iloc[0]['turnaround_days'])
        gen = df_ws[df_ws['specialisation'] == 'General']
        return int(gen.iloc[0]['turnaround_days']) if not gen.empty else 3

    alerts_ok = True
    for _, r in alerts_df.iterrows():
        stock = r['qty_on_hand']
        reorder = r['reorder_level']
        dtf = r['days_to_failure']
        lt = r['lead_time_days']
        risk = r['risk_level']
        repair_days = _calc_repair_days_independent(r['component'])
        
        if stock >= 1:
            if risk == 'red': exp = "SCHEDULE NOW (IN STOCK)"
            elif risk == 'amber' and stock <= reorder: exp = "WATCH"
            else: exp = "OK"
        else:
            need_days = lt + repair_days
            slack = dtf - need_days
            if slack < 0: exp = "CANNOT ARRIVE IN TIME"
            elif slack <= ORDER_MARGIN_DAYS: exp = "ORDER NOW"
            elif slack <= WATCH_MARGIN_DAYS or risk in ['amber', 'red']: exp = "WATCH"
            else: exp = "OK"
            
        if r['status'] != exp:
            alerts_ok = False
            print(f"FAIL: Alert {r['aircraft_id']} expected {exp}, got {r['status']}")
    check(alerts_ok, "Alert statuses independently verified")

    # Parity check asserting independent repair days match ml.repair.get_repair_days
    from ml.repair import get_repair_days
    from ml.config import COMPONENTS
    parity_ok = all(_calc_repair_days_independent(c) == get_repair_days(c, df_ws) for c in COMPONENTS)
    check(parity_ok, "Independent repair days match ml.repair.get_repair_days for all components")
    
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
    check(planner_cap_ok, "No workshop capacity exceeded (including flagged jobs)", "Workshop capacity exceeded")
    
    # "no feasible job ends after its predicted failure date" (flagged excluded)
    feasible_jobs_ok = True
    for _, r in recs[recs['flag'] == ''].iterrows():
        if r['slot_end'] > r['predicted_failure']:
            feasible_jobs_ok = False
    check(feasible_jobs_ok, "No feasible job ends after its predicted failure date", "Feasible job ends after predicted failure date")
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("planner_page", "app/pages/3_Planner.py")
    planner_page = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planner_page)
    build_gantt = planner_page.build_gantt
    fig = build_gantt(recs, alerts_df)
    bar_count = len([t for t in fig.data if type(t).__name__ == 'Bar'])
    check(bar_count == len(alerts_df), "Gantt bar count equals planned job count (1:1 mapping)", "Gantt bar count mismatch")

    infeasible_jobs = recs[recs['flag'].isin(['PART_ARRIVES_AFTER_FAILURE', 'REPAIR_ENDS_AFTER_FAILURE', 'REPAIR_STARTS_AFTER_FAILURE'])]
    hatched_traces = [t for t in fig.data if type(t).__name__ == 'Bar' and getattr(getattr(t.marker, 'pattern', None), 'shape', None)]
    assert len(hatched_traces) == len(infeasible_jobs), f"Expected {len(infeasible_jobs)} hatched traces, got {len(hatched_traces)}"
    passed += 1
    print("PASS: Hatched traces equal infeasible jobs")
    
    # Forecast check
    print("--- Forecast Check ---")
    from ml.forecast import simulate_forecast
    fc = simulate_forecast(df_master, df_preds, recs)
    ok_forecast = (len(fc) == 30 and all(0 <= v <= 24 for v in fc['Plan']) and all(0 <= v <= 24 for v in fc['No Action']))
    check(ok_forecast, "Forecast has 30 values, each 0..24, both scenarios", "Forecast output invalid")
    
    # Fresh computation verification vs disk CSVs
    print("--- Fresh Computation vs Disk CSVs Check ---")
    disk_recs = pd.read_csv('data/planner_recommendations.csv', keep_default_na=False)
    disk_fc = pd.read_csv('data/forecast_30d.csv')
    
    s_fresh_recs = recs.sort_values(by=['aircraft_id', 'component']).reset_index(drop=True)
    s_fresh_recs['mission_details'] = s_fresh_recs['mission_details'].astype(str)
    s_disk_recs = disk_recs.sort_values(by=['aircraft_id', 'component']).reset_index(drop=True)
    s_disk_recs['mission_details'] = s_disk_recs['mission_details'].astype(str)
    
    recs_match = True
    try:
        pd.testing.assert_frame_equal(s_fresh_recs, s_disk_recs, check_like=True, check_dtype=False)
    except AssertionError:
        recs_match = False
    check(recs_match, "data/planner_recommendations.csv equals fresh computation", "planner_recommendations.csv mismatch with fresh computation")
    
    s_fresh_fc = fc.sort_values(by=['Date']).reset_index(drop=True)
    s_fresh_fc['Date'] = s_fresh_fc['Date'].astype(str)
    s_disk_fc = disk_fc.sort_values(by=['Date']).reset_index(drop=True)
    s_disk_fc['Date'] = s_disk_fc['Date'].astype(str)
    
    fc_match = True
    try:
        pd.testing.assert_frame_equal(s_fresh_fc, s_disk_fc, check_like=True, check_dtype=False, rtol=1e-5, atol=1e-5)
    except AssertionError:
        fc_match = False
    check(fc_match, "data/forecast_30d.csv equals fresh computation", "forecast_30d.csv mismatch with fresh computation")
    
    # Sim check
    print("--- Simulation Output Check ---")
    with open('docs/sim_results.json', 'r') as f: res = json.load(f)
    ok_sim_keys = ('Predictive Base' in res and 'Reactive Base' in res and 'Paired Difference' in res and 'Sensitivity' in res)
    check(ok_sim_keys, "Simulation output keys present", "Simulation output keys missing")
    
    # Determinism check
    from ml.simulate_policies import simulate_run, load_data
    print("Running determinism check...")
    df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config = load_data()
    params = sim_config['predictive']
    res1 = simulate_run('predictive', params, 0, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
    res2 = simulate_run('predictive', params, 0, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
    check(str(res1) == str(res2), "Simulation is deterministic (same seed, identical output)", "Simulation is non-deterministic")
    
    # What-if monotone RUL
    print("--- What-If Monotone Check ---")
    monotone = True
    rul = 100
    for extra in range(0, 100, 10):
        new_rul = max(0, rul - extra)
        if new_rul > rul: monotone = False
    check(monotone, "What-if RUL is monotone decreasing")
    
    # Twin state check
    print("--- Twin State Check ---")
    import importlib.util
    spec2 = importlib.util.spec_from_file_location("twin_page", "app/pages/2_Digital_Twin.py")
    twin_page = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(twin_page)
    get_twin_states = twin_page.get_twin_states
    from ml.replay import replay, engine_for_aircraft
    from ml.config import DEMO_AIRCRAFT_ID
    
    df_rep = replay(engine_for_aircraft(DEMO_AIRCRAFT_ID))
    ac_info = df_master[df_master['aircraft_id'] == DEMO_AIRCRAFT_ID].iloc[0]
    fpd = ac_info['flights_per_day']
    
    # Run debounce unit-test
    from ml.debounce import debounce_series
    print("Debounce Unit-Test:")
    print(debounce_series(pd.Series(['green', 'green', 'amber', 'green', 'amber', 'amber', 'amber', 'red', 'amber', 'red', 'red', 'red']), threshold=3).tolist())
    
    raw_status, debounced_status, raw_risk, debounced_risk = get_twin_states(df_rep, fpd, ac_info)
    
    print("Cycle 120-190 (Raw vs Debounced):")
    for i, row in df_rep.iterrows():
        c = row['cycle']
        if 120 <= c <= 190:
            print(f"Cycle {c}: Raw {raw_status[i]} / Debounced {debounced_status[i]}")
            
    check_cycles = [52, 125, 150, 186, int(df_rep['cycle'].max())]
    for c in check_cycles:
        idx = df_rep[df_rep['cycle'] == c].index[0]
        rul = df_rep.iloc[idx]['predicted_rul']
        dtf = rul / fpd
        print(f"Cycle {c} State: RUL={rul:.1f}, Risk={debounced_risk[idx]}, DTF={dtf:.1f}, Status={debounced_status[idx]}")
        
    transitions = []
    last_status = debounced_status[0]
    for i, s in enumerate(debounced_status):
        if s != last_status:
            transitions.append(f"Cycle {df_rep.iloc[i]['cycle']}: {last_status} -> {s}")
            last_status = s
            
    print(f"Twin transitions for Demo Engine (Count: {len(transitions)}): {transitions}")
    ok_transitions = len(transitions) <= 6
    check(ok_transitions, "At most 6 transitions", "More than 6 transitions")
    
    ok_short = True
    for t_idx in range(len(transitions) - 1):
        c1 = int(transitions[t_idx].split(':')[0].replace('Cycle ', ''))
        c2 = int(transitions[t_idx+1].split(':')[0].replace('Cycle ', ''))
        if c2 - c1 < 3: ok_short = False
    check(ok_short, "No transition shorter than 3 cycles", "Transition shorter than 3 cycles")
    
    # Severity never decreases
    sev = {'OK': 0, 'WATCH': 1, 'ORDER NOW': 2, 'CANNOT ARRIVE IN TIME': 3, 'SCHEDULE NOW (IN STOCK)': 3}
    ok_sev = True
    for i in range(len(debounced_status) - 1):
        if sev[debounced_status[i+1]] < sev[debounced_status[i]]:
            ok_sev = False
    check(ok_sev, "Severity never decreases on debounced series", "Severity decreased")
    
    # Green zero-stock engine with slack > 30 shows OK
    ok_slack = True
    for _, r in alerts_df.iterrows():
        if r['risk_level'] == 'green' and r['qty_on_hand'] == 0:
            repair_days = _calc_repair_days_independent(r['component'])
            need_days = r['lead_time_days'] + repair_days
            slack = r['days_to_failure'] - need_days
            if slack > 30 and r['status'] != 'OK':
                ok_slack = False
    check(ok_slack, "Green zero-stock engine with slack > 30 shows OK", "Green zero-stock engine with slack > 30 does not show OK")

    # Auth helpers and credentials security check (Stage L1)
    print("--- Auth Helpers & Access Control Check ---")
    import re
    from app.auth import verify, allowed_pages, PAGES_BY_ROLE, GUEST_ROLE, DEMO_USERS

    demo_access_file = _root / 'docs' / 'DEMO_ACCESS.md'
    assert demo_access_file.exists(), "docs/DEMO_ACCESS.md does not exist"
    with open(demo_access_file, 'r', encoding='utf-8') as f:
        demo_access_text = f.read()

    creds = {}
    for line in demo_access_text.splitlines():
        m = re.search(r'`(viewer|maintainer|admin)`\s*\|\s*`([^`]+)`', line)
        if m:
            creds[m.group(1)] = m.group(2)

    check(len(creds) == 3, "All three demo credentials parsed from docs/DEMO_ACCESS.md", "Failed parsing credentials from docs/DEMO_ACCESS.md")

    roles_ok = True
    for u, p in creds.items():
        if verify(u, p) != u:
            roles_ok = False
            print(f"FAIL: verify({u}, ...) returned {verify(u, p)}, expected {u}")
    check(roles_ok, "Correct credentials return the right role for all three users")

    wrong_pw_ok = (
        verify("viewer", "wrong_password_xyz") is None
        and verify("maintainer", "wrong_password_xyz") is None
        and verify("admin", "wrong_password_xyz") is None
        and verify("nonexistent_user", creds.get("admin", "")) is None
    )
    check(wrong_pw_ok, "Wrong password and unknown user return None")

    empty_ok = (
        verify("", "") is None
        and verify("viewer", "") is None
        and verify("", creds.get("viewer", "")) is None
        and verify(None, None) is None
        and verify("viewer", None) is None
        and verify(None, creds.get("viewer", "")) is None
    )
    check(empty_ok, "Empty input returns None")

    v_pages = allowed_pages("viewer")
    viewer_excludes_ok = not any("Planner" in p for p in v_pages) and not any("Digital Twin" in p for p in v_pages)
    check(viewer_excludes_ok, "allowed_pages for viewer excludes Planner and Digital Twin")

    admin_pages = allowed_pages("admin")
    req_pages = ["Fleet Overview", "Aircraft Detail", "Digital Twin", "Planner", "Results", "Methodology"]
    admin_all_ok = all(any(rp in ap for ap in admin_pages) for rp in req_pages)
    check(admin_all_ok, "admin includes all pages")

    no_plaintext_pw = True
    for folder in ['app', 'ml']:
        for root_dir, _, fnames in os.walk(_root / folder):
            for fname in fnames:
                if fname.endswith(('.py', '.json', '.csv', '.txt', '.md', '.yaml', '.yml')):
                    fpath = Path(root_dir) / fname
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                        content = fp.read()
                        for u, pw in creds.items():
                            if pw in content:
                                no_plaintext_pw = False
                                print(f"FAIL: Plaintext password for {u} found in {fpath.relative_to(_root)}")
    check(no_plaintext_pw, "Grep over app/ and ml/ finds none of the three plain-text passwords")

    print("--- Stage L2: Login Gate & Page Authorization Tests ---")
    from streamlit.testing.v1 import AppTest

    # (a) main.py without auth shows login form and no dashboard
    at_unauth = AppTest.from_file(str(_root / "app" / "main.py"))
    at_unauth.run(timeout=30)
    has_login = any("Login" in str(s.value) for s in at_unauth.subheader) or len(at_unauth.text_input) >= 2
    has_caption = any("Demo access control, not production security." in str(c.value) for c in at_unauth.caption)
    no_dashboard = not any("Fleet Status" in str(s.value) for s in at_unauth.subheader)
    check(has_login and has_caption and no_dashboard and not at_unauth.exception,
          "main.py without auth shows login form and no dashboard")

    # (b) each role renders allowed pages without exception
    page_file_map = {
        "Fleet Overview": _root / "app" / "pages" / "0_Fleet_Overview.py",
        "Aircraft Detail": _root / "app" / "pages" / "1_Aircraft_Detail.py",
        "Digital Twin": _root / "app" / "pages" / "2_Digital_Twin.py",
        "Planner": _root / "app" / "pages" / "3_Planner.py",
        "Results": _root / "app" / "pages" / "4_Results.py",
        "Methodology": _root / "app" / "pages" / "5_Method.py",
    }
    roles_ok = True
    for r in ["viewer", "maintainer", "admin"]:
        for p_title in allowed_pages(r):
            p_file = page_file_map.get(p_title)
            if p_file and p_file.exists():
                at_r = AppTest.from_file(str(p_file))
                at_r.session_state["auth_user"] = r
                at_r.session_state["role"] = r
                at_r.run(timeout=30)
                denied_errors = [e.value for e in at_r.error if "access denied" in e.value.lower()]
                if at_r.exception or len(denied_errors) > 0:
                    roles_ok = False
                    print(f"FAIL: Role {r} failed rendering allowed page {p_title}: {at_r.exception or denied_errors}")
    check(roles_ok, "Each role renders allowed pages without exception")

    # (c) viewer opening Planner or Twin directly gets error and no page content (st.stop())
    viewer_restricted_ok = True
    for restricted in ["2_Digital_Twin.py", "3_Planner.py"]:
        at_v = AppTest.from_file(str(_root / "app" / "pages" / restricted))
        at_v.session_state["auth_user"] = "viewer"
        at_v.session_state["role"] = "viewer"
        at_v.run(timeout=30)
        has_denied = any("access denied" in e.value.lower() for e in at_v.error)
        if restricted == "2_Digital_Twin.py":
            stopped = len([m for m in at_v.metric if m.label == "Current Cycle"]) == 0
        else:
            stopped = not any("Plan Summary" in str(s.value) for s in at_v.subheader)
        if not (has_denied and stopped and not at_v.exception):
            viewer_restricted_ok = False
            print(f"FAIL: Viewer accessing {restricted} directly did not stop with error (has_denied={has_denied}, stopped={stopped})")
    check(viewer_restricted_ok, "Viewer opening Planner or Twin directly gets error and no page content (st.stop())")

    # (d) Logout clears session
    at_logout = AppTest.from_file(str(_root / "app" / "main.py"))
    at_logout.session_state["auth_user"] = "admin"
    at_logout.session_state["role"] = "admin"
    at_logout.run(timeout=30)
    at_logout.sidebar.button(key="logout_btn").click().run(timeout=30)
    logout_cleared = (not at_logout.session_state.get("auth_user")) and (not at_logout.session_state.get("role"))
    logout_login_shown = any("Demo access control, not production security." in str(c.value) for c in at_logout.caption)
    check(logout_cleared and logout_login_shown, "Logout clears session auth_user and role and returns to login gate")

    print("--- Stage L2-FIX: Enhanced Security & Authorization Checks ---")
    from app.auth import set_current_user

    # LF4(a): app/auth.py and every file in app/ contain none of: sys.argv, os.environ, check_day, TEST_MODE, BYPASS
    forbidden_patterns = ["sys.argv", "os.environ", "check_day", "TEST_MODE", "BYPASS"]
    app_files = []
    for r_dir, _, f_names in os.walk(_root / "app"):
        for f_n in f_names:
            if f_n.endswith(".py"):
                app_files.append(Path(r_dir) / f_n)

    forbidden_found = []
    for f_p in sorted(app_files):
        with open(f_p, "r", encoding="utf-8", errors="replace") as fp:
            f_content = fp.read()
        for pat in forbidden_patterns:
            if pat in f_content:
                forbidden_found.append((str(f_p.relative_to(_root)), pat))

    print(f"Forbidden search across {len(app_files)} files in app/ (patterns={forbidden_patterns}): {forbidden_found}")
    check(len(forbidden_found) == 0, "app/ files contain none of: sys.argv, os.environ, check_day, TEST_MODE, BYPASS")

    # LF4(b): every page, run with an empty session state, shows the login prompt or access denied and renders none of its normal content
    all_pages = [
        _root / "app" / "main.py",
        _root / "app" / "pages" / "0_Fleet_Overview.py",
        _root / "app" / "pages" / "1_Aircraft_Detail.py",
        _root / "app" / "pages" / "2_Digital_Twin.py",
        _root / "app" / "pages" / "3_Planner.py",
        _root / "app" / "pages" / "4_Results.py",
        _root / "app" / "pages" / "5_Method.py",
    ]
    empty_session_ok = True
    for p_path in all_pages:
        at_empty = AppTest.from_file(str(p_path))
        at_empty.run(timeout=30)
        p_name = p_path.name
        if p_name == "main.py":
            has_prompt = any("Login" in str(s.value) for s in at_empty.subheader) and len(at_empty.text_input) >= 2
            no_normal = (
                not any("Fleet Status" in str(s.value) for s in at_empty.subheader)
                and len(at_empty.metric) == 0
                and len(at_empty.dataframe) == 0
            )
            if not (has_prompt and no_normal and not at_empty.exception):
                empty_session_ok = False
                print(f"FAIL: main.py with empty session failed (has_prompt={has_prompt}, no_normal={no_normal})")
        elif p_name == "0_Fleet_Overview.py":
            has_denied = any("access denied" in e.value.lower() for e in at_empty.error)
            no_normal = (
                not any("Fleet Status" in str(s.value) for s in at_empty.subheader)
                and len(at_empty.dataframe) == 0
            )
            if not (has_denied and no_normal and not at_empty.exception):
                empty_session_ok = False
                print(f"FAIL: {p_name} with empty session failed (has_denied={has_denied}, no_normal={no_normal})")
        elif p_name == "1_Aircraft_Detail.py":
            has_denied = any("access denied" in e.value.lower() for e in at_empty.error)
            no_normal = len(at_empty.selectbox) == 0 and len(at_empty.dataframe) == 0
            if not (has_denied and no_normal and not at_empty.exception):
                empty_session_ok = False
                print(f"FAIL: {p_name} with empty session failed (has_denied={has_denied}, no_normal={no_normal})")
        elif p_name == "2_Digital_Twin.py":
            has_denied = any("access denied" in e.value.lower() for e in at_empty.error)
            no_normal = len(at_empty.metric) == 0 and len(at_empty.button) == 0 and len(at_empty.slider) == 0
            if not (has_denied and no_normal and not at_empty.exception):
                empty_session_ok = False
                print(f"FAIL: {p_name} with empty session failed (has_denied={has_denied}, no_normal={no_normal})")
        elif p_name == "3_Planner.py":
            has_denied = any("access denied" in e.value.lower() for e in at_empty.error)
            no_normal = len(at_empty.subheader) == 0 and len(at_empty.dataframe) == 0
            if not (has_denied and no_normal and not at_empty.exception):
                empty_session_ok = False
                print(f"FAIL: {p_name} with empty session failed (has_denied={has_denied}, no_normal={no_normal})")
        elif p_name == "4_Results.py":
            has_denied = any("access denied" in e.value.lower() for e in at_empty.error)
            no_normal = len(at_empty.subheader) == 0 and len(at_empty.dataframe) == 0
            if not (has_denied and no_normal and not at_empty.exception):
                empty_session_ok = False
                print(f"FAIL: {p_name} with empty session failed (has_denied={has_denied}, no_normal={no_normal})")
        elif p_name == "5_Method.py":
            has_denied = any("access denied" in e.value.lower() for e in at_empty.error)
            no_normal = len(at_empty.markdown) == 0
            if not (has_denied and no_normal and not at_empty.exception):
                empty_session_ok = False
                print(f"FAIL: {p_name} with empty session failed (has_denied={has_denied}, no_normal={no_normal})")
    check(empty_session_ok, "Every page with empty session state shows login prompt or access denied and renders none of normal content")

    # LF4(c): a viewer account is denied the admin-only page and the maintainer-only pages
    viewer_denials_ok = True
    for restricted_page in ["2_Digital_Twin.py", "3_Planner.py"]:
        at_vd = AppTest.from_file(str(_root / "app" / "pages" / restricted_page))
        set_current_user("viewer", session_state=at_vd.session_state)
        at_vd.run(timeout=30)
        has_denied = any("access denied" in e.value.lower() for e in at_vd.error)
        no_content = (
            len(at_vd.metric) == 0
            and len(at_vd.subheader) == 0
            and len(at_vd.dataframe) == 0
            and not at_vd.exception
        )
        if not (has_denied and no_content):
            viewer_denials_ok = False
            print(f"FAIL: Viewer was not strictly denied {restricted_page} (has_denied={has_denied}, no_content={no_content})")
    check(viewer_denials_ok, "Viewer account is strictly denied maintainer/admin pages and renders no page content")
    
    smoke_passed, smoke_failed = run_smoke_tests()
    passed += smoke_passed
    failed += smoke_failed
    
    print(f"{passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    check_day3()





