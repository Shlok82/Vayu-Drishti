import json
import sys
import os
import copy
import numpy as np
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from ml.simulate_policies import load_data, simulate_run

def eval_wiring(name, r_params, p_params, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config):
    r_avail = []
    p_avail = []
    for s in range(20):
        rr = simulate_run('reactive', r_params, s, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
        pr = simulate_run('predictive', p_params, s, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
        r_avail.append(rr[0])
        p_avail.append(pr[0])
    return {'avail_mean': np.mean(r_avail)}, {'avail_mean': np.mean(p_avail)}

def main():
    print("Loading data for wiring tests...")
    df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config = load_data()
    
    print("Running 20 iterations baseline...")
    base_r, base_p = eval_wiring('Baseline', sim_config['reactive'], sim_config['predictive'], df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
    base_r_mean = base_r['avail_mean']
    base_p_mean = base_p['avail_mean']
    
    print("\n--- Extreme Wiring Tests (20 runs each) ---")
    rp = copy.deepcopy(sim_config['reactive']); rp['repair_days'] = [15, 25]
    pp = copy.deepcopy(sim_config['predictive']); pp['repair_days'] = 20
    rs, ps = eval_wiring('repair x5', rp, pp, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
    print(f"Repair x5 -> R-avail {rs['avail_mean']:.3f} (delta {rs['avail_mean']-base_r_mean:.3f}), P-avail {ps['avail_mean']:.3f} (delta {ps['avail_mean']-base_p_mean:.3f})")
    
    rp = copy.deepcopy(sim_config['reactive']); rp['diagnosis_delay_days'] = 30
    rs, _ = eval_wiring('diag 30d', rp, sim_config['predictive'], df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
    print(f"Diag 30d -> R-avail {rs['avail_mean']:.3f} (delta {rs['avail_mean']-base_r_mean:.3f})")
    
    rp = copy.deepcopy(sim_config['reactive']); rp['lead_time_multiplier'] = 3.0
    pp = copy.deepcopy(sim_config['predictive']); pp['lead_time_multiplier'] = 3.0
    rs, ps = eval_wiring('lead x3', rp, pp, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
    print(f"Lead x3 -> R-avail {rs['avail_mean']:.3f} (delta {rs['avail_mean']-base_r_mean:.3f}), P-avail {ps['avail_mean']:.3f} (delta {ps['avail_mean']-base_p_mean:.3f})")
    
    pp = copy.deepcopy(sim_config['predictive']); pp['false_alarm_rate'] = 0.50
    _, ps = eval_wiring('false alarm 50%', sim_config['reactive'], pp, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
    print(f"FA 50% -> P-avail {ps['avail_mean']:.3f} (delta {ps['avail_mean']-base_p_mean:.3f})")
    
    pp = copy.deepcopy(sim_config['predictive']); pp['alert_lead_time_multiplier'] = 0.0
    _, ps = eval_wiring('alert lead 0', sim_config['reactive'], pp, df_preds_sim, df_master_sim, df_parts_sim, df_spares_sim, df_ws_sim, df_sched_sim, metrics, sim_config)
    print(f"Alert 0 -> P-avail {ps['avail_mean']:.3f} (delta {ps['avail_mean']-base_p_mean:.3f})")

if __name__ == '__main__':
    main()
