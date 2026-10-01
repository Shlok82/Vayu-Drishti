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
    # Track usage per specific capacity slot: ws_usage[ws_id][slot_index][date] = bool
    ws_usage = {ws: {s: set() for s in range(cap)} for ws, cap in ws_cap.items()}
    
    recs = []
    for _, alert in alerts_df.iterrows():
        ac = alert['aircraft_id']
        comp = alert['component']
        dtf = alert['days_to_failure']
        fail_date = as_of_dt + timedelta(days=dtf)
        part_lt = alert['lead_time_days'] if alert['qty_on_hand'] <= 0 else 0
        
        part_arrival = as_of_dt + timedelta(days=part_lt)
        
        best_ws = None
        best_slot_start = None
        best_slot_end = None
        best_slot_index = None
        best_cost = float('inf')
        best_missions = []
        best_flag = ""
        best_action = ""
        best_out_of_horizon = False
        
        # Consider all workshops
        for _, ws in df_ws.iterrows():
            ws_id = ws['workshop_id']
            ta = ws['turnaround_days']
            cap = ws_cap[ws_id]
            
            search_start = max(as_of_dt, part_arrival).date()
            latest_start = fail_date.date() - timedelta(days=ta)
            
            # Find the best slot from search_start up to something far (e.g. search_start + 60)
            # We want to check all candidate dates from search_start to max(latest_start, search_start + 60)
            end_search = max(latest_start, search_start + timedelta(days=60))
            
            candidate_date = search_start
            while candidate_date <= end_search:
                # Can it fit in any slot index of this workshop?
                for slot_idx in range(cap):
                    can_fit = True
                    for d in range(ta):
                        if (candidate_date + timedelta(days=d)) in ws_usage[ws_id][slot_idx]:
                            can_fit = False
                            break
                    if can_fit:
                        # Evaluate missions affected
                        missions = []
                        cost = 0
                        has_high_priority = False
                        
                        ac_sched = df_sched[df_sched['aircraft_id'] == ac]
                        out_of_horizon = False
                        
                        for d in range(ta):
                            d_date = candidate_date + timedelta(days=d)
                            days_from_as_of = (datetime.combine(d_date, datetime.min.time()) - as_of_dt).days
                            if days_from_as_of >= 60:
                                out_of_horizon = True
                                break
                            
                            day_missions = ac_sched[ac_sched['date'] == d_date.strftime("%Y-%m-%d")]
                            for _, m in day_missions.iterrows():
                                m_id = m['mission_id']
                                prio = m['priority']
                                if prio == 'high': has_high_priority = True
                                w = MISSION_PRIORITY_WEIGHTS.get(prio, 1)
                                missions.append({'id': m_id, 'priority': prio, 'date': d_date.strftime("%Y-%m-%d")})
                                cost += w
                                
                        # Determine flags for this candidate
                        slot_end = candidate_date + timedelta(days=ta)
                        
                        flag = ""
                        action = ""
                        if part_arrival.date() > fail_date.date():
                            flag = "PART_ARRIVES_AFTER_FAILURE"
                            action = "Expedite part or plan to ground aircraft."
                        elif slot_end > fail_date.date():
                            flag = "REPAIR_ENDS_AFTER_FAILURE"
                            action = "Cannibalise part or accept downtime."
                        elif has_high_priority:
                            flag = "HIGH_PRIORITY_CONFLICT"
                            action = "Reschedule missions."
                            
                        # If this is strictly better (lower cost) or (same cost but earlier)
                        if best_ws is None or cost < best_cost or (cost == best_cost and candidate_date < best_slot_start.date()):
                            best_ws = ws_id
                            best_slot_start = datetime.combine(candidate_date, datetime.min.time())
                            best_slot_end = datetime.combine(slot_end, datetime.min.time())
                            best_slot_index = slot_idx
                            best_cost = cost
                            best_missions = missions
                            best_flag = flag
                            best_action = action
                            best_out_of_horizon = out_of_horizon
                            
                candidate_date += timedelta(days=1)
                
        # Commit to the best slot
        ta = df_ws[df_ws['workshop_id'] == best_ws]['turnaround_days'].iloc[0]
        for d in range(ta):
            ws_usage[best_ws][best_slot_index].add((best_slot_start + timedelta(days=d)).date())
            
        m_count = len(best_missions)
        m_text = "outside schedule horizon" if best_out_of_horizon else m_count
        
        recs.append({
            'aircraft_id': ac,
            'component': comp,
            'workshop_id': best_ws,
            'capacity_slot': best_slot_index + 1,
            'lane_id': f"{best_ws} (Slot {best_slot_index + 1})",
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
