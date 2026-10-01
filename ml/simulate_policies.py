import pandas as pd
import numpy as np
import json
import os
import matplotlib.pyplot as plt
from sim_config import load_sim_config

def load_data():
    df_preds = pd.read_csv('data/predictions.csv')
    df_master = pd.read_csv('data/aircraft_master.csv')
    df_parts = pd.read_csv('data/parts_catalog.csv')
    df_spares = pd.read_csv('data/spares_inventory.csv')
    df_ws = pd.read_csv('data/workshops.csv')
    df_sched = pd.read_csv('data/flight_schedule.csv')
    with open('docs/metrics.json', 'r') as f:
        metrics = json.load(f)
    sim_config = load_sim_config()
    return df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config

def simulate(policy, params, df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config):
    # Returns (availability, unscheduled_downtime, missions_affected, readiness_over_time)
    days = sim_config['simulation']['days']
    runs = sim_config['simulation']['runs']
    seed = sim_config['simulation']['seed']
    np.random.seed(seed)
    
    # We will simulate at the engine level. 
    # For each run:
    # 1. Sample true failure time per engine = pred_rul + residual
    # 2. Track events
    # 3. Compute metrics
    
    # Pre-extract data
    eng_parts = {}
    for _, ac in df_master.iterrows():
        ac_type = ac['type']
        for comp in ['engine_1', 'engine_2']:
            pt = df_parts[(df_parts['component'] == comp) & (df_parts['type'] == ac_type)]
            if not pt.empty:
                eng_parts[(ac['aircraft_id'], comp)] = {
                    'part_no': pt.iloc[0]['part_no'],
                    'lead_time': pt.iloc[0]['lead_time_days']
                }
                
    init_stock = df_spares.groupby('part_no')['qty_on_hand'].sum().to_dict()
    
    ws_cap = sim_config['simulation']['workshop_capacity']
    
    # Residuals
    res_binned = metrics['residuals_binned']
    
    # Alert behavior (debounced)
    debounced_mean = metrics['alert_lead_time_debounced']['mean']
    debounced_min = metrics['alert_lead_time_debounced']['min']
    debounced_max = metrics['alert_lead_time_debounced']['max']
    
    # Output metrics over runs
    run_avail = []
    run_unsched = []
    run_missions = []
    daily_ready_all_runs = np.zeros((runs, days))
    
    # Flight Schedule (missions per ac per day)
    sched_dict = {}
    for _, row in df_sched.iterrows():
        ac = row['aircraft_id']
        day_offset = (pd.to_datetime(row['date']) - pd.to_datetime('2026-10-01')).days
        if 0 <= day_offset < days:
            if ac not in sched_dict: sched_dict[ac] = {}
            weight = sim_config['simulation']['mission_cost_weights'].get(row['priority'], 1)
            sched_dict[ac][day_offset] = weight
            
    ac_list = df_master['aircraft_id'].tolist()
    
    for r in range(runs):
        stock = init_stock.copy()
        ws_usage = {d: 0 for d in range(days)}
        
        ac_downtime_days = {ac: 0 for ac in ac_list}
        ac_unsched_days = {ac: 0 for ac in ac_list}
        ac_missions_affected = {ac: 0 for ac in ac_list}
        ac_ready_daily = {ac: np.ones(days) for ac in ac_list}
        
        # We process each engine. If it fails within 'days', we simulate it.
        # To handle multiple failures on the same aircraft, we just overlay downtime.
        
        events = [] # list of (fail_day, ac, comp)
        
        for _, row in df_preds.iterrows():
            if not row['component'].startswith('engine'): continue
            
            ac = row['aircraft_id']
            comp = row['component']
            rul_pred = row['predicted_rul_cycles']
            
            # Sample residual
            bin_k = '0-30' if rul_pred <= 30 else '30-80' if rul_pred <= 80 else '>80'
            res = np.random.choice(res_binned[bin_k])
            rul_true = rul_pred + res
            
            fpd = df_master[df_master['aircraft_id'] == ac]['flights_per_day'].iloc[0]
            fail_day = rul_true / fpd
            
            if fail_day < days:
                events.append({
                    'fail_day': fail_day,
                    'ac': ac,
                    'comp': comp,
                    'rul_pred': rul_pred,
                    'fpd': fpd
                })
                
        # Sort events by fail_day
        events.sort(key=lambda x: x['fail_day'])
        
        for ev in events:
            ac = ev['ac']
            comp = ev['comp']
            fail_day = ev['fail_day']
            
            part = eng_parts.get((ac, comp))
            if not part: continue
            pno = part['part_no']
            lt = part['lead_time']
            
            if policy == 'reactive':
                # Reactive logic
                diag = params.get('diagnosis_delay_days', 2)
                repair = np.random.randint(params['repair_days'][0], params['repair_days'][1]+1)
                
                # Check stock at fail_day
                if stock.get(pno, 0) > 0:
                    stock[pno] -= 1
                    part_wait = 0
                else:
                    part_wait = lt
                    
                start_repair = int(fail_day) + diag + part_wait
                
                # Find workshop slot
                while ws_usage.get(start_repair, 0) >= ws_cap:
                    start_repair += 1
                    
                for d in range(repair):
                    ws_usage[start_repair + d] = ws_usage.get(start_repair + d, 0) + 1
                    
                end_day = start_repair + repair
                
                # Record downtime
                fd_int = max(0, int(fail_day))
                ed_int = min(days, int(end_day))
                for d in range(fd_int, ed_int):
                    ac_ready_daily[ac][d] = 0
                    ac_unsched_days[ac] += 1
                    if ac in sched_dict and d in sched_dict[ac]:
                        ac_missions_affected[ac] += sched_dict[ac][d]
                        
            elif policy == 'predictive':
                # Predictive logic
                repair = params.get('repair_days', 2)
                alert_multiplier = params.get('alert_lead_time_multiplier', 1.0)
                
                # Alert time
                if debounced_max > 0:
                    alert_lead = np.random.uniform(debounced_min, debounced_max) * alert_multiplier
                else:
                    alert_lead = 24.0 * alert_multiplier # fallback
                    
                alert_day = (ev['rul_pred'] - alert_lead) / ev['fpd']
                if alert_day < 0: alert_day = 0
                
                # If miss (prob 0.0, but we can simulate if configured)
                # false alarm
                if np.random.rand() < params.get('false_alarm_rate', 0.05):
                    # trigger an extra repair, but doesn't consume stock for simplicity, just downtime
                    fa_day = np.random.uniform(0, days)
                    fa_start = int(fa_day)
                    while ws_usage.get(fa_start, 0) >= ws_cap:
                        fa_start += 1
                    for d in range(repair):
                        ws_usage[fa_start + d] = ws_usage.get(fa_start + d, 0) + 1
                        if fa_start + d < days:
                            ac_ready_daily[ac][fa_start + d] = 0
                            
                # Normal predictive
                if stock.get(pno, 0) > 0:
                    stock[pno] -= 1
                    part_ready = alert_day
                else:
                    part_ready = alert_day + (lt * params.get('lead_time_multiplier', 1.0))
                    
                # Plan slot before failure if possible
                start_repair = max(int(part_ready), int(alert_day))
                
                # If part arrives after failure, we suffer unscheduled downtime
                if start_repair > fail_day:
                    start_repair = int(fail_day) + max(0, int(part_ready - fail_day))
                    is_unsched = True
                else:
                    # try to schedule before failure
                    while ws_usage.get(start_repair, 0) >= ws_cap and start_repair < fail_day:
                        start_repair += 1
                    if start_repair >= fail_day:
                        is_unsched = True
                    else:
                        is_unsched = False
                        
                for d in range(repair):
                    ws_usage[start_repair + d] = ws_usage.get(start_repair + d, 0) + 1
                    
                end_day = start_repair + repair
                
                fd_int = max(0, start_repair if not is_unsched else int(fail_day))
                ed_int = min(days, int(end_day))
                for d in range(fd_int, ed_int):
                    ac_ready_daily[ac][d] = 0
                    if is_unsched or start_repair >= fail_day:
                        ac_unsched_days[ac] += 1
                    
                    if ac in sched_dict and d in sched_dict[ac]:
                        ac_missions_affected[ac] += sched_dict[ac][d]
                        
        fleet_ready = np.sum([ac_ready_daily[ac] for ac in ac_list], axis=0)
        daily_ready_all_runs[r] = fleet_ready
        
        run_avail.append(np.mean(fleet_ready) / len(ac_list))
        run_unsched.append(sum(ac_unsched_days.values()))
        run_missions.append(sum(ac_missions_affected.values()))
        
    res = {
        'avail_mean': np.mean(run_avail),
        'avail_p025': np.percentile(run_avail, 2.5),
        'avail_p975': np.percentile(run_avail, 97.5),
        'unsched_mean': np.mean(run_unsched),
        'unsched_p025': np.percentile(run_unsched, 2.5),
        'unsched_p975': np.percentile(run_unsched, 97.5),
        'missions_mean': np.mean(run_missions),
        'missions_p025': np.percentile(run_missions, 2.5),
        'missions_p975': np.percentile(run_missions, 97.5),
        'daily_mean': np.mean(daily_ready_all_runs, axis=0).tolist(),
        'daily_p025': np.percentile(daily_ready_all_runs, 2.5, axis=0).tolist(),
        'daily_p975': np.percentile(daily_ready_all_runs, 97.5, axis=0).tolist()
    }
    return res

