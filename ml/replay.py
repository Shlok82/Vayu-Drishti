import pandas as pd
import joblib
import numpy as np

from ml.config import RED_BELOW, AMBER_BELOW, RUL_CLIP

_MODEL = None
_METADATA = None
_DATA = None

def load_resources():
    global _MODEL, _METADATA, _DATA
    if _MODEL is None:
        data = joblib.load('ml/model.joblib')
        _MODEL = data['model']
        _METADATA = data['metadata']
        
        # Load train (which contains heldout engines)
        # Load heldout engines from demo
        _DATA = pd.read_csv('data/demo/heldout_engines.csv')

def replay(engine_id, source="heldout"):
    load_resources()
    
    eng_data = _DATA[_DATA['engine'] == engine_id].sort_values('cycle').copy()
    if eng_data.empty:
        raise ValueError(f"Engine {engine_id} not found in source {source}")
        
    max_cycle = eng_data['cycle'].max()
    eng_data['true_rul'] = max_cycle - eng_data['cycle']
    
    sensor_cols = [c for c in eng_data.columns if c.startswith('s') or c.startswith('set')]
    eng_data_sensors = eng_data[sensor_cols]
    
    # Need to compute rolling and slope
    df_rolled = eng_data_sensors.rolling(10, min_periods=1).mean()
    df_rolled.columns = [f'{c}_roll_mean' for c in sensor_cols]
    
    df_diff = eng_data_sensors.diff(periods=9) / 9.0
    df_diff.columns = [f'{c}_slope' for c in sensor_cols]
    df_diff = df_diff.fillna(0)
    
    eval_df = pd.concat([eng_data.reset_index(drop=True), df_rolled.reset_index(drop=True), df_diff.reset_index(drop=True)], axis=1)
    
    features = _METADATA['features']
    preds = _MODEL.predict(eval_df[features])
    
    # Clip preds to valid range
    preds = np.clip(preds, a_min=0.0, a_max=RUL_CLIP)
    
    def get_risk(rul):
        if rul < RED_BELOW: return 'red'
        if rul <= AMBER_BELOW: return 'amber'
        return 'green'
        
    risks = [get_risk(r) for r in preds]
    healths = [min(100.0, max(0.0, (r / RUL_CLIP) * 100.0)) for r in preds]
    
    out_df = eng_data[['cycle'] + _METADATA['kept_sensors'] + ['true_rul']].copy()
    out_df['predicted_rul'] = preds
    out_df['risk_level'] = risks
    out_df['health_score'] = healths
    
    return out_df

if __name__ == "__main__":
    df = replay(71)
    print(df.tail())
