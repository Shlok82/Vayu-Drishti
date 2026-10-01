import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
import xgboost as xgb
from sklearn.metrics import mean_squared_error
import joblib
import json
import os
import sys

from ml.config import RUL_CLIP, SEED, N_VAL_ENGINES

# Column names based on CMAPSS documentation
columns = ['engine', 'cycle', 'set1', 'set2', 'set3'] + [f's{i}' for i in range(1, 22)]

def load_data(file_path):
    df = pd.read_csv(file_path, sep=r'\s+', header=None, names=columns)
    return df

def add_features(df):
    df = df.sort_values(['engine', 'cycle'])
    sensor_cols = [c for c in df.columns if c.startswith('s') or c.startswith('set')]
    df_rolled = df.groupby('engine')[sensor_cols].rolling(10, min_periods=1).mean().reset_index(0, drop=True)
    df_rolled.columns = [f'{c}_roll_mean' for c in sensor_cols]
    df_diff = df.groupby('engine')[sensor_cols].diff(periods=9) / 9.0
    df_diff.columns = [f'{c}_slope' for c in sensor_cols]
    df_diff = df_diff.fillna(0)
    return pd.concat([df, df_rolled, df_diff], axis=1)

def main():
    print("Loading data...")
    train = load_data('data/raw/train_FD001.txt')
    test = load_data('data/raw/test_FD001.txt')
    rul_true = pd.read_csv('data/raw/RUL_FD001.txt', header=None, names=['RUL'])
    
    max_cycles = train.groupby('engine')['cycle'].max()
    train['RUL'] = train['engine'].map(max_cycles) - train['cycle']
    train['RUL'] = train['RUL'].clip(upper=RUL_CLIP)
    
    print("Dropping constant columns based on train data...")
    std_dev = train.std()
    constant_cols = std_dev[std_dev < 1e-5].index.tolist()
    constant_cols = [c for c in constant_cols if c not in ['engine', 'cycle', 'RUL']]
    
    train = train.drop(columns=constant_cols)
    test = test.drop(columns=constant_cols, errors='ignore')
    
    print("Adding rolling features...")
    train = add_features(train)
    test = add_features(test)
    
    features = [c for c in train.columns if c not in ['engine', 'cycle', 'RUL']]
    kept_sensors = [f for f in features if not f.endswith('_roll_mean') and not f.endswith('_slope')]
    
    print("Splitting train into train/validation by engine ID...")
    np.random.seed(SEED)
    unique_engines = train['engine'].unique()
    val_engines = np.random.choice(unique_engines, size=N_VAL_ENGINES, replace=False)
    train_engines = [e for e in unique_engines if e not in val_engines]
    
    X_train = train[train['engine'].isin(train_engines)][features]
    y_train = train[train['engine'].isin(train_engines)]['RUL']
    
    X_val = train[train['engine'].isin(val_engines)][features]
    y_val = train[train['engine'].isin(val_engines)]['RUL']
    
    print("Training XGBRegressor...")
    model = XGBRegressor(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=SEED
    )
    model.fit(X_train, y_train)
    
    val_preds = model.predict(X_val)
    val_rmse = float(np.sqrt(mean_squared_error(y_val, val_preds)))
    print(f"Validation RMSE (on {N_VAL_ENGINES} held-out engines): {val_rmse:.2f}")
    
    last_cycles = test.groupby('engine').last().reset_index()
    X_test_final = last_cycles[features]
    test_preds = model.predict(X_test_final)
    
    test_rmse_raw = float(np.sqrt(mean_squared_error(rul_true['RUL'], test_preds)))
    rul_true_clipped = rul_true['RUL'].clip(upper=RUL_CLIP)
    test_rmse_clipped = float(np.sqrt(mean_squared_error(rul_true_clipped, test_preds)))
    
    print(f"Test RMSE (Raw vs predictions): {test_rmse_raw:.2f}")
    print(f"Test RMSE (Clipped at {RUL_CLIP} vs predictions): {test_rmse_clipped:.2f}")
    
    os.makedirs('ml', exist_ok=True)
    os.makedirs('docs', exist_ok=True)
    
    metadata = {
        'val_rmse': val_rmse,
        'test_rmse_raw': test_rmse_raw,
        'test_rmse_clipped': test_rmse_clipped,
        'n_train_engines': len(train_engines),
        'n_val_engines': len(val_engines),
        'kept_sensors': kept_sensors,
        'xgboost_version': xgb.__version__,
        'python_version': sys.version.split()[0],
        'features': features,
        'val_engines': val_engines.tolist()
    }
    
    joblib.dump({'model': model, 'metadata': metadata}, 'ml/model.joblib')
    model.save_model('ml/model.json')
    
    with open('docs/metrics.json', 'w') as f:
        json.dump(metadata, f, indent=4)
        
    print("Saved model to ml/model.joblib and ml/model.json, metrics to docs/metrics.json")

if __name__ == '__main__':
    main()

