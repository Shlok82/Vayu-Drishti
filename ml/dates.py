from datetime import datetime, timedelta
from ml.config import AS_OF

def get_days_to_failure(rul_cycles, flights_per_day):
    if flights_per_day <= 0:
        return 9999.0
    return float(rul_cycles) / float(flights_per_day)

def get_failure_date(rul_cycles, flights_per_day):
    days = get_days_to_failure(rul_cycles, flights_per_day)
    as_of_dt = datetime.strptime(AS_OF, "%Y-%m-%d %H:%M")
    return (as_of_dt + timedelta(days=days)).strftime("%Y-%m-%d")

