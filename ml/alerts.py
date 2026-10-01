import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import pandas as pd
from datetime import datetime
from ml.config import AS_OF, ORDER_MARGIN_DAYS, WATCH_MARGIN_DAYS

def get_spares_status(dtf, lt, stock, reorder, risk, min_turnaround):
    if stock >= 1:
        if risk == 'red':
            return "SCHEDULE NOW (IN STOCK)"
        if risk == 'amber' and stock <= reorder:
            return "WATCH"
        return "OK"
    else:
        need_days = lt + min_turnaround
        slack = dtf - need_days
        if slack < 0:
            return "CANNOT ARRIVE IN TIME"
        elif slack <= ORDER_MARGIN_DAYS:
            return "ORDER NOW"
        elif slack <= WATCH_MARGIN_DAYS or risk in ['amber', 'red']:
            return "WATCH"
        else:
            return "OK"

def generate_alerts(df_preds, df_master, df_parts, df_spares, df_ws=None):
    urgency_df = df_preds[df_preds['risk_level'].isin(['red', 'amber'])].copy()
    if urgency_df.empty:
        return pd.DataFrame()
        
    as_of_dt = datetime.strptime(AS_OF, "%Y-%m-%d %H:%M")
    
    urgency_df = urgency_df.merge(df_master[['aircraft_id', 'type', 'flights_per_day']], on='aircraft_id', how='left')
    from ml.dates import get_days_to_failure
    urgency_df['days_to_failure'] = urgency_df.apply(lambda row: get_days_to_failure(row['predicted_rul_cycles'], row['flights_per_day']), axis=1)
    
    # We need to map variants. The components in df_preds are just 'engine_1' etc.
    # We must match by aircraft_id and component? But parts_catalog only has 'type'.
    # Our synthetic data parts_catalog uses the 'type' string like 'Generic Fighter Trainer - V1'
    urgency_df = urgency_df.merge(df_parts[['aircraft_id', 'component', 'part_no', 'lead_time_days']], on=['aircraft_id', 'component'], how='left')
    
    stock_agg = df_spares.groupby('part_no')['qty_on_hand'].sum().reset_index()
    reorder_agg = df_spares.groupby('part_no')['reorder_level'].max().reset_index()
    spares_info = stock_agg.merge(reorder_agg, on='part_no')
    
    urgency_df = urgency_df.merge(spares_info, on='part_no', how='left')
    
    min_turnaround = 5
    if df_ws is not None and not df_ws.empty:
        min_turnaround = df_ws['turnaround_days'].min()
    
    # Sort by days_to_failure ascending
    urgency_df = urgency_df.sort_values('days_to_failure')
    
    alerts = []
    for _, row in urgency_df.iterrows():
        ac_id = row['aircraft_id']
        comp = row['component']
        dtf = row['days_to_failure']
        risk = row['risk_level']
        part_no = row['part_no']
        lt = row['lead_time_days']
        stock = row.get('qty_on_hand', 0)
        reorder = row.get('reorder_level', 0)
        
        status = get_spares_status(dtf, lt, stock, reorder, risk, min_turnaround)
        
        reorder_text = ", below reorder level, reorder" if stock <= reorder and stock >= 1 else ""
        
        if status == "SCHEDULE NOW (IN STOCK)":
            action_text = "schedule now" + reorder_text
        elif status == "ORDER NOW":
            action_text = "order now"
        elif status == "CANNOT ARRIVE IN TIME":
            action_text = "cannot arrive in time"
        elif status == "WATCH":
            action_text = "watch" + reorder_text
        else:
            action_text = "ok" + reorder_text

        msg = f"Part {part_no} fails in {int(dtf)} days, stock {int(stock)}, lead time {int(lt)} days, repair {int(min_turnaround)} days: {action_text}."
        
        alerts.append({
            'aircraft_id': ac_id,
            'component': comp,
            'days_to_failure': dtf,
            'part_no': part_no,
            'qty_on_hand': stock,
            'reorder_level': reorder,
            'lead_time_days': lt,
            'risk_level': risk,
            'status': status,
            'alert_message': msg,
            'min_turnaround': min_turnaround
        })
        
    return pd.DataFrame(alerts)



