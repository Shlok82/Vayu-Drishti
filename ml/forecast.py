import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import pandas as pd
from datetime import datetime, timedelta
from ml import config

def simulate_forecast(df_master, df_preds, recs_df, days=30):
    as_of_dt = datetime.strptime(config.AS_OF, "%Y-%m-%d %H:%M").date()
    
    # Precompute per-aircraft FPD and initial states
    ac_fpd = {row['aircraft_id']: row['flights_per_day'] for _, row in df_master.iterrows()}
    
    # Track component RULs
    initial_ruls = {}
    for _, row in df_preds.iterrows():
        ac_id = row['aircraft_id']
        if ac_id not in initial_ruls:
            initial_ruls[ac_id] = {}
        initial_ruls[ac_id][row['component']] = row['predicted_rul_cycles']
        
    # Planned slots: {ac_id: [(start, end, comp)]}
    planned_slots = {}
    if not recs_df.empty:
        for _, row in recs_df.iterrows():
            if row['flag'] == "":
                ac = row['aircraft_id']
                if ac not in planned_slots:
                    planned_slots[ac] = []
                st = datetime.strptime(row['slot_start'], "%Y-%m-%d").date()
                en = datetime.strptime(row['slot_end'], "%Y-%m-%d").date()
                planned_slots[ac].append({'start': st, 'end': en, 'comp': row['component']})
                
    # We will simulate 30 days
    no_action_ready = []
    planned_ready = []
    
    # State tracking
    # No action: aircraft just fails when RUL < 0 and stays down.
    # Planned: aircraft is down during slot, then RUL resets to 125.
    
    dates = [as_of_dt + timedelta(days=d) for d in range(days)]
    
    for plan_mode in [False, True]:
        counts = []
        
        # Initialize
        ruls = {ac: dict(comps) for ac, comps in initial_ruls.items()}
        # For reactive mode, we don't fix. For planned, we fix at the end of the slot.
        # Track currently in workshop
        in_workshop = {ac: False for ac in ac_fpd}
        failed = {ac: False for ac in ac_fpd} # If failed, it stays down in no_action
        
        for d in range(days):
            current_date = dates[d]
            ready_today = 0
            
            for ac, fpd in ac_fpd.items():
                is_ready = True
                
                # Update RULs (unless in workshop)
                # For simplicity, RUL falls by fpd if not in workshop
                if plan_mode and current_date >= as_of_dt:
                    # Check if in workshop today
                    is_in_ws = False
                    for slot in planned_slots.get(ac, []):
                        if slot['start'] <= current_date < slot['end']:
                            is_in_ws = True
                            break
                        elif current_date == slot['end']:
                            # Reset RUL
                            ruls[ac][slot['comp']] = 125.0
                    
                    if is_in_ws:
                        is_ready = False
                    else:
                        # degrade
                        for comp in ruls[ac]:
                            ruls[ac][comp] -= fpd
                else:
                    # No action (or before AS_OF)
                    for comp in ruls[ac]:
                        ruls[ac][comp] -= fpd
                        
                # Check red/failed
                for comp, rul in ruls[ac].items():
                    if rul <= config.RED_BELOW:
                        is_ready = False
                    if rul <= 0:
                        failed[ac] = True
                        
                if failed[ac]:
                    is_ready = False
                    
                if is_ready:
                    ready_today += 1
                    
            counts.append(ready_today)
            
        if plan_mode:
            planned_ready = counts
        else:
            no_action_ready = counts
            
    return pd.DataFrame({
        'Date': dates,
        'No Action': no_action_ready,
        'Plan': planned_ready
    })

