import pandas as pd
import numpy as np
import joblib
import os
import random
from datetime import datetime, timedelta

from config import SEED, FLEET_SIZE, RED_BELOW, AMBER_BELOW, AS_OF, COMPONENTS

"""
Assumptions for Synthetic Data Generation:
- maintenance_logs: 6 to 18 months of history before AS_OF per aircraft. Downtime: scheduled (1-4 days), unscheduled (3-14 days).
- parts_catalog: 6 components (2 engines, 4 generic). Lead time 5 to 45 days.
- spares_inventory: 3 depots. Specifically designed so that a RED engine part has 0 stock and long lead time (to trigger ORDER NOW). AMBER parts are mostly in stock.
- workshops: 4 workshops with varying capacity (2-5 slots) and turnaround (5-15 days).
- flight_schedule: 60 days forward from AS_OF. Aircraft fly randomly (not every day).
"""

def main():
    print("Loading model and metadata...")
    if not os.path.exists('ml/model.joblib'):
        print("Model not found. Run train_baseline.py first.")
        return
        
    model_data = joblib.load('ml/model.joblib')
    model = model_data['model']
    features = model_data['metadata']['features']
    
    columns = ['engine', 'cycle', 'set1', 'set2', 'set3'] + [f's{i}' for i in range(1, 22)]
    test = pd.read_csv('data/raw/test_FD001.txt', sep=r'\s+', header=None, names=columns)
    
    test = test.sort_values(['engine', 'cycle'])
    sensor_cols = [c for c in test.columns if c.startswith('s') or c.startswith('set')]
    df_rolled = test.groupby('engine')[sensor_cols].rolling(10, min_periods=1).mean().reset_index(0, drop=True)
    df_rolled.columns = [f'{c}_roll_mean' for c in sensor_cols]
    df_diff = test.groupby('engine')[sensor_cols].diff(periods=9) / 9.0
    df_diff.columns = [f'{c}_slope' for c in sensor_cols]
    df_diff = df_diff.fillna(0)
    test = pd.concat([test, df_rolled, df_diff], axis=1)
    
    last_cycles = test.groupby('engine').last().reset_index()
    X_test = last_cycles[features]
    preds = model.predict(X_test)
    last_cycles['predicted_rul'] = preds
    
    green_engines = last_cycles[last_cycles['predicted_rul'] > AMBER_BELOW]['engine'].tolist()
    amber_engines = last_cycles[(last_cycles['predicted_rul'] <= AMBER_BELOW) & (last_cycles['predicted_rul'] >= RED_BELOW)]['engine'].tolist()
    red_engines = last_cycles[last_cycles['predicted_rul'] < RED_BELOW]['engine'].tolist()
    
    np.random.seed(SEED)
    random.seed(SEED)
    
    # Aircraft engines assignment
    g_sel = np.random.choice(green_engines, size=32, replace=False).tolist()
    green_engine_pairs = [(g_sel[i], g_sel[i+1]) for i in range(0, 32, 2)]
    
    a_sel = np.random.choice(amber_engines, size=6, replace=False).tolist()
    g2_sel = np.random.choice(list(set(green_engines) - set(g_sel)), size=6, replace=False).tolist()
    amber_engine_pairs = [(a_sel[i], g2_sel[i]) for i in range(6)]
    
    r_sel = np.random.choice(red_engines, size=2, replace=False).tolist()
    g3_sel = np.random.choice(list(set(green_engines) - set(g_sel) - set(g2_sel)), size=2, replace=False).tolist()
    red_engine_pairs = [(r_sel[i], g3_sel[i]) for i in range(2)]
    
    all_pairs = green_engine_pairs + amber_engine_pairs + red_engine_pairs
    np.random.shuffle(all_pairs)
    
    aircraft_data = []
    for i in range(FLEET_SIZE):
        ac_id = f"AF-{1001 + i}"
        eng1, eng2 = all_pairs[i]
        aircraft_data.append({
            'aircraft_id': ac_id,
            'type': random.choice(["Generic Fighter Trainer", "Generic Transport Aircraft"]),
            'base': random.choice(["Base Alpha", "Base Bravo", "Base Charlie"]),
            'flights_per_day': round(random.uniform(0.8, 2.0), 2),
            'total_flight_hours': random.randint(1500, 5000),
            'engine_ids': f"{eng1},{eng2}"
        })
        
    df_master = pd.DataFrame(aircraft_data)
    os.makedirs('data', exist_ok=True)
    df_master.to_csv('data/aircraft_master.csv', index=False)
    
    # 2. parts_catalog
    parts = []
    # Vary by type
    types = ["Generic Fighter Trainer", "Generic Transport Aircraft"]
    for ac_type in types:
        if "Fighter" in ac_type:
            pn_e1 = 'PN-ENG-F101'
            pn_e2 = 'PN-ENG-F102'
        else:
            pn_e1 = 'PN-ENG-T201'
            pn_e2 = 'PN-ENG-T202'
            
        part_numbers = {
            'engine_1': pn_e1,
            'engine_2': pn_e2,
            'hydraulic_pump': f'PN-HYD-{ac_type[:3].upper()} (Simulated)',
            'generator': f'PN-GEN-{ac_type[:3].upper()} (Simulated)',
            'avionics_unit': f'PN-AVI-{ac_type[:3].upper()} (Simulated)',
            'landing_gear_actuator': f'PN-LGA-{ac_type[:3].upper()} (Simulated)'
        }
        
        for comp, pn in part_numbers.items():
            if 'ENG-F1' in pn:
                lead = 45 # Long lead time for Fighter engines
            else:
                lead = random.randint(5, 20)
            parts.append({'type': ac_type, 'component': comp, 'part_no': pn, 'lead_time_days': lead})
            
    pd.DataFrame(parts).to_csv('data/parts_catalog.csv', index=False)
    
    # 3. spares_inventory
    spares = []
    depots = ['Depot North', 'Depot South', 'Depot Central']
    for p in parts:
        pn = p['part_no']
        
        if pn == 'PN-ENG-F101':
            stock = 0
            reorder = 2
        elif pn == 'PN-ENG-F102':
            stock = random.randint(3, 8)
            reorder = 2
        elif pn == 'PN-ENG-T201':
            stock = random.randint(1, 3)
            reorder = 4
        elif pn == 'PN-ENG-T202':
            stock = 0
            reorder = 2
        else:
            stock = random.randint(1, 10)
            reorder = random.randint(2, 5)
            
        spares.append({
            'part_no': pn,
            'depot': random.choice(depots),
            'qty_on_hand': stock,
            'reorder_level': reorder
        })
    pd.DataFrame(spares).to_csv('data/spares_inventory.csv', index=False)

    as_of_dt = datetime.strptime(AS_OF, "%Y-%m-%d %H:%M")
    
    # 4. maintenance_logs
    logs = []
    log_id = 1
    for ac in aircraft_data:
        ac_id = ac['aircraft_id']
        num_logs = random.randint(3, 10)
        for _ in range(num_logs):
            days_ago = random.randint(1, 540) # up to 18 months
            log_date = as_of_dt - timedelta(days=days_ago)
            kind = random.choice(['scheduled', 'unscheduled'])
            downtime = random.randint(1, 4) if kind == 'scheduled' else random.randint(3, 14)
            action = random.choice(['Routine Inspection', 'Component Replacement', 'Calibration', 'Software Update'])
            comp = random.choice(list(part_numbers.keys()))
            logs.append({
                'log_id': f"LOG-{log_id:04d}",
                'aircraft_id': ac_id,
                'component': comp,
                'date': log_date.strftime("%Y-%m-%d"),
                'kind': kind,
                'action': action,
                'downtime_days': downtime
            })
            log_id += 1
    pd.DataFrame(logs).to_csv('data/maintenance_logs.csv', index=False)

    # 5. workshops
    ws_data = [
        {'workshop_id': 'WS-1', 'location': 'Base Alpha', 'capacity_slots': 3, 'turnaround_days': 10, 'specialisation': 'Engines'},
        {'workshop_id': 'WS-2', 'location': 'Base Bravo', 'capacity_slots': 2, 'turnaround_days': 5, 'specialisation': 'Avionics'},
        {'workshop_id': 'WS-3', 'location': 'Base Charlie', 'capacity_slots': 5, 'turnaround_days': 15, 'specialisation': 'General'},
        {'workshop_id': 'WS-4', 'location': 'Depot Central', 'capacity_slots': 4, 'turnaround_days': 7, 'specialisation': 'Hydraulics'}
    ]
    pd.DataFrame(ws_data).to_csv('data/workshops.csv', index=False)
    
    # 6. flight_schedule
    schedule = []
    for day in range(60):
        sched_date = as_of_dt + timedelta(days=day)
        # Choose a random subset of aircraft to fly today (e.g., 60% of fleet)
        flying_ac = random.sample(aircraft_data, int(FLEET_SIZE * 0.6))
        for ac in flying_ac:
            schedule.append({
                'date': sched_date.strftime("%Y-%m-%d"),
                'aircraft_id': ac['aircraft_id'],
                'mission_id': f"MSN-{random.randint(1000,9999)}",
                'priority': random.choice(['low', 'medium', 'high'])
            })
    pd.DataFrame(schedule).to_csv('data/flight_schedule.csv', index=False)
    
    print("Created all synthetic tables in /data.")

if __name__ == '__main__':
    main()
