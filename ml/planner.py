import pandas as pd
from datetime import datetime, timedelta
import config

def get_recommendations(alerts_df, df_workshops, df_schedule, df_master):
    recommendations = []
    
    # Track workshop capacities per day
    ws_capacity = {row['workshop_id']: row['capacity_slots'] for _, row in df_workshops.iterrows()}
    ws_turnaround = {row['workshop_id']: row['turnaround_days'] for _, row in df_workshops.iterrows()}
    
    # State tracking: {workshop_id: {date_str: slots_used}}
    daily_usage = {ws_id: {} for ws_id in ws_capacity}
    
    as_of_dt = datetime.strptime(config.AS_OF, "%Y-%m-%d %H:%M").date()
    
    # Only amber/red from alerts
    urgency_df = alerts_df.copy()
    if urgency_df.empty:
        return pd.DataFrame()
        
    urgency_df = urgency_df.sort_values('days_to_failure')
    
    # Convert schedule to dict for fast lookup
    # {ac_id: {date_str: {mission_id, priority}}}
    schedule = {}
    for _, row in df_schedule.iterrows():
        ac = row['aircraft_id']
        dt = row['date']
        if ac not in schedule:
            schedule[ac] = {}
        schedule[ac][dt] = {'id': row['mission_id'], 'priority': row['priority']}
        
    for _, alert in urgency_df.iterrows():
        ac_id = alert['aircraft_id']
        dtf = alert['days_to_failure']
        stock = alert['qty_on_hand']
        lt = alert['lead_time_days']
        
        fail_date = as_of_dt + timedelta(days=int(dtf))
        
        # Earliest start
        if stock > 0:
            earliest_start = as_of_dt
        else:
            earliest_start = as_of_dt + timedelta(days=lt)
            
        best_slot = None
        best_ws = None
        min_cost = float('inf')
        best_affected = []
        
        # We search up to fail_date - turnaround
        for ws_id, cap in ws_capacity.items():
            turnaround = ws_turnaround[ws_id]
            
            # Latest possible start date so it finishes before fail_date
            latest_start = fail_date - timedelta(days=turnaround)
            
            if earliest_start > latest_start:
                continue # Cannot finish in time
                
            # Scan possible start dates
            for start_day_offset in range((latest_start - earliest_start).days + 1):
                start_candidate = earliest_start + timedelta(days=start_day_offset)
                
                # Check capacity
                feasible = True
                for d in range(turnaround):
                    d_date = (start_candidate + timedelta(days=d)).strftime("%Y-%m-%d")
                    if daily_usage[ws_id].get(d_date, 0) >= cap:
                        feasible = False
                        break
                
                if feasible:
                    # Calculate mission cost
                    cost = 0
                    affected = []
                    ac_sched = schedule.get(ac_id, {})
                    for d in range(turnaround):
                        d_date = (start_candidate + timedelta(days=d)).strftime("%Y-%m-%d")
                        if d_date in ac_sched:
                            msn = ac_sched[d_date]
                            cost += config.MISSION_PRIORITY_WEIGHTS.get(msn['priority'], 1)
                            affected.append(f"{msn['id']} ({msn['priority']})")
                            
                    if cost < min_cost:
                        min_cost = cost
                        best_slot = start_candidate
                        best_ws = ws_id
                        best_affected = affected
                        
                    if cost == 0:
                        break # Cannot get better than 0 cost
        
        if best_slot:
            turnaround = ws_turnaround[best_ws]
            end_date = best_slot + timedelta(days=turnaround)
            for d in range(turnaround):
                d_date = (best_slot + timedelta(days=d)).strftime("%Y-%m-%d")
                daily_usage[best_ws][d_date] = daily_usage[best_ws].get(d_date, 0) + 1
                
            recommendations.append({
                'aircraft_id': ac_id,
                'component': alert['component'],
                'risk': alert['risk_level'],
                'workshop_id': best_ws,
                'slot_start': best_slot.strftime("%Y-%m-%d"),
                'slot_end': end_date.strftime("%Y-%m-%d"),
                'missions_affected': ", ".join(best_affected) if best_affected else "None",
                'flag': ""
            })
        else:
            # Infeasible, just pick the earliest_start in the first workshop, and flag it
            best_ws = list(ws_capacity.keys())[0]
            turnaround = ws_turnaround[best_ws]
            best_slot = earliest_start
            end_date = best_slot + timedelta(days=turnaround)
            
            if earliest_start > fail_date - timedelta(days=turnaround):
                flag = "Part cannot arrive in time"
            else:
                flag = "No capacity available"
                
            recommendations.append({
                'aircraft_id': ac_id,
                'component': alert['component'],
                'risk': alert['risk_level'],
                'workshop_id': best_ws,
                'slot_start': best_slot.strftime("%Y-%m-%d"),
                'slot_end': end_date.strftime("%Y-%m-%d"),
                'missions_affected': "Unknown",
                'flag': flag
            })
            
    return pd.DataFrame(recommendations)
