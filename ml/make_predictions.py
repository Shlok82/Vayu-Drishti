import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import pandas as pd
import numpy as np
import joblib
import os
from datetime import datetime, timedelta

from ml.config import RUL_CLIP, RED_BELOW, AMBER_BELOW, AS_OF

def main():
    if not os.path.exists('ml/model.joblib') or not os.path.exists('data/aircraft_master.csv'):
        print("Run train_baseline.py and make_synthetic.py first.")
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
    rul_map = dict(zip(last_cycles['engine'], last_cycles['predicted_rul']))
    
    df_master = pd.read_csv('data/aircraft_master.csv')
    
    predictions = []
    generated_at = AS_OF
    current_date = datetime.strptime(AS_OF, "%Y-%m-%d %H:%M")
    
    for _, row in df_master.iterrows():
        ac_id = row['aircraft_id']
        engs = [int(e) for e in row['engine_ids'].split(',')]
        flights_per_day = row['flights_per_day']
        
        for i, eng in enumerate(engs):
            rul = rul_map.get(eng, 100)
            rul_clipped = max(0.0, min(float(rul), float(RUL_CLIP)))
            
            if rul_clipped < RED_BELOW:
                risk = 'red'
            elif rul_clipped <= AMBER_BELOW:
                risk = 'amber'
            else:
                risk = 'green'
                
            fail_date = current_date + timedelta(days=rul_clipped / flights_per_day)
            health = min(100.0, max(0.0, (rul_clipped / RUL_CLIP) * 100.0))
            
            predictions.append({
                'aircraft_id': ac_id,
                'component': f'engine_{i+1}',
                'predicted_rul_cycles': round(rul_clipped, 1),
                'predicted_failure_date': fail_date.strftime("%Y-%m-%d"),
                'risk_level': risk,
                'health_score': round(health, 1),
                'generated_at': generated_at,
                'top_reasons': ''
            })
            
    df_preds = pd.DataFrame(predictions)
    df_preds.to_csv('data/predictions.csv', index=False)
    print("Created data/predictions.csv")

if __name__ == '__main__':
    main()

