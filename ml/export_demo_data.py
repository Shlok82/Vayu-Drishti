import pandas as pd
import json
import os

def export_demo_data():
    os.makedirs('data/demo', exist_ok=True)
    
    # 1. Fleet History (test_FD001.txt) for the 48 fleet engines
    master = pd.read_csv('data/aircraft_master.csv')
    fleet_engines = set()
    for eng_str in master['engine_ids']:
        fleet_engines.update([int(x) for x in eng_str.split(',')])
        
    columns = ['engine', 'cycle', 'set1', 'set2', 'set3'] + [f's{i}' for i in range(1, 22)]
    test = pd.read_csv('data/raw/test_FD001.txt', sep=r'\s+', header=None, names=columns)
    
    fleet_data = test[test['engine'].isin(fleet_engines)]
    fleet_data.to_csv('data/demo/fleet_history.csv', index=False)
    
    # 2. Heldout Engines (train_FD001.txt)
    with open('docs/metrics.json', 'r') as f:
        metrics = json.load(f)
    val_engines = metrics['val_engines']
    
    train = pd.read_csv('data/raw/train_FD001.txt', sep=r'\s+', header=None, names=columns)
    val_data = train[train['engine'].isin(val_engines)].copy()
    
    max_cycles = val_data.groupby('engine')['cycle'].max()
    val_data['true_rul'] = val_data['engine'].map(max_cycles) - val_data['cycle']
    
    val_data.to_csv('data/demo/heldout_engines.csv', index=False)
    
    fleet_size = os.path.getsize('data/demo/fleet_history.csv') / (1024 * 1024)
    val_size = os.path.getsize('data/demo/heldout_engines.csv') / (1024 * 1024)
    
    print(f"Exported data/demo/fleet_history.csv ({fleet_size:.2f} MB)")
    print(f"Exported data/demo/heldout_engines.csv ({val_size:.2f} MB)")
    print(f"Total size of data/demo/: {fleet_size + val_size:.2f} MB")
    
if __name__ == '__main__':
    export_demo_data()
