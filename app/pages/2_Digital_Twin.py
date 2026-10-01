import streamlit as st
import pandas as pd
import os
import sys
import time
import plotly.graph_objects as go

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from ml.config import DEMO_ENGINE_ID, AS_OF, DEMO_AIRCRAFT_ID, RED_BELOW, AMBER_BELOW
from ml.replay import replay
from datetime import datetime, timedelta

def main():
    st.title("Digital Twin - Live Health State")
    st.caption(f"Aircraft {DEMO_AIRCRAFT_ID}, engine_1 replaced by held-out engine {DEMO_ENGINE_ID} for the replay.")
    
    if DEMO_ENGINE_ID is None:
        st.error("DEMO_ENGINE_ID is not set in config.")
        return
        
    if 'replay_df' not in st.session_state:
        with st.spinner("Loading replay data..."):
            st.session_state.replay_df = replay(DEMO_ENGINE_ID)
            
    df = st.session_state.replay_df
    max_cycles = len(df)
    
    if 'current_cycle' not in st.session_state:
        st.session_state.current_cycle = 1
        
    if 'playing' not in st.session_state:
        st.session_state.playing = False
        
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Play / Pause Simulation"):
            st.session_state.playing = not st.session_state.playing
    with col2:
        speed = st.selectbox("Playback Speed", options=[1, 2, 5, 10, 50], index=1)
    with col3:
        if st.button("Reset"):
            st.session_state.current_cycle = 1
            st.session_state.playing = False
            
    cycle_sel = st.slider("Scrub Cycle", min_value=1, max_value=max_cycles, value=st.session_state.current_cycle, key="slider")
    
    if st.session_state.playing:
        st.session_state.current_cycle = cycle_sel
    else:
        st.session_state.current_cycle = cycle_sel
        
    current_row = df.iloc[st.session_state.current_cycle - 1]
    
    st.write("---")
    master = pd.read_csv('data/aircraft_master.csv')
    ac_info = master[master['aircraft_id'] == DEMO_AIRCRAFT_ID].iloc[0]
    fpd = ac_info['flights_per_day']
    
    as_of_dt = datetime.strptime(AS_OF, "%Y-%m-%d %H:%M")
    sim_now = as_of_dt + timedelta(days=(st.session_state.current_cycle - 1) / fpd)
    days_to_fail = current_row['predicted_rul'] / fpd
    fail_date = sim_now + timedelta(days=days_to_fail)
    
    risk = current_row['risk_level']
    color = "red" if risk == "red" else "orange" if risk == "amber" else "green"
    badge = f"<span style='background-color:{color}; color:white; padding: 2px 6px; border-radius: 4px; font-size:0.6em; vertical-align: top;'>{risk.upper()}</span>"
    
    metric_cols = st.columns(4)
    metric_cols[0].metric("Simulated Clock", sim_now.strftime("%Y-%m-%d %H:%M"))
    metric_cols[1].markdown(f"**Predicted RUL:** <span style='color:{color}; font-size:1.5em'>{current_row['predicted_rul']:.1f}</span> {badge}", unsafe_allow_html=True)
    metric_cols[2].metric("Health Index (RUL-scaled)", f"{current_row['health_score']:.1f}/100")
    metric_cols[3].metric("Predicted Failure", f"{fail_date.strftime('%Y-%m-%d')} ({days_to_fail:.1f} days)")
    
    # Spares Check Live
    parts_df = pd.read_csv('data/parts_catalog.csv')
    spares_df = pd.read_csv('data/spares_inventory.csv')
    ac_type = ac_info['type']
    
    eng_part_row = parts_df[(parts_df['component'] == 'engine_1') & (parts_df['type'] == ac_type)]
    if not eng_part_row.empty:
        eng_part_no = eng_part_row['part_no'].values[0]
        eng_lead = eng_part_row['lead_time_days'].values[0]
        eng_stock = spares_df[spares_df['part_no'] == eng_part_no]['qty_on_hand'].sum()
        eng_reorder = spares_df[spares_df['part_no'] == eng_part_no]['reorder_level'].max()
        
        if risk in ['red', 'amber']:
            if eng_stock <= 0 and eng_lead > days_to_fail:
                st.error(f"🚨 **Spares Alert**: {eng_part_no} fails in {int(days_to_fail)} days, stock {eng_stock}, lead time {eng_lead} days. **CANNOT ARRIVE IN TIME**")
            elif eng_stock <= 0 or (eng_stock <= eng_reorder and eng_lead >= days_to_fail):
                st.error(f"⚠️ **Spares Alert**: {eng_part_no} fails in {int(days_to_fail)} days, stock {eng_stock}, lead time {eng_lead} days. **ORDER NOW**")
            elif eng_stock > eng_reorder:
                st.success(f"✅ **Spares Alert**: {eng_part_no} fails in {int(days_to_fail)} days. Stock {eng_stock} (OK).")
            else:
                st.warning(f"⚠️ **Spares Alert**: {eng_part_no} fails in {int(days_to_fail)} days. Stock {eng_stock} (WATCH).")
        else:
            st.info(f"ℹ️ **Spares Status**: Component is GREEN. No action needed.")

    # What-if 
    st.write("---")
    with st.expander("What-If Analysis (Extra Flight Hours)"):
        extra_hours = st.number_input("Add flight hours", value=50)
        avg_flight_hours_per_cycle = 1.5
        extra_cycles = int(extra_hours / avg_flight_hours_per_cycle)
        
        # look forward in the trajectory
        future_cycle = st.session_state.current_cycle + extra_cycles
        if future_cycle > max_cycles:
            future_cycle = max_cycles
            
        future_row = df.iloc[future_cycle - 1]
        st.write(f"After +{extra_hours} hours (+{extra_cycles} cycles) -> Cycle {future_cycle}")
        st.write(f"Predicted RUL will be **{future_row['predicted_rul']:.1f}** (Risk: **{future_row['risk_level'].upper()}**)")

    st.write("---")
    colA, colB = st.columns(2)
    
    with colA:
        st.subheader("Live Sensor Values (Normalized)")
        history = df.iloc[:st.session_state.current_cycle].copy()
        
        # Normalize to first 10 cycles
        baseline = df.iloc[:10]
        sensors = ['s2', 's11', 's14']
        
        fig_sens = go.Figure()
        for s in sensors:
            mean = baseline[s].mean()
            std = baseline[s].std() if baseline[s].std() != 0 else 1.0
            norm_vals = (history[s] - mean) / std
            fig_sens.add_trace(go.Scatter(x=history['cycle'], y=norm_vals, mode='lines', name=s))
            
        # Visible window: last 50 cycles
        x_min = max(1, st.session_state.current_cycle - 50)
        x_max = max(50, st.session_state.current_cycle)
        fig_sens.update_layout(xaxis=dict(range=[x_min, x_max]), margin=dict(l=0, r=0, t=30, b=0), yaxis_title="Z-Score (vs cycles 1-10)")
        st.plotly_chart(fig_sens, use_container_width=True)
        
    with colB:
        st.subheader("RUL Prediction Trajectory")
        history = df.iloc[:st.session_state.current_cycle]
        fig_rul = go.Figure()
        fig_rul.add_trace(go.Scatter(x=history['cycle'], y=history['predicted_rul'], mode='lines', name='Predicted RUL'))
        fig_rul.add_trace(go.Scatter(x=history['cycle'], y=history['true_rul'], mode='lines', line=dict(dash='dash'), name='Ground Truth (Eval)'))
        fig_rul.add_hline(y=AMBER_BELOW, line_dash="dot", line_color="orange", annotation_text="AMBER")
        fig_rul.add_hline(y=RED_BELOW, line_dash="dot", line_color="red", annotation_text="RED")
        fig_rul.update_layout(xaxis_title="Cycle", yaxis_title="Remaining Useful Life", margin=dict(l=0, r=0, t=30, b=0), xaxis=dict(range=[1, max_cycles]))
        st.plotly_chart(fig_rul, use_container_width=True)
    
    if st.session_state.playing:
        if st.session_state.current_cycle < max_cycles:
            time.sleep(1.0 / speed)
            st.session_state.current_cycle += 1
            st.rerun()
        else:
            st.session_state.playing = False

if __name__ == '__main__':
    main()
