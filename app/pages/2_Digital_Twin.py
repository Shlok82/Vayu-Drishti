import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from ml.replay import replay
from ml.config import DEMO_ENGINE_ID, RED_BELOW, AMBER_BELOW, RUL_CLIP, AS_OF, DATA_DIR
from datetime import datetime, timedelta
from ml.alerts import get_spares_status

def main():
    st.title("Digital Twin Replay")
    st.caption(f"Demo as-of date: {AS_OF} (fixed)")
    
    df_master = pd.read_csv(DATA_DIR / 'aircraft_master.csv')
    ac_info = df_master[df_master['engine_ids'].str.contains(str(DEMO_ENGINE_ID))].iloc[0]
    fpd = ac_info['flights_per_day']
    
    st.info(f"**Aircraft {ac_info['aircraft_id']}** (Type: {ac_info['type']}, Flights/day: {fpd}) — engine_1 replaced by held-out engine {DEMO_ENGINE_ID} for replay.")
    
    if 'replay_df' not in st.session_state:
        st.session_state.replay_df = replay(DEMO_ENGINE_ID)
        
    df = st.session_state.replay_df
    max_cycle = int(df['cycle'].max())
    
    c = st.slider("Cycle (Playback)", min_value=1, max_value=max_cycle, value=1, step=1, key="slider")
    history = df[df['cycle'] <= c].copy()
    current_state = history.iloc[-1]
    
    rul = current_state['predicted_rul']
    true_rul = current_state['true_rul']
    risk = current_state['risk_level']
    health = current_state['health_score']
    
    as_of_dt = datetime.strptime(AS_OF, "%Y-%m-%d %H:%M")
    
    # What-if Logic
    st.sidebar.subheader("What-If Analysis")
    extra_hours = st.sidebar.slider("Extra Flight Hours", 0.0, 50.0, 0.0, 1.0)
    extra_cycles = extra_hours / 1.5 # AVG_FLIGHT_HOURS_PER_CYCLE
    sim_rul = max(0, rul - extra_cycles)
    sim_risk = 'red' if sim_rul < RED_BELOW else ('amber' if sim_rul <= AMBER_BELOW else 'green')
    
    metric_cols = st.columns(4)
    metric_cols[0].metric("Current Cycle", int(c))
    
    rul_disp = f">= 125 (model cap)" if sim_rul >= 125 else f"{sim_rul:.1f}"
    metric_cols[1].metric("Predicted RUL", rul_disp, delta=f"-{extra_cycles:.1f} from what-if" if extra_hours > 0 else None, delta_color="inverse")
    
    risk_color = "red" if sim_risk == "red" else ("orange" if sim_risk == "amber" else "green")
    metric_cols[2].markdown(f"### Risk: :{risk_color}[{sim_risk.upper()}]")
    
    days_to_fail = sim_rul / fpd
    fail_date = as_of_dt + timedelta(days=days_to_fail)
    metric_cols[3].metric("Predicted Failure", f"{fail_date.strftime('%Y-%m-%d')}")
    metric_cols[3].caption(f"{days_to_fail:.1f} days to failure")
    
    df_parts = pd.read_csv(DATA_DIR / 'parts_catalog.csv')
    df_spares = pd.read_csv(DATA_DIR / 'spares_inventory.csv')
    df_ws = pd.read_csv(DATA_DIR / 'workshops.csv')
    min_turnaround = df_ws['turnaround_days'].min()
    
    # Spares Logic
    part_row = df_parts[(df_parts['type'] == ac_info['type']) & (df_parts['component'] == 'engine_1')]
    if not part_row.empty:
        eng_part_no = part_row.iloc[0]['part_no']
        eng_lead = part_row.iloc[0]['lead_time_days']
        
        stock_agg = df_spares[df_spares['part_no'] == eng_part_no]['qty_on_hand'].sum()
        reorder_agg = df_spares[df_spares['part_no'] == eng_part_no]['reorder_level'].max()
        if pd.isna(reorder_agg): reorder_agg = 0
        
        status = get_spares_status(days_to_fail, eng_lead, stock_agg, reorder_agg, sim_risk, min_turnaround)
        
        msg = f"**Spares Alert**: Part {eng_part_no} fails in {days_to_fail:.1f} days, stock {stock_agg}, lead time {eng_lead} days, repair {min_turnaround} days. Status: **{status}**"
        
        if status in ["CANNOT ARRIVE IN TIME", "ORDER NOW"]:
            st.error("🚨 " + msg)
        elif status == "SCHEDULE NOW (IN STOCK)":
            st.error("🛠️ " + msg)
        elif status == "WATCH":
            st.warning("⚠️ " + msg)
        else:
            st.success("✅ " + msg)
            
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Sensor Telemetry (Normalized)")
        fig_sens = go.Figure()
        for sens in ['s2', 's3', 's4']:
            baseline = df[sens].iloc[:10].mean()
            std = df[sens].std()
            if std > 0:
                y_norm = (history[sens] - baseline) / std
                fig_sens.add_trace(go.Scatter(x=history['cycle'], y=y_norm, mode='lines', name=sens.split('_')[0]))
        fig_sens.update_layout(xaxis_title="Cycle", yaxis_title="Z-Score Deviation", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_sens, use_container_width=True)
        
    with c2:
        st.subheader("RUL Trajectory")
        fig_rul = go.Figure()
        fig_rul.add_trace(go.Scatter(x=history['cycle'], y=history['predicted_rul'], mode='lines', name='Predicted RUL'))
        
        clipped_true_rul = history['true_rul'].clip(upper=125)
        fig_rul.add_trace(go.Scatter(x=history['cycle'], y=clipped_true_rul, mode='lines', line=dict(dash='dash'), name='Ground Truth (capped)'))
        
        fig_rul.add_hline(y=AMBER_BELOW, line_dash="dot", line_color="orange", annotation_text="Amber Threshold")
        fig_rul.add_hline(y=RED_BELOW, line_dash="dot", line_color="red", annotation_text="Red Threshold")
        
        fig_rul.update_layout(
            xaxis=dict(title="Cycle", range=[1, max_cycle]),
            yaxis=dict(title="RUL Cycles", range=[0, 135]),
            margin=dict(l=0, r=0, t=30, b=0)
        )
        st.plotly_chart(fig_rul, use_container_width=True)

if __name__ == '__main__':
    main()
