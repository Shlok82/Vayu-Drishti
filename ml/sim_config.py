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
    'workshop_capacity': 14, # Rationale: Capacity of 2 caused infinite queue loops. Now sum of capacity_slots (14). Effect: allows realistic throughput.
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

SENSITIVITIES = {
    # Diagnosis delay range: evaluates sensitivity to field diagnosis lag from 0 (instant digital telemetry) to 10 days
    'diagnosis_delay_days': [0, 2, 5, 10],
    # Reactive repair day ranges: evaluates unscheduled repair time from fast [1, 3] to nominal [3, 7] and delayed [10, 20] days
    'repair_days_reactive': [[1, 3], [3, 7], [10, 20]],
    # Predictive repair days: paired with reactive ranges; nominal set to 2 matching baseline PREDICTIVE['repair_days']
    'repair_days_predictive': [1, 2, 7],
    # Part lead time multiplier: evaluates supply chain variation from expedited (0.5x) to delayed (2.0x)
    'lead_time_multipliers': [0.5, 1.0, 2.0],
    # False alarm rate: evaluates model precision impact from 1% (clean predictions) to 20% (frequent false alarms)
    'false_alarm_rates': [0.01, 0.05, 0.20],
    # Alert lead time multiplier: evaluates model warning horizon from compressed (0.5x) to extended (1.5x)
    'alert_lead_time_multipliers': [0.5, 1.0, 1.5]
}

def load_sim_config():
    return {
        'simulation': SIMULATION,
        'reactive': REACTIVE,
        'predictive': PREDICTIVE,
        'weaker_model': WEAKER_MODEL,
        'sensitivities': SENSITIVITIES
    }
