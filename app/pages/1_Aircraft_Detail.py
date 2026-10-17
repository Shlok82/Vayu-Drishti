import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
import sys

# Ensure ml modules can be imported

st.set_page_config(page_title="Aircraft Detail - Vayu Drishti", layout="wide")

@st.cache_data
def load_data():
    master_path = os.path.join('data', 'aircraft_master.csv')
    preds_path = os.path.join('data', 'predictions.csv')
    maint_path = os.path.join('data', 'maintenance_logs.csv')
    parts_path = os.path.join('data', 'parts_catalog.csv')
    spares_path = os.path.join('data', 'spares_inventory.csv')
    
    data = {}
    if os.path.exists(master_path): data['master'] = pd.read_csv(master_path)
    if os.path.exists(preds_path): data['preds'] = pd.read_csv(preds_path)
    if os.path.exists(maint_path): data['maint'] = pd.read_csv(maint_path)
    if os.path.exists(parts_path): data['parts'] = pd.read_csv(parts_path)
    if os.path.exists(spares_path): data['spares'] = pd.read_csv(spares_path)
    ws_path = os.path.join('data', 'workshops.csv')
    if os.path.exists(ws_path): data['workshops'] = pd.read_csv(ws_path)
    
    # Load raw train data for sensor history
    train_path = os.path.join('data', 'demo', 'heldout_engines.csv')
    if os.path.exists(train_path):
        data['train_history'] = pd.read_csv(train_path)
        
    # Same for test data for the actual engines of the aircraft
    test_path = os.path.join('data', 'demo', 'fleet_history.csv')
    if os.path.exists(test_path):
        data['test_history'] = pd.read_csv(test_path)
        
    return data

