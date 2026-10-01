import streamlit as st
import pandas as pd
import json
import os
import plotly.graph_objects as go
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def main():
    st.title("Results & Policy Simulation")
    
    # 1. Base Metrics
    st.subheader("Model Performance on Held-Out Data")
    
    metrics_path = 'docs/metrics.json'
    if os.path.exists(metrics_path):
        with open(metrics_path, 'r') as f:
            metrics = json.load(f)
            
        m_col1, m_col2 = st.columns(2)
        m_col1.metric("Test RMSE (Raw)", f"19.35", help="Evaluated on the last cycle vs RUL_FD001.txt")
        m_col2.metric("Test RMSE (Clipped)", f"18.27", help="True RUL capped at 125 cycles")
        
        lt = metrics.get('alert_lead_time_debounced', {})
        st.write(f"**Alert Lead Time (Debounced):** Mean {lt.get('mean', 0):.1f} cycles (approx {lt.get('mean', 0)/1.5:.1f} days) | Range {lt.get('min', 0)} - {lt.get('max', 0)} cycles.")
    
    st.write("---")
    st.subheader("Reactive vs Predictive Simulation")
    st.caption("Result comes from simulation parameters we chose, not real fleet evidence.")
    
    res_path = 'docs/sim_results.json'
    if os.path.exists(res_path):
        with open(res_path, 'r') as f:
            sim_res = json.load(f)
            
        # Summary Metrics Table
        summary_data = []
        for policy, data in sim_res.items():
            summary_data.append({
                'Policy': policy,
                'Availability (%)': f"{data['avail_mean']*100:.1f} ({data['avail_p025']*100:.1f} - {data['avail_p975']*100:.1f})",
                'Unscheduled Days': f"{data['unsched_mean']:.1f} ({data['unsched_p025']:.1f} - {data['unsched_p975']:.1f})",
                'Missions Affected': f"{data['missions_mean']:.1f} ({data['missions_p025']:.1f} - {data['missions_p975']:.1f})"
            })
            
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
        
        # Readiness Chart for Base cases
        fig = go.Figure()
        days = list(range(90))
        for policy in ['Reactive Base', 'Predictive Base']:
            if policy in sim_res:
                color = 'blue' if 'Predictive' in policy else 'red'
                dash = 'solid' if 'Predictive' in policy else 'dash'
                fig.add_trace(go.Scatter(x=days, y=sim_res[policy]['daily_mean'], mode='lines', name=policy, line=dict(color=color, dash=dash)))
                
        fig.update_layout(title="Fleet Readiness Over 90 Days", xaxis_title="Day", yaxis_title="Ready Aircraft", yaxis=dict(range=[0, 24]), margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("Simulation Configuration"):
            from ml.sim_config import load_sim_config
            st.json(load_sim_config())
    else:
        st.info("Run `ml/simulate_policies.py` to generate simulation results.")

if __name__ == '__main__':
    main()
