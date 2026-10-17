import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import pandas as pd
from ml.config import DATA_DIR

_WORKSHOPS_CACHE = None

def load_workshops(df_ws=None):
    global _WORKSHOPS_CACHE
    if df_ws is not None and not df_ws.empty:
        return df_ws
    if _WORKSHOPS_CACHE is None:
        _WORKSHOPS_CACHE = pd.read_csv(DATA_DIR / 'workshops.csv')
    return _WORKSHOPS_CACHE

def get_repair_days(component: str = 'engine_1', df_ws=None) -> int:
    """
    Returns component repair time in days from data/workshops.csv:
    - engine components ('engine_1', 'engine_2', 'engine') -> 'Engines' workshop = 3 days
    - avionics components ('avionics_unit', 'avionics') -> 'Avionics' workshop = 2 days
    - hydraulics components ('hydraulic_pump', 'landing_gear_actuator', 'hydraulics') -> 'Hydraulics' workshop = 3 days
    - other / general components ('generator', etc.) -> 'General' workshop = 5 days
    """
    ws = load_workshops(df_ws)
    comp_lower = str(component).lower()
    
    if 'engine' in comp_lower:
        spec = 'Engines'
    elif 'avionic' in comp_lower:
        spec = 'Avionics'
    elif 'hydraul' in comp_lower or 'gear' in comp_lower or 'actuator' in comp_lower:
        spec = 'Hydraulics'
    else:
        spec = 'General'
        
    matched = ws[ws['specialisation'] == spec]
    if not matched.empty:
        return int(matched.iloc[0]['turnaround_days'])
        
    general = ws[ws['specialisation'] == 'General']
    if not general.empty:
        return int(general.iloc[0]['turnaround_days'])
    return 3
