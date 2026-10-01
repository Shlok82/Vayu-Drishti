import streamlit as st
import pandas as pd
import os
import sys
import plotly.express as px

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from ml.planner import get_recommendations
from ml.alerts import generate_alerts

def main():
    st.title("Maintenance Planner")
    
    parts_path = os.path.join('data', 'parts_catalog.csv')
    spares_path = os.path.join('data', 'spares_inventory.csv')
    master_path = os.path.join('data', 'aircraft_master.csv')
    preds_path = os.path.join('data', 'predictions.csv')
    ws_path = os.path.join('data', 'workshops.csv')
    sched_path = os.path.join('data', 'flight_schedule.csv')
    
    if not all(os.path.exists(p) for p in [parts_path, spares_path, master_path, preds_path, ws_path, sched_path]):
        st.error("Missing data files. Run make_synthetic.py and make_predictions.py first.")
        return
        
    df_parts = pd.read_csv(parts_path)
    df_spares = pd.read_csv(spares_path)
    df_master = pd.read_csv(master_path)
    df_preds = pd.read_csv(preds_path)
    df_ws = pd.read_csv(ws_path)
    df_sched = pd.read_csv(sched_path)
    
    alerts_df = generate_alerts(df_preds, df_master, df_parts, df_spares)
    
    if alerts_df.empty:
        st.success("No maintenance recommended: all fleet components are healthy (GREEN).")
        return
        
    st.subheader("Recommended Maintenance Slots")
    recs = get_recommendations(alerts_df, df_ws, df_sched, df_master)
    
    # Highlight infeasible or flagged
    def color_flags(row):
        return ['background-color: #ffcccc' if row['flag'] != "" else ''] * len(row)
        
    st.dataframe(recs.style.apply(color_flags, axis=1), use_container_width=True, hide_index=True)
    
    st.write("---")
    st.subheader("Workshop Schedule (Gantt)")
    
    # Filter only feasible for Gantt
    feasible = recs[recs['flag'] == ""]
    if feasible.empty:
        st.info("No feasible slots planned.")
        return
        
    feasible = feasible.copy()
    feasible['slot_start'] = pd.to_datetime(feasible['slot_start'])
    feasible['slot_end'] = pd.to_datetime(feasible['slot_end'])
    
    fig = px.timeline(feasible, x_start="slot_start", x_end="slot_end", y="workshop_id", color="risk",
                      hover_data=['aircraft_id', 'component', 'missions_affected'],
                      color_discrete_map={'red': 'red', 'amber': 'orange'})
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
if __name__ == '__main__':
    main()
