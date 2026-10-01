import pandas as pd
import numpy as np
import joblib
import json
import os
import matplotlib.pyplot as plt
import re
from config import RED_BELOW, RUL_CLIP

def main():
    print("Loading data and model...")
    train = pd.read_csv('data/raw/train_FD001.txt', sep=r'\s+', header=None, 
                        names=['engine', 'cycle', 'set1', 'set2', 'set3'] + [f's{i}' for i in range(1, 22)])
    
    with open('docs/metrics.json', 'r') as f:
        metrics = json.load(f)
        
    val_engines = metrics['val_engines']
    features = metrics['features']
    model_data = joblib.load('ml/model.joblib')
    model = model_data['model']
    
    # Compute true RUL for val engines
    val_data = train[train['engine'].isin(val_engines)].copy()
    max_cycles = val_data.groupby('engine')['cycle'].max()
    val_data['true_rul'] = val_data['engine'].map(max_cycles) - val_data['cycle']
    
    engine_results = {}
    
    print("Evaluating cycle-by-cycle predictions on held-out engines...")
    for eng in val_engines:
        eng_data = val_data[val_data['engine'] == eng].sort_values('cycle').copy()
        preds = []
        
        # Causal rolling features
        sensor_cols = [c for c in eng_data.columns if c.startswith('s') or c.startswith('set')]
        eng_data_sensors = eng_data[sensor_cols]
        df_rolled = eng_data_sensors.rolling(10, min_periods=1).mean()
        df_rolled.columns = [f'{c}_roll_mean' for c in sensor_cols]
        df_diff = eng_data_sensors.diff(periods=9) / 9.0
        df_diff.columns = [f'{c}_slope' for c in sensor_cols]
        df_diff = df_diff.fillna(0)
        
        eng_eval = pd.concat([eng_data.reset_index(drop=True), df_rolled.reset_index(drop=True), df_diff.reset_index(drop=True)], axis=1)
        
        X = eng_eval[features]
        eng_preds = model.predict(X)
        eng_eval['predicted_rul'] = eng_preds
        engine_results[eng] = eng_eval
        
    # Metrics
    all_true = []
    all_pred = []
    final_true = []
    final_pred = []
    
    first_crossing_leads = []
    debounced_leads = []
    misses_first = 0
    misses_debounced = 0
    early_alerts = 0
    
    valid_demo_engines = []
    
    for eng, df in engine_results.items():
        all_true.extend(df['true_rul'].tolist())
        all_pred.extend(df['predicted_rul'].tolist())
        
        final_true.append(df['true_rul'].iloc[-1])
        final_pred.append(df['predicted_rul'].iloc[-1])
        
        max_c = df['cycle'].max()
        # alerts
        red_mask = df['predicted_rul'] < RED_BELOW
        
        # First crossing
        if red_mask.any():
            first_idx = red_mask.idxmax()
            lead_time = max_c - df.loc[first_idx, 'cycle']
            first_crossing_leads.append(lead_time)
            if lead_time > 100:
                early_alerts += 1
        else:
            misses_first += 1
            
        # Debounced (3 consecutive)
        # Using a rolling sum of boolean mask to find 3 consecutive True
        debounced_mask = red_mask.rolling(window=3).sum() == 3
        debounced_lead = None
        if debounced_mask.any():
            deb_idx = debounced_mask.idxmax()
            debounced_lead = max_c - df.loc[deb_idx, 'cycle']
            debounced_leads.append(debounced_lead)
        else:
            misses_debounced += 1
            
        # Check if good demo engine
        if 180 <= max_c <= 250 and debounced_lead is not None and debounced_lead >= 20:
            valid_demo_engines.append(eng)

    all_true_clipped = np.clip(all_true, a_min=None, a_max=RUL_CLIP)
            
    rmse_overall = np.sqrt(np.mean((np.array(all_true_clipped) - np.array(all_pred))**2))
    rmse_final = np.sqrt(np.mean((np.array(final_true) - np.array(final_pred))**2))
    
    def get_stats(arr):
        if not arr: return {'mean': None, 'median': None, 'min': None, 'max': None}
        return {
            'mean': float(np.mean(arr)),
            'median': float(np.median(arr)),
            'min': float(np.min(arr)),
            'max': float(np.max(arr))
        }
        
    fc_stats = get_stats(first_crossing_leads)
    deb_stats = get_stats(debounced_leads)
    
    print(f"Overall Per-Cycle RMSE: {rmse_overall:.2f}")
    print(f"Final-Cycle RMSE: {rmse_final:.2f}")
    print(f"Alert Lead Time (First Crossing): {fc_stats}")
    print(f"Alert Lead Time (Debounced): {deb_stats}")
    print(f"Misses (First): {misses_first}, Misses (Debounced): {misses_debounced}")
    print(f"Early Alerts (>100 cycles before failure): {early_alerts}")
    
    metrics.update({
        'rmse_overall_per_cycle': rmse_overall,
        'rmse_at_failure_cycle_heldout': rmse_final,
        'rmse_at_failure_cycle_heldout_note': 'Not comparable to the standard test RMSE since it is evaluated only on held-out training engines.',
        'alert_lead_time_first_crossing': fc_stats,
        'alert_lead_time_debounced': deb_stats,
        'misses_first': misses_first,
        'misses_debounced': misses_debounced,
        'early_alerts': early_alerts
    })
    
    # Calculate empirical residuals binned by predicted RUL
    # We bin predicted RUL into: 0-30, 30-80, >80
    residuals = {'0-30': [], '30-80': [], '>80': []}
    for p, t in zip(all_pred, all_true):
        res = t - p
        if p <= 30:
            residuals['0-30'].append(res)
        elif p <= 80:
            residuals['30-80'].append(res)
        else:
            residuals['>80'].append(res)
            
    # Sample 100 residuals per bin for simulation to avoid huge JSON
    np.random.seed(42)
    binned_res = {}
    for k, v in residuals.items():
        if len(v) > 100:
            binned_res[k] = list(np.random.choice(v, size=100, replace=False))
        else:
            binned_res[k] = list(v)
            
    metrics['residuals_binned'] = binned_res

    
    # Save metrics
    with open('docs/metrics.json', 'w') as f:
        json.dump(metrics, f, indent=4)
        
    # Plotting
    os.makedirs('docs/figures', exist_ok=True)
    plt.figure(figsize=(12, 8))
    for eng, df in list(engine_results.items())[:5]: # Plot 5 engines for clarity
        plt.plot(df['cycle'], df['true_rul'], linestyle='--', label=f'True Eng {eng}')
        plt.plot(df['cycle'], df['predicted_rul'], label=f'Pred Eng {eng}')
    
    plt.axhline(y=RED_BELOW, color='r', linestyle=':', label='Red Alert Threshold')
    plt.xlabel('Cycle')
    plt.ylabel('RUL')
    plt.title('Predicted vs True RUL for Held-Out Engines')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig('docs/figures/pred_vs_true.png')
    plt.close()
    
    print("Saved docs/metrics.json and docs/figures/pred_vs_true.png")
    
    if valid_demo_engines:
        demo_id = valid_demo_engines[0]
    else:
        demo_id = val_engines[0]
        
    print(f"Selected DEMO_ENGINE_ID: {demo_id}")
    
    # Update config.py
    with open('ml/config.py', 'r') as f:
        config_content = f.read()
        
    config_content = re.sub(r'DEMO_ENGINE_ID\s*=\s*.*', f'DEMO_ENGINE_ID = {demo_id}', config_content)
    
    with open('ml/config.py', 'w') as f:
        f.write(config_content)
    print("Updated DEMO_ENGINE_ID in ml/config.py")

if __name__ == '__main__':
    main()
