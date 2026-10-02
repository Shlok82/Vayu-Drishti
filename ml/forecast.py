import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ml import config
from ml.sim_config import load_sim_config

def simulate_forecast(df_master, df_preds, recs_df, days=30):
    as_of_dt = datetime.strptime(config.AS_OF, "%Y-%m-%d %H:%M").date()
    
    # Precompute per-aircraft FPD and initial states
    ac_fpd = {row['aircraft_id']: row['flights_per_day'] for _, row in df_master.iterrows()}
    
    initial_ruls = {}
    for _, row in df_preds.iterrows():
        ac_id = row['aircraft_id']
        if ac_id not in initial_ruls:
            initial_ruls[ac_id] = {}
        initial_ruls[ac_id][row['component']] = row['predicted_rul_cycles']
        
    planned_slots = {}
    if not recs_df.empty:
        for _, row in recs_df.iterrows():
            if row['flag'] == "":
                ac = row['aircraft_id']
                if ac not in planned_slots:
                    planned_slots[ac] = []
                st = datetime.strptime(row['slot_start'], "%Y-%m-%d").date()
                en = datetime.strptime(row['slot_end'], "%Y-%m-%d").date()
                planned_slots[ac].append({'start': st, 'end': en, 'comp': row['component']})
                
    dates = [as_of_dt + timedelta(days=d) for d in range(days)]
    
    # Load required data
    df_parts = pd.read_csv(config.DATA_DIR / 'parts_catalog.csv')
    df_spares = pd.read_csv(config.DATA_DIR / 'spares_inventory.csv')
    df_ws = pd.read_csv(config.DATA_DIR / 'workshops.csv')
    
    sim_cfg = load_sim_config()
    react_cfg = sim_cfg['reactive']
    
    ws_cap = df_ws['capacity_slots'].sum()
    
    part_lt = {}
    for _, r in df_parts.iterrows():
        part_lt[(r['aircraft_id'], r['component'])] = r['lead_time_days']
        
    part_stock = {}
    for _, r in df_parts.iterrows():
        pno = r['part_no']
        stock = df_spares[df_spares['part_no'] == pno]['qty_on_hand'].sum()
        part_stock[(r['aircraft_id'], r['component'])] = stock
        
    ws_ta = df_ws['turnaround_days'].mean()
    
    # Global diagnostic data to expose for printing
    _daily_red_plan = []
    _daily_failed_plan = []
    _sample_ac_day5 = {}
    
    def run_scenario(plan_mode):
        ruls = {ac: dict(comps) for ac, comps in initial_ruls.items()}
        failed = {ac: False for ac in ac_fpd}
        
        repair_queue = [] 
        ws_usage = {}
        stock = part_stock.copy()
        
        counts = []
        
        for d in range(days):
            current_date = dates[d]
            ready_today = 0
            
            day_reds = 0
            day_failed = 0
            
            for ac, fpd in ac_fpd.items():
                is_ready = True
                is_red = False
                
                active_repair = None
                for rep in repair_queue:
                    if rep[0] == ac:
                        if rep[1] <= current_date < rep[2]:
                            active_repair = rep
                        elif current_date == rep[2]:
                            failed[ac] = False
                            for comp in ruls[ac]:
                                ruls[ac][comp] = 125.0
                
                if active_repair:
                    is_ready = False
                else:
                    is_in_planned_ws = False
                    if plan_mode and current_date >= as_of_dt:
                        for slot in planned_slots.get(ac, []):
                            if slot['start'] <= current_date < slot['end']:
                                is_in_planned_ws = True
                                break
                            elif current_date == slot['end']:
                                ruls[ac][slot['comp']] = 125.0
                    
                    if is_in_planned_ws:
                        is_ready = False
                    else:
                        for comp in ruls[ac]:
                            ruls[ac][comp] -= fpd
                            
                for comp, rul in ruls[ac].items():
                    if rul <= config.RED_BELOW:
                        is_ready = False
                        is_red = True
                    if rul <= 0 and not failed[ac]:
                        failed[ac] = True
                        diag = react_cfg.get('diagnosis_delay_days', 2)
                        st_avail = stock.get((ac, comp), 0)
                        if st_avail > 0:
                            stock[(ac, comp)] -= 1
                            part_wait = 0
                        else:
                            part_wait = part_lt.get((ac, comp), 20)
                            
                        start_repair = current_date + timedelta(days=diag + int(part_wait))
                        
                        while ws_usage.get(start_repair, 0) >= ws_cap:
                            start_repair += timedelta(days=1)
                            
                        repair_days = int(ws_ta)
                        for dr in range(repair_days):
                            ws_usage[start_repair + timedelta(days=dr)] = ws_usage.get(start_repair + timedelta(days=dr), 0) + 1
                            
                        end_repair = start_repair + timedelta(days=repair_days)
                        repair_queue.append((ac, start_repair, end_repair))
                        
                if failed[ac]:
                    is_ready = False
                    day_failed += 1
                    
                if is_red:
                    day_reds += 1
                    
                if is_ready:
                    ready_today += 1
                    
                # Capture day 5 state
                if plan_mode and d == 5 and len(_sample_ac_day5) < 5:
                    _sample_ac_day5[ac] = {
                        'Ready?': is_ready,
                        'Workshop?': bool(active_repair or (plan_mode and is_in_planned_ws)),
                        'Reds?': is_red
                    }
                    
            counts.append(ready_today)
            if plan_mode:
                _daily_red_plan.append(day_reds)
                _daily_failed_plan.append(day_failed)
                
        return counts

    no_action_ready = run_scenario(False)
    planned_ready = run_scenario(True)
    
    print("--- Forecast Output ---")
    print(f"No Action (Ready): {no_action_ready}")
    print(f"Plan (Ready): {planned_ready}")
    print(f"Plan (Red aircraft): {_daily_red_plan}")
    print(f"Plan (Failed aircraft): {_daily_failed_plan}")
    print(f"Plan (Sample Day 5): {_sample_ac_day5}")
    
    return pd.DataFrame({
        'Date': dates,
        'No Action': no_action_ready,
        'Plan': planned_ready
    })
