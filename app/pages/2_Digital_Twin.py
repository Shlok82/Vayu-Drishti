import streamlit as st
import pandas as pd
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from ml.config import DEMO_ENGINE_ID, AS_OF, DEMO_AIRCRAFT_ID
from ml.replay import replay
from datetime import datetime, timedelta

st.set_page_config(page_title="Digital Twin - Vayu Drishti", layout="wide")

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
        speed = st.selectbox("Playback Speed", options=[1, 2, 5, 10], index=1)
        
    with col3:
        if st.button("Reset"):
            st.session_state.current_cycle = 1
            st.session_state.playing = False
            
    # Slider
    cycle_sel = st.slider("Scrub Cycle", min_value=1, max_value=max_cycles, value=st.session_state.current_cycle, key="slider")
    
    # Sync states
    if st.session_state.playing:
        st.session_state.current_cycle = cycle_sel
    else:
        st.session_state.current_cycle = cycle_sel
        
    # Get current state
    current_row = df.iloc[st.session_state.current_cycle - 1]
    
    st.write("---")
    
    master = pd.read_csv('data/aircraft_master.csv')
    ac_info = master[master['aircraft_id'] == DEMO_AIRCRAFT_ID].iloc[0]
    fpd = ac_info['flights_per_day']
    
    as_of_dt = datetime.strptime(AS_OF, "%Y-%m-%d %H:%M")
    days_to_fail = current_row['predicted_rul'] / fpd
    fail_date = as_of_dt + timedelta(days=days_to_fail)
    
    # Display metrics
    risk = current_row['risk_level']
    color = "red" if risk == "red" else "orange" if risk == "amber" else "green"
    
    metric_cols = st.columns(4)
    metric_cols[0].metric("Current Cycle", current_row['cycle'])
    metric_cols[1].markdown(f"**Predicted RUL:** <span style='color:{color}; font-size:1.5em'>{current_row['predicted_rul']:.1f}</span>", unsafe_allow_html=True)
    metric_cols[2].metric("Health Score", f"{current_row['health_score']:.1f}/100")
    metric_cols[3].metric("Predicted Failure", fail_date.strftime("%Y-%m-%d"))
    
    # Spares Check Live
    parts_df = pd.read_csv('data/parts_catalog.csv')
    spares_df = pd.read_csv('data/spares_inventory.csv')
    
    # get part for engine_1 and type
    ac_type = ac_info['type']
    eng_part_no = parts_df[(parts_df['component'] == 'engine_1') & (parts_df['type'] == ac_type)]['part_no'].values[0]
    eng_lead = parts_df[(parts_df['component'] == 'engine_1') & (parts_df['type'] == ac_type)]['lead_time_days'].values[0]
    eng_stock = spares_df[spares_df['part_no'] == eng_part_no]['qty_on_hand'].sum()
    eng_reorder = spares_df[spares_df['part_no'] == eng_part_no]['reorder_level'].max()
    
    if risk in ['red', 'amber']:
        if eng_stock <= 0 or (eng_stock <= eng_reorder and eng_lead >= days_to_fail):
            status = "ORDER NOW"
            st.error(f"⚠️ **Spares Alert**: {eng_part_no} fails in {int(days_to_fail)} days, stock {eng_stock}, lead time {eng_lead} days. **ORDER NOW**")
        elif eng_stock > eng_reorder:
            status = "OK"
            st.success(f"✅ **Spares Alert**: {eng_part_no} fails in {int(days_to_fail)} days. Stock {eng_stock} (OK).")
        else:
            status = "WATCH"
            st.warning(f"⚠️ **Spares Alert**: {eng_part_no} fails in {int(days_to_fail)} days. Stock {eng_stock} (WATCH).")
    else:
        st.info(f"ℹ️ **Spares Status**: Component is GREEN. No action needed.")

    st.write("---")
    st.subheader("Live Sensor Values")
    # Show last 10 cycles for live context
    start_idx = max(0, st.session_state.current_cycle - 10)
    history = df.iloc[start_idx:st.session_state.current_cycle]
    
    # Use standard line chart for a few sensors
    st.line_chart(history.set_index('cycle')[['s2', 's11', 's14']])
    
    # Play loop
    if st.session_state.playing:
        if st.session_state.current_cycle < max_cycles:
            time.sleep(1.0 / speed)
            st.session_state.current_cycle += 1
            st.rerun()
        else:
            st.session_state.playing = False

if __name__ == '__main__':
    main()
