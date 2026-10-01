import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
import sys

# Ensure ml modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

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
    st.dataframe(styled_preds, use_container_width=True, hide_index=True)
    
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
                # Plot a couple of representative sensors that degrade, e.g., s2, s11, s14
                fig = go.Figure()
                for sensor in ['s2', 's11', 's14']:
                    fig.add_trace(go.Scatter(x=eng_data['cycle'], y=eng_data[sensor], mode='lines', name=sensor))
                fig.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0), xaxis_title="Cycle", yaxis_title="Sensor Value")
                st.plotly_chart(fig, use_container_width=True)
                
    st.write("---")
    st.subheader("Spares Check")
    if 'parts' in data and 'spares' in data:
        df_parts = data['parts']
        df_spares = data['spares']
        trouble_comps = ac_preds[ac_preds['risk_level'].isin(['red', 'amber'])].copy()
        
        if not trouble_comps.empty:
            as_of_dt = pd.to_datetime(trouble_comps['generated_at'].iloc[0])
            trouble_comps['days_to_failure'] = (pd.to_datetime(trouble_comps['predicted_failure_date']) - as_of_dt).dt.days
            
            trouble_comps['type'] = ac_info['type']
            merged = trouble_comps.merge(df_parts, on=['type', 'component'], how='left')
            
            total_stock = df_spares.groupby('part_no')['qty_on_hand'].sum().reset_index()
            max_reorder = df_spares.groupby('part_no')['reorder_level'].max().reset_index()
            spares_agg = total_stock.merge(max_reorder, on='part_no')
            
            merged = merged.merge(spares_agg, on='part_no', how='left')
            
            statuses = []
            for _, row in merged.iterrows():
                dtf = row['days_to_failure']
                lt = row['lead_time_days']
                stock = row['qty_on_hand']
                reorder = row['reorder_level']
                
                if stock <= 0 or (stock <= reorder and lt >= dtf):
                    statuses.append("ORDER NOW")
                elif stock > reorder:
                    statuses.append("OK")
                else:
                    statuses.append("WATCH")
            
            merged['status'] = statuses
            
            for _, row in merged[merged['status'] == 'ORDER NOW'].iterrows():
                st.error(f"⚠️ **{row['Component Label']}**: Part {row['part_no']} fails in {row['days_to_failure']} days, stock {row['qty_on_hand']}, lead time {row['lead_time_days']} days. **ORDER NOW**")
                
            st.dataframe(merged[['Component Label', 'part_no', 'days_to_failure', 'qty_on_hand', 'lead_time_days', 'status']], use_container_width=True, hide_index=True)
        else:
            st.success("No amber or red components to check.")
            
    st.write("---")
    st.subheader("Maintenance History")
    if 'maint' in data:
        ac_maint = data['maint'][data['maint']['aircraft_id'] == selected_ac].sort_values('date', ascending=False)
        st.dataframe(ac_maint.drop(columns=['aircraft_id']), use_container_width=True, hide_index=True)

if __name__ == '__main__':
    main()
