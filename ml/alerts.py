import pandas as pd
from config import AS_OF

def generate_alerts(df_preds, df_master, df_parts, df_spares):
    # Only amber/red components
    trouble_comps = df_preds[df_preds['risk_level'].isin(['red', 'amber'])].copy()
    
    if trouble_comps.empty:
        return pd.DataFrame()
        
    as_of_str = trouble_comps['generated_at'].iloc[0]
    as_of_dt = pd.to_datetime(as_of_str)
    trouble_comps['days_to_failure'] = (pd.to_datetime(trouble_comps['predicted_failure_date']) - as_of_dt).dt.days
    
    # Map components to parts catalog by component and type
    trouble_comps = trouble_comps.merge(df_master[['aircraft_id', 'type']], on='aircraft_id', how='left')
    merged = trouble_comps.merge(df_parts, on=['type', 'component'], how='left')
    
    # Aggregate spares by part_no to get total qty
    total_stock = df_spares.groupby('part_no')['qty_on_hand'].sum().reset_index()
    max_reorder = df_spares.groupby('part_no')['reorder_level'].max().reset_index()
    if not total_stock.empty:
        spares_agg = total_stock.merge(max_reorder, on='part_no')
        merged = merged.merge(spares_agg, on='part_no', how='left')
    else:
        merged['qty_on_hand'] = 0
        merged['reorder_level'] = 0
    
    # Status logic
    statuses = []
    messages = []
    for _, row in merged.iterrows():
        dtf = row['days_to_failure']
        lt = row['lead_time_days']
        stock = row['qty_on_hand']
        reorder = row['reorder_level']
        
        if stock <= 0 and lt > dtf:
            status = "CANNOT ARRIVE IN TIME"
            msg = f"Part {row['part_no']} fails in {dtf} days, stock {stock}, lead time {lt} days: cannot arrive in time!"
        elif stock <= 0 or (stock <= reorder and lt >= dtf):
            status = "ORDER NOW"
            msg = f"Part {row['part_no']} fails in {dtf} days, stock {stock}, lead time {lt} days: order now."
        elif stock > reorder:
            status = "OK"
            msg = f"Part {row['part_no']} fails in {dtf} days, stock {stock}: OK."
        else:
            status = "WATCH"
            msg = f"Part {row['part_no']} fails in {dtf} days, stock {stock}: watch."
            
        statuses.append(status)
        messages.append(msg)
        
    merged['status'] = statuses
    merged['alert_message'] = messages
    
    # Sort by urgency
    status_order = {'CANNOT ARRIVE IN TIME': 0, 'ORDER NOW': 1, 'WATCH': 2, 'OK': 3}
    merged['_sort'] = merged['status'].map(status_order)
    merged = merged.sort_values(['_sort', 'days_to_failure']).drop(columns=['_sort'])
    
    return merged[['aircraft_id', 'component', 'days_to_failure', 'part_no', 'qty_on_hand', 'lead_time_days', 'status', 'alert_message', 'risk_level']]
