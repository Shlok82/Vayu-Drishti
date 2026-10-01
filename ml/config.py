import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / 'data'
DOCS_DIR = ROOT_DIR / 'docs'

RUL_CLIP = 125
RED_BELOW = 30
AMBER_BELOW = 80
SEED = 42
N_VAL_ENGINES = 20
AS_OF = "2026-10-01 09:00"
FLEET_SIZE = 24
DEMO_ENGINE_ID = 71
DEMO_AIRCRAFT_ID = 'AF-1001'
COMPONENTS = ['engine_1', 'engine_2', 'hydraulic_pump', 'generator', 'avionics_unit', 'landing_gear_actuator']

# Planner Config
MISSION_PRIORITY_WEIGHTS = {'low': 1, 'medium': 2, 'high': 4}
AVG_FLIGHT_HOURS_PER_CYCLE = 1.5
WATCH_MARGIN_DAYS = 30
ORDER_MARGIN_DAYS = 14


