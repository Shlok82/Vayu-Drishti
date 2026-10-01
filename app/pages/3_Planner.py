import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from ml.config import DATA_DIR, AS_OF
from ml.alerts import generate_alerts
from ml.planner import get_recommendations

def main():
    st.title("Maintenance Planner")
    st.caption(f"Demo as-of date: {AS_OF} (fixed)")
    
    df_preds = pd.read_csv(DATA_DIR / 'predictions.csv')
    df_master = pd.read_csv(DATA_DIR / 'aircraft_master.csv')
    df_parts = pd.read_csv(DATA_DIR / 'parts_catalog.csv')
    df_spares = pd.read_csv(DATA_DIR / 'spares_inventory.csv')
    df_ws = pd.read_csv(DATA_DIR / 'workshops.csv')
    df_sched = pd.read_csv(DATA_DIR / 'flight_schedule.csv')
    
    alerts_df = generate_alerts(df_preds, df_master, df_parts, df_spares, df_ws)
    
    if alerts_df.empty:
        st.success("No critical maintenance required.")
        return
        
    recs = get_recommendations(alerts_df, df_ws, df_sched, df_master)
    if recs.empty:
        st.success("No recommendations generated.")
        return
        
    # Summary
    total_jobs = len(recs)
    feasible = len(recs[recs['flag'] == ''])
    infeasible_df = recs[recs['flag'] != '']
    infeasible_count = len(infeasible_df)
    
    st.subheader("Plan Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs", total_jobs)
    c2.metric("Feasible Jobs", feasible)
    c3.metric("Infeasible / Flagged Jobs", infeasible_count)
    
    if infeasible_count > 0:
        st.warning("Some jobs are flagged and require manual intervention:")
        reasons = infeasible_df['flag'].value_counts()
        for r, count in reasons.items():
            st.write(f"- **{r}**: {count} jobs")
            
    st.write("---")
    st.subheader("Schedule Gantt Chart")
    
    # Gantt Chart Construction
    fig = go.Figure()
    
    all_ws = sorted(df_ws['workshop_id'].tolist(), reverse=True)
    
    for i, row in recs.iterrows():
        ws = row['workshop_id']
        start = row['slot_start']
        end = row['slot_end']
        flag = row['flag']
        ac = row['aircraft_id']
        fail_date = row['predicted_failure']
        
        # Risk level from alerts_df
        risk = alerts_df[(alerts_df['aircraft_id'] == ac) & (alerts_df['component'] == row['component'])]['risk_level'].iloc[0]
        
        is_infeasible = flag != ""
        color = 'lightgrey' if is_infeasible else ('red' if risk == 'red' else 'orange')
        line = dict(color='black', width=1) if is_infeasible else dict(width=0)
        pattern = dict(shape='/') if is_infeasible else None
        
        hover_text = f"Aircraft: {ac}<br>Risk: {risk}<br>Flag: {flag if flag else 'None'}<br>Missions Affected: {row['missions_affected_count']}"
        
        # Draw bar
        fig.add_trace(go.Bar(
            base=start,
            x=[(datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days * 86400000],
            y=[ws],
            orientation='h',
            marker_color=color,
            marker_line=line,
            marker_pattern=pattern,
            text=f"{ac} {'(INFEASIBLE)' if is_infeasible else ''}",
            textposition='inside',
            hoverinfo='text',
            hovertext=hover_text,
            showlegend=False
        ))
        
        # Draw predicted failure marker
        fig.add_trace(go.Scatter(
            x=[fail_date], y=[ws],
            mode='markers', marker=dict(symbol='x', color='black', size=8),
            name='Predicted Failure', showlegend=False, hoverinfo='skip'
        ))
        
    as_of_d = datetime.strptime(AS_OF, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d")
    fig.add_vline(x=datetime.strptime(as_of_d, "%Y-%m-%d").timestamp() * 1000, line_width=2, line_dash="dash", line_color="black")
    
    # X range
    latest_end = max(datetime.strptime(r['slot_end'], "%Y-%m-%d") for _, r in recs.iterrows())
    fig.update_layout(
        barmode='overlay',
        yaxis=dict(categoryarray=all_ws, type='category'),
        xaxis=dict(
            type='date',
            range=[as_of_d, (latest_end + timedelta(days=7)).strftime("%Y-%m-%d")]
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        height=300 + 40 * len(all_ws)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.write("---")
    st.subheader("Job Details")
    
    # Format table
    disp_df = recs[['aircraft_id', 'component', 'workshop_id', 'slot_start', 'slot_end', 'missions_affected_count', 'mission_cost', 'flag', 'recommended_action']].copy()
    disp_df.columns = ['Aircraft', 'Component', 'Workshop', 'Start', 'End', 'Missions Affected', 'Cost', 'Flag', 'Recommendation']
    
    st.dataframe(disp_df, use_container_width=True, hide_index=True)
    
    with st.expander("View Full Mission Conflict Details"):
        conflict_list = []
        for _, r in recs.iterrows():
            if len(r['mission_details']) > 0:
                for m in r['mission_details']:
                    conflict_list.append({
                        'Aircraft': r['aircraft_id'],
                        'Date': m['date'],
                        'Mission ID': m['id'],
                        'Priority': m['priority']
                    })
        if conflict_list:
            st.dataframe(pd.DataFrame(conflict_list), hide_index=True)
        else:
            st.write("No specific mission conflicts.")

if __name__ == '__main__':
    main()
