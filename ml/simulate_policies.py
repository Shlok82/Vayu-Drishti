import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import pandas as pd
import numpy as np
import json
import os
import matplotlib.pyplot as plt
from ml.sim_config import load_sim_config

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

def simulate_run(policy, params, r, df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config):
    days = sim_config['simulation']['days']
    seed = sim_config['simulation']['seed']
    np.random.seed(seed + r) # Seed PER RUN for perfect paired comparison
    
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
    res_binned = metrics['residuals_binned']
    debounced_mean = metrics['alert_lead_time_debounced']['mean']
    debounced_min = metrics['alert_lead_time_debounced']['min']
    debounced_max = metrics['alert_lead_time_debounced']['max']
    
    sched_dict = {}
    for _, row in df_sched.iterrows():
        ac = row['aircraft_id']
        day_offset = (pd.to_datetime(row['date']) - pd.to_datetime('2026-10-01')).days
        if 0 <= day_offset < days:
            if ac not in sched_dict: sched_dict[ac] = {}
            weight = sim_config['simulation']['mission_cost_weights'].get(row['priority'], 1)
            sched_dict[ac][day_offset] = weight
            
    ac_list = df_master['aircraft_id'].tolist()
    
    stock = init_stock.copy()
    ws_usage = {d: 0 for d in range(days)}
    ac_unsched_days = {ac: 0 for ac in ac_list}
    ac_missions_affected = {ac: 0 for ac in ac_list}
    ac_ready_daily = {ac: np.ones(days) for ac in ac_list}
    
    events = []
    for _, row in df_preds.iterrows():
        if not row['component'].startswith('engine'): continue
        ac = row['aircraft_id']
        comp = row['component']
        rul_pred = row['predicted_rul_cycles']
        bin_k = '0-30' if rul_pred <= 30 else '30-80' if rul_pred <= 80 else '>80'
        res = np.random.choice(res_binned[bin_k])
        rul_true = rul_pred + res
        fpd = df_master[df_master['aircraft_id'] == ac]['flights_per_day'].iloc[0]
        fail_day = rul_true / fpd
        if fail_day < days:
            events.append({
                'fail_day': fail_day, 'ac': ac, 'comp': comp, 'rul_pred': rul_pred, 'fpd': fpd
            })
            
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
            diag = params.get('diagnosis_delay_days', 2)
            repair = np.random.randint(params['repair_days'][0], params['repair_days'][1]+1)
            if stock.get(pno, 0) > 0:
                stock[pno] -= 1
                part_wait = 0
            else:
                part_wait = lt * params.get('lead_time_multiplier', 1.0)
            start_repair = int(fail_day) + diag + part_wait
            while ws_usage.get(start_repair, 0) >= ws_cap:
                start_repair += 1
            for d in range(repair):
                ws_usage[start_repair + d] = ws_usage.get(start_repair + d, 0) + 1
            end_day = start_repair + repair
            fd_int = max(0, int(fail_day))
            ed_int = min(days, int(end_day))
            for d in range(fd_int, ed_int):
                ac_ready_daily[ac][d] = 0
                ac_unsched_days[ac] += 1
                if ac in sched_dict and d in sched_dict[ac]:
                    ac_missions_affected[ac] += sched_dict[ac][d]
                    
        elif policy == 'predictive':
            repair = params.get('repair_days', 2)
            alert_multiplier = params.get('alert_lead_time_multiplier', 1.0)
            if debounced_max > 0:
                alert_lead = np.random.uniform(debounced_min, debounced_max) * alert_multiplier
            else:
                alert_lead = 24.0 * alert_multiplier
            alert_day = max(0, (ev['rul_pred'] - alert_lead) / ev['fpd'])
            
            if np.random.rand() < params.get('false_alarm_rate', 0.05):
                fa_day = np.random.uniform(0, days)
                fa_start = int(fa_day)
                while ws_usage.get(fa_start, 0) >= ws_cap:
                    fa_start += 1
                for d in range(repair):
                    ws_usage[fa_start + d] = ws_usage.get(fa_start + d, 0) + 1
                    if fa_start + d < days:
                        ac_ready_daily[ac][fa_start + d] = 0
                        
            if stock.get(pno, 0) > 0:
                stock[pno] -= 1
                part_ready = alert_day
            else:
                part_ready = alert_day + (lt * params.get('lead_time_multiplier', 1.0))
            
            start_repair = max(int(part_ready), int(alert_day))
            if start_repair > fail_day:
                start_repair = int(fail_day) + max(0, int(part_ready - fail_day))
                is_unsched = True
            else:
                while ws_usage.get(start_repair, 0) >= ws_cap and start_repair < fail_day:
                    start_repair += 1
                is_unsched = (start_repair >= fail_day)
                
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
    avail = np.mean(fleet_ready) / len(ac_list)
    unsched = sum(ac_unsched_days.values())
    missions = sum(ac_missions_affected.values())
    return avail, unsched, missions, fleet_ready

