
from ml.config import AVG_FLIGHT_HOURS_PER_CYCLE
def calculate_what_if_rul(base_rul, extra_hours):
    extra_cycles = extra_hours / AVG_FLIGHT_HOURS_PER_CYCLE
    return max(0.0, base_rul - extra_cycles)
