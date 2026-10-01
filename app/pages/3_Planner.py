import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
import streamlit as st
import pandas as pd
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
    
    # Define groups
    infeasible_mask = recs['flag'].isin(['PART_ARRIVES_AFTER_FAILURE', 'REPAIR_ENDS_AFTER_FAILURE'])
    infeasible_count = infeasible_mask.sum()
    
    conflict_mask = (~infeasible_mask) & ((recs['flag'] == 'HIGH_PRIORITY_CONFLICT') | (recs['mission_cost'] > 0))
    conflict_count = conflict_mask.sum()
    
    feasible_count = total_jobs - infeasible_count - conflict_count
    
    st.subheader("Plan Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Jobs", total_jobs)
    c2.metric("Feasible", feasible_count)
    c3.metric("Feasible w/ Conflicts", conflict_count)
    c4.metric("Infeasible", infeasible_count)
    
    if infeasible_count > 0 or (recs['flag'] == 'HIGH_PRIORITY_CONFLICT').sum() > 0:
        st.warning("Some jobs are flagged and require manual intervention:")
        reasons = recs[recs['flag'] != '']['flag'].value_counts()
        for r, count in reasons.items():
            st.write(f"- **{r}**: {count} jobs")
            
    st.write("---")
    st.subheader("Schedule Gantt Chart")
    
    # Gantt Chart Construction
    fig = go.Figure()
    
    # Collect all unique lanes to order them
    all_lanes = sorted(recs['lane_id'].unique().tolist(), reverse=True)
    
    added_fail_legend = False
    
    for i, row in recs.iterrows():
        lane = row['lane_id']
        start = row['slot_start']
        end = row['slot_end']
        flag = row['flag']
        ac = row['aircraft_id']
        fail_date = row['predicted_failure']
        
        # Risk level from alerts_df
        risk = alerts_df[(alerts_df['aircraft_id'] == ac) & (alerts_df['component'] == row['component'])]['risk_level'].iloc[0]
        
        is_infeasible = flag in ['PART_ARRIVES_AFTER_FAILURE', 'REPAIR_ENDS_AFTER_FAILURE']
        color = 'lightgrey' if is_infeasible else ('red' if risk == 'red' else 'orange')
        line = dict(color='black', width=1) if is_infeasible else dict(width=0)
        pattern = dict(shape='/') if is_infeasible else None
        
        hover_text = f"Aircraft: {ac}<br>Risk: {risk}<br>Flag: {flag if flag else 'None'}<br>Missions Affected: {row['missions_affected_count']}"
        
        # Draw bar
        duration_ms = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days * 86400000
        fig.add_trace(go.Bar(
            base=start,
            x=[duration_ms],
            y=[lane],
            orientation='h',
            marker_color=color,
            marker_line=line,
            marker_pattern=pattern,
            text=f"{ac} {'(INFEASIBLE)' if is_infeasible else ''}",
            textposition='inside',
            textfont=dict(color='black' if is_infeasible else 'white'),
            hoverinfo='text',
            hovertext=hover_text,
            showlegend=False
        ))
        
        # Draw predicted failure marker as a thin vertical line on the lane
        fig.add_trace(go.Scatter(
            x=[fail_date, fail_date],
            y=[lane, lane],
            mode='markers',
            marker=dict(symbol='line-ns', color='black', size=15, line=dict(width=2, color='black')),
            name='Predicted Failure',
            showlegend=not added_fail_legend,
            hoverinfo='skip'
        ))
        added_fail_legend = True
        
    as_of_d = datetime.strptime(AS_OF, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d")
    fig.add_vline(x=datetime.strptime(as_of_d, "%Y-%m-%d").timestamp() * 1000, line_width=2, line_dash="dash", line_color="black")
    
    # X range
    latest_end = max(datetime.strptime(r['slot_end'], "%Y-%m-%d") for _, r in recs.iterrows())
    fig.update_layout(
        barmode='overlay',
        yaxis=dict(categoryarray=all_lanes, type='category'),
        xaxis=dict(
            type='date',
            range=[as_of_d, (latest_end + timedelta(days=7)).strftime("%Y-%m-%d")]
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        height=300 + 40 * len(all_lanes),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, width='stretch')
    
    st.write("---")
    st.subheader("Job Details")
    
    # Format table
    disp_df = recs[['aircraft_id', 'component', 'lane_id', 'slot_start', 'slot_end', 'missions_affected_count', 'mission_cost', 'flag', 'recommended_action']].copy()
    disp_df.columns = ['Aircraft', 'Component', 'Lane', 'Start', 'End', 'Missions Affected', 'Cost', 'Flag', 'Recommendation']
    
    st.dataframe(disp_df, width='stretch', hide_index=True)
    
    with st.expander("View Full Mission Conflict Details"):
        conflict_list = []
        for _, r in recs.iterrows():
            if isinstance(r['mission_details'], list) and len(r['mission_details']) > 0:
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