def main():
    st.title("Aircraft Detail")
    
    data = load_data()
    if 'master' not in data or 'preds' not in data:
        st.error("Data missing.")
        return
        
    master = data['master']
    preds = data['preds']
    
    ac_ids = master['aircraft_id'].unique()
    selected_ac = st.selectbox("Select Aircraft", ac_ids)
    
    ac_info = master[master['aircraft_id'] == selected_ac].iloc[0]
    
    st.subheader(f"Info: {selected_ac}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Base", ac_info['base'])
    col2.metric("Type", ac_info['type'])
    col3.metric("Flights / Day", ac_info['flights_per_day'])
    
    st.write("---")
    st.subheader("Component Predictions")
    
    ac_preds = preds[preds['aircraft_id'] == selected_ac].copy()
    ac_preds['is_simulated'] = ~ac_preds['component'].str.startswith('engine')
    ac_preds['Component Label'] = ac_preds.apply(lambda r: r['component'] if not r['is_simulated'] else f"{r['component']} (Simulated)", axis=1)
    
    def color_risk(val):
        color = 'red' if val == 'red' else 'orange' if val == 'amber' else 'green'
        return f'color: {color}; font-weight: bold'
        
    styled_preds = ac_preds[['Component Label', 'predicted_rul_cycles', 'predicted_failure_date', 'risk_level', 'health_score']].style.map(color_risk, subset=['risk_level'])
    st.dataframe(styled_preds, width="stretch", hide_index=True)
    
    st.write("---")
    st.subheader("Sensor Trend Chart (Test History)")
    # Find the actual engine IDs for this aircraft to plot their test history
    engine_ids = [int(x) for x in ac_info['engine_ids'].split(',')]
    
    if 'test_history' in data:
        test_history = data['test_history']
        for i, eng_id in enumerate(engine_ids):
            eng_data = test_history[test_history['engine'] == eng_id].sort_values('cycle')
            if not eng_data.empty:
                st.write(f"**Engine {i+1} (ID: {eng_id})**")
                # Plot representative sensors as z-scores vs first 10 cycles
                fig = go.Figure()
                sensor_colors = {'s2': '#2563EB', 's11': '#059669', 's14': '#DC2626'}
                for sensor in ['s2', 's11', 's14']:
                    baseline = eng_data[sensor].iloc[:10].mean()
                    std = eng_data[sensor].iloc[:10].std()
                    if pd.isna(std) or std == 0:
                        std = eng_data[sensor].std()
                    if std and std > 0:
                        y_norm = (eng_data[sensor] - baseline) / std
                    else:
                        y_norm = eng_data[sensor] - baseline
                    fig.add_trace(go.Scatter(
                        x=eng_data['cycle'],
                        y=y_norm,
                        mode='lines',
                        name=sensor,
                        line=dict(color=sensor_colors.get(sensor, '#2563EB'), width=2)
                    ))
                fig.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0), xaxis_title="Cycle", yaxis_title="Z-Score Deviation (vs first 10 cycles)")
                st.plotly_chart(fig, width="stretch")
                
    st.write("---")
    st.subheader("Spares Check")
    if 'parts' in data and 'spares' in data:
        df_parts = data['parts']
        df_spares = data['spares']
        trouble_comps = ac_preds[ac_preds['risk_level'].isin(['red', 'amber'])].copy()
        
        if not trouble_comps.empty:
            as_of_dt = pd.to_datetime(trouble_comps['generated_at'].iloc[0])
            trouble_comps['days_to_failure'] = (pd.to_datetime(trouble_comps['predicted_failure_date']) - as_of_dt).dt.days
            
            
            merged = trouble_comps.merge(df_parts, on=['aircraft_id', 'component'], how='left')
            
            total_stock = df_spares.groupby('part_no')['qty_on_hand'].sum().reset_index()
            max_reorder = df_spares.groupby('part_no')['reorder_level'].max().reset_index()
            spares_agg = total_stock.merge(max_reorder, on='part_no')
            
            merged = merged.merge(spares_agg, on='part_no', how='left')
            
            from ml.alerts import get_spares_status
            from ml.repair import get_repair_days
            df_ws = data.get('workshops', None)
            
            statuses = []
            for _, row in merged.iterrows():
                dtf = row['days_to_failure']
                lt = row['lead_time_days']
                stock = row['qty_on_hand']
                reorder = row['reorder_level']
                risk = row['risk_level']
                comp = row['component']
                repair_days = get_repair_days(comp, df_ws)
                statuses.append(get_spares_status(dtf, lt, stock, reorder, risk, repair_days))
            
            merged['status'] = statuses
            
            for _, row in merged[merged['status'] == 'ORDER NOW'].iterrows():
                st.error(f" **{row['Component Label']}**: Part {row['part_no']} fails in {row['days_to_failure']} days, stock {row['qty_on_hand']}, lead time {row['lead_time_days']} days. **ORDER NOW**")
                
            st.dataframe(merged[['Component Label', 'part_no', 'days_to_failure', 'qty_on_hand', 'lead_time_days', 'status']], width="stretch", hide_index=True)
        else:
            st.success("No amber or red components to check.")
            
    st.write("---")
    with st.expander("What-If Analysis (Extra Flight Hours)"):
        from ml.config import AVG_FLIGHT_HOURS_PER_CYCLE, AMBER_BELOW, RED_BELOW
        extra_hours = st.number_input("Add flight hours", value=50)
        extra_cycles = extra_hours / AVG_FLIGHT_HOURS_PER_CYCLE
        
        st.write(f"**Adding +{extra_hours} hours (+{extra_cycles:.1f} cycles)** (Linear approximation)")
        
        from ml.whatif import calculate_what_if_rul
        from ml.dates import get_failure_date
        what_if_data = []
        for _, row in ac_preds.iterrows():
            new_rul = calculate_what_if_rul(row['predicted_rul_cycles'], extra_hours)
            if new_rul < RED_BELOW: new_risk = 'red'
            elif new_rul <= AMBER_BELOW: new_risk = 'amber'
            else: new_risk = 'green'
            
            crosses = "Yes" if new_risk != row['risk_level'] else "No"
            new_fail_dt = get_failure_date(new_rul, ac_info['flights_per_day'])
            
            what_if_data.append({
                'Component': row['Component Label'],
                'Orig RUL': row['predicted_rul_cycles'],
                'New RUL': round(new_rul, 1),
                'Orig Risk': row['risk_level'],
                'New Risk': new_risk,
                'Crosses Threshold?': crosses,
                'New Failure Date': new_fail_dt
            })
        st.dataframe(pd.DataFrame(what_if_data), width="stretch", hide_index=True)
            
    st.write("---")
    st.subheader("Maintenance History")
    if 'maint' in data:
        ac_maint = data['maint'][data['maint']['aircraft_id'] == selected_ac].sort_values('date', ascending=False)
        st.dataframe(ac_maint.drop(columns=['aircraft_id']), width="stretch", hide_index=True)

if __name__ == '__main__':
    main()





