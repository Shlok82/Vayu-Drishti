import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import pandas as pd
from datetime import datetime, timedelta
from ml.config import AS_OF, MISSION_PRIORITY_WEIGHTS

def get_recommendations(alerts_df, df_ws, df_sched, df_master):
    if alerts_df.empty:
        return pd.DataFrame()
        
    as_of_dt = datetime.strptime(AS_OF, "%Y-%m-%d %H:%M")
    
    # Sort alerts by priority: red first, then days_to_failure
    alerts_df['risk_score'] = alerts_df['risk_level'].map({'red': 0, 'amber': 1, 'green': 2})
    alerts_df = alerts_df.sort_values(['risk_score', 'days_to_failure'])
    
    ws_cap = df_ws.set_index('workshop_id')['capacity_slots'].to_dict()
    ws_usage = {ws: {} for ws in ws_cap}
    
    recs = []
    for _, alert in alerts_df.iterrows():
        ac = alert['aircraft_id']
        comp = alert['component']
        dtf = alert['days_to_failure']
        fail_date = as_of_dt + timedelta(days=dtf)
        part_lt = alert['lead_time_days'] if alert['qty_on_hand'] <= 0 else 0
        
        part_arrival = as_of_dt + timedelta(days=part_lt)
        
        # Determine valid workshops (can be any for now, just pick fastest turnaround)
        best_ws = None
        best_slot_start = None
        best_slot_end = None
        best_cost = float('inf')
        best_missions = []
        best_flag = ""
        best_action = ""
        
        # Consider all workshops, find the first available slot >= part_arrival
        for _, ws in df_ws.iterrows():
            ws_id = ws['workshop_id']
            ta = ws['turnaround_days']
            cap = ws_cap[ws_id]
            
            # Start searching from part arrival or AS_OF
            search_start = max(as_of_dt, part_arrival).date()
            fail_date_only = fail_date.date()
            
            # Find earliest slot that fits capacity
            slot_start = search_start
            while True:
                # Check capacity for `ta` days
                can_fit = True
                for d in range(ta):
                    d_date = slot_start + timedelta(days=d)
                    if ws_usage[ws_id].get(d_date, 0) >= cap:
                        can_fit = False
                        break
                if can_fit:
                    break
                slot_start += timedelta(days=1)
                
            slot_end = slot_start + timedelta(days=ta)
            
            # Evaluate missions affected
            missions = []
            cost = 0
            # Filter schedule for this aircraft
            ac_sched = df_sched[df_sched['aircraft_id'] == ac]
            
            out_of_horizon = False
            for d in range(ta):
                d_date = slot_start + timedelta(days=d)
                days_from_as_of = (d_date - as_of_dt.date()).days
                if days_from_as_of >= 60:
                    out_of_horizon = True
                    break
                
                day_missions = ac_sched[ac_sched['date'] == d_date.strftime("%Y-%m-%d")]
                for _, m in day_missions.iterrows():
                    m_id = m['mission_id']
                    prio = m['priority']
                    w = MISSION_PRIORITY_WEIGHTS.get(prio, 1)
                    missions.append({'id': m_id, 'priority': prio, 'date': d_date.strftime("%Y-%m-%d")})
                    cost += w
                    
            flag = ""
            action = ""
            if part_arrival.date() > fail_date_only:
                flag = "PART_ARRIVES_AFTER_FAILURE"
                action = "Expedite part or plan to ground aircraft."
            elif slot_end > fail_date_only:
                flag = "REPAIR_ENDS_AFTER_FAILURE"
                action = "Cannibalise part or accept downtime."
            elif cost > 0:
                flag = "HIGH_PRIORITY_CONFLICT"
                action = "Reschedule missions."
                
            if best_ws is None or cost < best_cost or (cost == best_cost and slot_start < best_slot_start):
                best_ws = ws_id
                best_slot_start = slot_start
                best_slot_end = slot_end
                best_cost = cost
                best_missions = missions
                best_flag = flag
                best_action = action
                best_out_of_horizon = out_of_horizon
                
        # Commit to best_ws
        ta = df_ws[df_ws['workshop_id'] == best_ws]['turnaround_days'].iloc[0]
        for d in range(ta):
            d_date = best_slot_start + timedelta(days=d)
            ws_usage[best_ws][d_date] = ws_usage[best_ws].get(d_date, 0) + 1
            
        m_count = len(best_missions)
        m_text = "outside schedule horizon" if best_out_of_horizon else m_count
        
        recs.append({
            'aircraft_id': ac,
            'component': comp,
            'workshop_id': best_ws,
            'slot_start': best_slot_start.strftime("%Y-%m-%d"),
            'slot_end': best_slot_end.strftime("%Y-%m-%d"),
            'missions_affected_count': m_text,
            'mission_cost': best_cost,
            'mission_details': best_missions,
            'flag': best_flag,
            'recommended_action': best_action,
            'predicted_failure': fail_date.strftime("%Y-%m-%d")
        })
        
    return pd.DataFrame(recs)