def summarize(results):
    avails = [r[0] for r in results]
    unscheds = [r[1] for r in results]
    missions = [r[2] for r in results]
    daily_ready = [r[3] for r in results]
    return {
        'avail_mean': np.mean(avails), 'avail_p025': np.percentile(avails, 2.5), 'avail_p975': np.percentile(avails, 97.5),
        'unsched_mean': np.mean(unscheds), 'unsched_p025': np.percentile(unscheds, 2.5), 'unsched_p975': np.percentile(unscheds, 97.5),
        'missions_mean': np.mean(missions), 'missions_p025': np.percentile(missions, 2.5), 'missions_p975': np.percentile(missions, 97.5),
        'daily_mean': np.mean(daily_ready, axis=0).tolist(),
        'avails_raw': avails, 'unscheds_raw': unscheds, 'missions_raw': missions
    }

def main():
    print("Loading data for simulation...")
    df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config = load_data()
    
    runs = sim_config['simulation']['runs']
    results = {}
    
    # 1. Base paired comparison
    base_r = []
    base_p = []
    for r in range(runs):
        base_r.append(simulate_run('reactive', sim_config['reactive'], r, df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config))
        base_p.append(simulate_run('predictive', sim_config['predictive'], r, df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config))
        
    results['Reactive Base'] = summarize(base_r)
    results['Predictive Base'] = summarize(base_p)
    
    # Paired differences: P - R for avail, R - P for unsched/missions (so positive is good)
    diff_avail = [p[0] - r[0] for p, r in zip(base_p, base_r)]
    results['Paired Difference'] = {
        'avail_diff_mean': np.mean(diff_avail),
        'avail_diff_p025': np.percentile(diff_avail, 2.5),
        'avail_diff_p975': np.percentile(diff_avail, 97.5),
        'predictive_wins_frac': sum(1 for d in diff_avail if d > 0) / runs,
        'unsched_diff_mean': np.mean([r[1] - p[1] for p, r in zip(base_p, base_r)]),
        'missions_diff_mean': np.mean([r[2] - p[2] for p, r in zip(base_p, base_r)])
    }
    
    # Clean raw output
    for k in ['Reactive Base', 'Predictive Base']:
        del results[k]['avails_raw']; del results[k]['unscheds_raw']; del results[k]['missions_raw']
    
    # 2. Full sensitivity table
    sensitivity_table = []
    
    def eval_sens(param, val, r_params, p_params):
        r_res = [simulate_run('reactive', r_params, r, df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config) for r in range(runs)]
        p_res = [simulate_run('predictive', p_params, r, df_preds, df_master, df_parts, df_spares, df_ws, df_sched, metrics, sim_config) for r in range(runs)]
        r_sum = summarize(r_res)
        p_sum = summarize(p_res)
        diff_av = [p[0] - r[0] for p, r in zip(p_res, r_res)]
        wins = sum(1 for d in diff_av if d > 0) / runs
        sensitivity_table.append({
            'Parameter': param,
            'Setting': str(val),
            'Reactive Avail': r_sum['avail_mean'],
            'Predictive Avail': p_sum['avail_mean'],
            'Pred Wins Frac': wins,
            'Pred Wins?': wins > 0.5
        })
        
    # Baseline
    eval_sens('Baseline', 'base', sim_config['reactive'], sim_config['predictive'])
    
    # Diagnosis delay
    for val in [1, 4]:
        rp = sim_config['reactive'].copy(); rp['diagnosis_delay_days'] = val
        eval_sens('Diagnosis Delay', val, rp, sim_config['predictive'])
        
    # Repair days
    for val, rp_val, pp_val in [('Fast', [1,3], 1), ('Slow', [5,14], 7)]:
        rp = sim_config['reactive'].copy(); rp['repair_days'] = rp_val
        pp = sim_config['predictive'].copy(); pp['repair_days'] = pp_val
        eval_sens('Repair Days', val, rp, pp)
        
    # Lead time multiplier
    for val in [0.5, 1.5]:
        rp = sim_config['reactive'].copy(); rp['lead_time_multiplier'] = val
        pp = sim_config['predictive'].copy(); pp['lead_time_multiplier'] = val
        eval_sens('Lead Time Multiplier', val, rp, pp)
        
    # False alarm rate
    for val in [0.01, 0.15]:
        pp = sim_config['predictive'].copy(); pp['false_alarm_rate'] = val
        eval_sens('False Alarm Rate', val, sim_config['reactive'], pp)
        
    # Alert lead time
    for val in [0.5, 1.5]:
        pp = sim_config['predictive'].copy(); pp['alert_lead_time_multiplier'] = val
        eval_sens('Alert Lead Multiplier', val, sim_config['reactive'], pp)
        
    results['Sensitivity'] = sensitivity_table
    
    os.makedirs('docs', exist_ok=True)
    with open('docs/sim_results.json', 'w') as f:
        json.dump(results, f, indent=4)
        
    print("Simulation complete. Results saved to docs/sim_results.json")

if __name__ == '__main__':
    main()

