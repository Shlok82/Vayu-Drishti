import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
# Simulation config

SIMULATION = {
    'days': 90, # Days to simulate
    'runs': 200, # Number of Monte Carlo iterations
    'seed': 42, # Random seed for reproducibility
    'workshop_capacity': 2, # Workshop capacity cap
    'mission_cost_weights': {'low': 1, 'medium': 2, 'high': 4} # Mission weights for computing costs
}

REACTIVE = {
    'diagnosis_delay_days': 2, # Days taken to diagnose failure before starting repair
    'repair_days': [3, 7] # Days taken to repair range
}

PREDICTIVE = {
    'false_alarm_rate': 0.05, # Ratio of false alarms (maintenance done but no failure imminent)
    'repair_days': 2, # Time taken for planned repair
    'lead_time_multiplier': 1.0, # Lead time multiplier if part is not in stock
    'alert_lead_time_source': 'metrics.json' # Source of the alert lead-time distribution
}

WEAKER_MODEL = {
    'alert_lead_time_multiplier': 0.5 # Case where model alert time is halved
}

def load_sim_config():
    return {
        'simulation': SIMULATION,
        'reactive': REACTIVE,
        'predictive': PREDICTIVE,
        'weaker_model': WEAKER_MODEL
    }

