import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Vayu Drishti", layout="wide")

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
    st.warning("Demo uses NASA C-MAPSS turbofan simulation data plus synthetic maintenance records. Not real fleet data.")
    
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
    st.write(f"**🟢 {green_count} Green** | **🟠 {amber_count} Amber** | **🔴 {red_count} Red**")
    
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
    st.dataframe(styled_preds, use_container_width=True, hide_index=True)
    st.caption("Predicted RUL is capped at 125 cycles; green values mean at least that many cycles remain. Failure date assumes flights per day from the aircraft record.")

if __name__ == '__main__':
    main()
