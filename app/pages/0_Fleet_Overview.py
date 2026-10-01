import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import streamlit as st
import pandas as pd
import os
import sys

from ml.config import DEMO_AIRCRAFT_ID, DEMO_ENGINE_ID

@st.cache_data
def load_data():
    master_path = os.path.join('data', 'aircraft_master.csv')
    preds_path = os.path.join('data', 'predictions.csv')
    
    if os.path.exists(master_path) and os.path.exists(preds_path):
        df_master = pd.read_csv(master_path)
        df_preds = pd.read_csv(preds_path)
        return df_master, df_preds
    return pd.DataFrame(), pd.DataFrame()

def main():
    st.title("Vayu Drishti - Fleet Overview")
    st.warning(f"Demo uses NASA C-MAPSS turbofan simulation data plus synthetic maintenance records. Not real fleet data. Aircraft **{DEMO_AIRCRAFT_ID}** is the demo aircraft whose engine_1 is replaced by held-out engine **{DEMO_ENGINE_ID}** in the twin.")
    
    df_master, df_preds = load_data()
    
    if df_master.empty or df_preds.empty:
        st.error("Data not found. Please run the ML scripts to generate synthetic data.")
        return
        
    # Format and sort table
    df_preds['predicted_rul_cycles'] = df_preds['predicted_rul_cycles'].round(1)
    df_preds['health_score'] = df_preds['health_score'].round(1)
    df_preds['predicted_failure_date'] = pd.to_datetime(df_preds['predicted_failure_date']).dt.date
    
    risk_order = {'red': 0, 'amber': 1, 'green': 2}
    df_preds['_risk_sort'] = df_preds['risk_level'].map(risk_order)
    df_preds = df_preds.sort_values(['_risk_sort', 'predicted_rul_cycles'], ascending=[True, True])
    df_preds = df_preds.drop(columns=['_risk_sort', 'top_reasons'], errors='ignore')
    
    # Calculate fleet readiness
    red_components = df_preds[df_preds['risk_level'] == 'red']
    unready_aircraft = red_components['aircraft_id'].unique()
    total_aircraft = len(df_master)
    ready_count = total_aircraft - len(unready_aircraft)
    
    ac_risks = []
    ac_cards_info = []
    
    for _, row in df_master.iterrows():
        ac_id = row['aircraft_id']
        ac_preds = df_preds[df_preds['aircraft_id'] == ac_id]
        risks = ac_preds['risk_level'].tolist()
        
        if 'red' in risks:
            overall_risk = 'red'
        elif 'amber' in risks:
            overall_risk = 'amber'
        else:
            overall_risk = 'green'
            
        ac_risks.append(overall_risk)
        worst_comp = ac_preds.iloc[0] # Already sorted by severity and RUL!
        ac_cards_info.append({
            'ac_id': ac_id,
            'risk': overall_risk,
            'rul': worst_comp['predicted_rul_cycles'],
            'fail_date': worst_comp['predicted_failure_date'],
            'sort_key': risk_order[overall_risk]
        })
        
    green_count = ac_risks.count('green')
    amber_count = ac_risks.count('amber')
    red_count = ac_risks.count('red')
    
    st.subheader(f"Fleet Status: {ready_count} of {total_aircraft} ready")
    st.caption("Ready = no red-risk component. Risk thresholds: red < 30 cycles, amber 30 to 80, green > 80.")
    st.write(f"**GREEN {green_count} Green** | **AMBER {amber_count} Amber** | **RED {red_count} Red**")
    
    ac_cards_info.sort(key=lambda x: (x['sort_key'], x['rul']))
    
    cols = st.columns(4)
    for idx, info in enumerate(ac_cards_info):
        color = "#ffcccc" if info['risk'] == 'red' else "#fff3cd" if info['risk'] == 'amber' else "#d4edda"
        with cols[idx % 4]:
            st.markdown(
                f"""
                <div style="background-color: {color}; padding: 15px; border-radius: 5px; margin-bottom: 10px; border: 1px solid #ccc;">
                    <h4 style="margin-top: 0; color: #333;">{info['ac_id']}</h4>
                    <p style="margin: 0; color: #555; font-size: 0.9em;">
                        Risk: <strong>{info['risk'].upper()}</strong><br/>
                        Min RUL: {info['rul']} cycles<br/>
                        Predicted Failure: {info['fail_date']}
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.write("---")
    st.subheader("Detailed Component Predictions")
    
    def color_risk(val):
        color = 'red' if val == 'red' else 'orange' if val == 'amber' else 'green'
        return f'color: {color}; font-weight: bold'
        
    styled_preds = df_preds.style.map(color_risk, subset=['risk_level'])
    st.dataframe(styled_preds, width='stretch', hide_index=True)
    st.caption("Predicted RUL is capped at 125 cycles; green values mean at least that many cycles remain. Failure date assumes flights per day from the aircraft record.")

    st.write("---")
    st.subheader("Spares-Aware Alerts")
    
    parts_path = os.path.join('data', 'parts_catalog.csv')
    spares_path = os.path.join('data', 'spares_inventory.csv')
    if os.path.exists(parts_path) and os.path.exists(spares_path):
        df_parts = pd.read_csv(parts_path)
        df_spares = pd.read_csv(spares_path)
        
        from ml.alerts import generate_alerts
        alerts_df = generate_alerts(df_preds, df_master, df_parts, df_spares)
        
        if not alerts_df.empty:
            counts = alerts_df['status'].value_counts()
            count_str = " | ".join([f"{k}: {v}" for k, v in counts.items()])
            st.write(f"**Alert Counts:** {count_str}")
            
            for _, row in alerts_df.iterrows():
                if row['status'] == 'CANNOT ARRIVE IN TIME':
                    st.error(f"[CRITICAL] **{row['aircraft_id']} ({row['component']})**: {row['alert_message']}")
                elif row['status'] == 'ORDER NOW':
                    st.error(f"[CRITICAL] **{row['aircraft_id']} ({row['component']})**: {row['alert_message']}")
                elif row['status'] == 'WATCH':
                    st.warning(f"[WARN] **{row['aircraft_id']} ({row['component']})**: {row['alert_message']}")
            
            st.dataframe(alerts_df.drop(columns=['alert_message']), width='stretch', hide_index=True)
        else:
            st.success("No amber or red components require spares checking currently.")
            
    st.write("---")
    st.subheader("Availability Forecast (Next 30 Days)")
    ws_path = os.path.join('data', 'workshops.csv')
    sched_path = os.path.join('data', 'flight_schedule.csv')
    
    if os.path.exists(ws_path) and os.path.exists(sched_path) and 'alerts_df' in locals() and not alerts_df.empty:
        from ml.planner import get_recommendations
        from ml.forecast import simulate_forecast
        import plotly.graph_objects as go
        
        df_ws = pd.read_csv(ws_path)
        df_sched = pd.read_csv(sched_path)
        recs_df = get_recommendations(alerts_df, df_ws, df_sched, df_master)
        
        forecast_df = simulate_forecast(df_master, df_preds, recs_df, days=30)
        
        mean_plan = forecast_df['Plan'].mean()
        mean_no_action = forecast_df['No Action'].mean()
        
        st.write(f"**Headline:** Next 30 days: {mean_plan:.1f} of 24 ready on average (plan) vs {mean_no_action:.1f} (no action)")
        st.caption("Simulation: Ready = not in a workshop AND no red-risk component. Risk evolves daily based on flight schedule. This is a deterministic simulation with chosen parameters.")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=forecast_df['Date'], y=forecast_df['Plan'], mode='lines+markers', name='Follow Planner Schedule'))
        fig.add_trace(go.Scatter(x=forecast_df['Date'], y=forecast_df['No Action'], mode='lines+markers', name='No Action (Reactive)', line=dict(dash='dash', color='red')))
        fig.update_layout(yaxis_title="Ready Aircraft", yaxis=dict(range=[0, 24]), margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, width='stretch')
    elif 'alerts_df' in locals() and alerts_df.empty:
        st.info("Fleet is perfectly healthy; forecast is 24/24 ready.")
            
if __name__ == '__main__':
    main()




