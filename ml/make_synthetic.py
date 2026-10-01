import pandas as pd
import numpy as np
import joblib
import os
import random

from config import SEED, FLEET_SIZE, RED_BELOW, AMBER_BELOW

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
    
    # 16 green aircraft (32 green engines)
    g_sel = np.random.choice(green_engines, size=32, replace=False).tolist()
    green_engine_pairs = [(g_sel[i], g_sel[i+1]) for i in range(0, 32, 2)]
    
    # 6 amber aircraft (6 amber, 6 green)
    a_sel = np.random.choice(amber_engines, size=6, replace=False).tolist()
    g2_sel = np.random.choice(list(set(green_engines) - set(g_sel)), size=6, replace=False).tolist()
    amber_engine_pairs = [(a_sel[i], g2_sel[i]) for i in range(6)]
    
    # 2 red aircraft (2 red, 2 green)
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
    print(f"Created data/aircraft_master.csv with {FLEET_SIZE} aircraft.")

if __name__ == '__main__':
    main()