def main():
    print("Loading data for simulation...")
    df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config = load_data()
    
    results = {}
    print("Simulating Reactive (Base)...")
    results['Reactive Base'] = simulate('reactive', sim_config['reactive'], df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config)
    
    print("Simulating Predictive (Base)...")
    results['Predictive Base'] = simulate('predictive', sim_config['predictive'], df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config)
    
    # Sensitivities
    print("Simulating Predictive (Weaker Model)...")
    wm_params = sim_config['predictive'].copy()
    wm_params['alert_lead_time_multiplier'] = sim_config['weaker_model']['alert_lead_time_multiplier']
    results['Predictive Weaker'] = simulate('predictive', wm_params, df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config)
    
    print("Simulating Predictive (High False Alarm)...")
    hfa_params = sim_config['predictive'].copy()
    hfa_params['false_alarm_rate'] = 0.20
    results['Predictive High False Alarm'] = simulate('predictive', hfa_params, df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config)
    
    print("Simulating Reactive (Fast Repair)...")
    fr_params = sim_config['reactive'].copy()
    fr_params['repair_days'] = [1, 3]
    fr_params['diagnosis_delay_days'] = 1
    results['Reactive Fast Repair'] = simulate('reactive', fr_params, df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config)
    
    os.makedirs('docs', exist_ok=True)
    with open('docs/sim_results.json', 'w') as f:
        json.dump(results, f, indent=4)
        
    print("Simulation complete. Results saved to docs/sim_results.json")

if __name__ == '__main__':
    main()
