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
    
    # Sort alerts by days_to_failure
    alerts_df = alerts_df.sort_values('days_to_failure')
    
    ws_cap = df_ws.set_index('workshop_id')['capacity_slots'].to_dict()
    ws_usage = {ws: {s: set() for s in range(cap)} for ws, cap in ws_cap.items()}
    
    # Precompute missions
    sched_dict = {}
    for _, row in df_sched.iterrows():
        ac = row['aircraft_id']
        d_str = row['date']
        if ac not in sched_dict:
            sched_dict[ac] = {}
        if d_str not in sched_dict[ac]:
            sched_dict[ac][d_str] = []
        sched_dict[ac][d_str].append({'id': row['mission_id'], 'priority': row['priority']})
    
    recs = []
    for _, alert in alerts_df.iterrows():
        ac = alert['aircraft_id']
        comp = alert['component']
        dtf = alert['days_to_failure']
        fail_date = as_of_dt + timedelta(days=dtf)
        part_lt = alert['lead_time_days'] if alert['qty_on_hand'] <= 0 else 0
        part_arrival = as_of_dt + timedelta(days=int(part_lt))
        
        best_ws = None
        best_slot_start = None
        best_slot_end = None
        best_slot_index = None
        best_cost = float('inf')
        best_missions = []
        best_flag = ""
        best_action = ""
        best_out_of_horizon = False
        
        # Determine specialized workshops for component
        comp_lower = comp.lower()
        if 'engine' in comp_lower: target_spec = 'Engines'
        elif 'avionic' in comp_lower: target_spec = 'Avionics'
        elif 'hydraul' in comp_lower or 'gear' in comp_lower or 'actuator' in comp_lower: target_spec = 'Hydraulics'
        else: target_spec = 'General'
        
        matched_ws = df_ws[df_ws['specialisation'] == target_spec]
        if matched_ws.empty:
            matched_ws = df_ws[df_ws['specialisation'] == 'General']
        
        search_start = max(as_of_dt, part_arrival).date()
        cand = search_start
        while best_slot_end is None or cand < best_slot_end.date():
            for _, ws in matched_ws.iterrows():
                ws_id = ws['workshop_id']
                ta = int(ws['turnaround_days'])
                cap = int(ws_cap[ws_id])
                slot_end = cand + timedelta(days=ta)
                
                for slot_idx in range(cap):
                    if all((cand + timedelta(days=d)) not in ws_usage[ws_id][slot_idx] for d in range(ta)):
                        missions = []
                        cost = 0
                        out_of_horizon = False
                        
                        ac_dict = sched_dict.get(ac, {})
                        for d in range(ta):
                            d_date = cand + timedelta(days=d)
                            d_str = d_date.strftime("%Y-%m-%d")
                            days_from_as_of = (datetime.combine(d_date, datetime.min.time()) - as_of_dt).days
                            if days_from_as_of >= 60:
                                out_of_horizon = True
                                break
                            for m in ac_dict.get(d_str, []):
                                prio = m['priority']
                                w = MISSION_PRIORITY_WEIGHTS.get(prio, 1)
                                missions.append({'id': m['id'], 'priority': prio, 'date': d_str})
                                cost += w
                                
                        is_better = False
                        if best_slot_end is None or slot_end < best_slot_end.date():
                            is_better = True
                        elif slot_end == best_slot_end.date() and cost < best_cost:
                            is_better = True
                                
                        if is_better:
                            best_ws = ws_id
                            best_slot_start = datetime.combine(cand, datetime.min.time())
                            best_slot_end = datetime.combine(slot_end, datetime.min.time())
                            best_slot_index = slot_idx
                            best_cost = cost
                            best_missions = missions
                            best_out_of_horizon = out_of_horizon
            cand += timedelta(days=1)
            
        has_high_priority = any(m['priority'] == 'high' for m in best_missions)
        if part_arrival.date() > fail_date.date():
            best_flag = "PART_ARRIVES_AFTER_FAILURE"
            best_action = "Expedite part or plan to ground aircraft."
        elif best_slot_start.date() > fail_date.date():
            best_flag = "REPAIR_STARTS_AFTER_FAILURE"
            best_action = "Cannibalise part or accept downtime."
        elif best_slot_end.date() > fail_date.date():
            best_flag = "REPAIR_ENDS_AFTER_FAILURE"
            best_action = "Cannibalise part or accept downtime."
        elif has_high_priority:
            best_flag = "HIGH_PRIORITY_CONFLICT"
            best_action = "Reschedule missions."
                
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

