import streamlit as st
import pandas as pd
import plotly.express as px
import altair as alt
import plotly.graph_objects as go
import plotly.io as pio

# Reset Plotly renderer to prevent duplicate rendering
pio.templates.default = None

st.set_page_config(page_title="Shrimp Farm Dashboard", layout="wide")

# =============================
#1️⃣ LOAD DATA
# =============================
excel_file = "tank_block_consolidated_report_2025-12-17_colored.xlsx"
df = pd.read_excel(excel_file)

# Rename columns
column_mapping = {
    "Date": "Date",
    "Worker Name": "WorkerName",
    "Block": "Block",
    "Tank No.": "Tank",
    "Scheduled Feed (g)": "ScheduledFeed_day_g",
    "Adjusted Feed (g)": "ActualFeed_day_g",
    "Leftover_g": "LeftoverFeed_g",
    "Dead Shrimp Count": "DeadCount_day",
    "Dead Shrimp Weight (g)": "DeadWeight_g",
    "InitialCount": "InitialCount",
    "LiveCount": "LiveCount",
    "Mortality_pct": "Mortality_pct",
    "Water Temperature": "WaterTemperature",
    "Room Temperature": "RoomTemperature",
    "Humidity": "Humidity",
    "Salinity (ppt)": "Salinity",
    "pH Value": "pH"
}
df = df.rename(columns=column_mapping)
df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
df = df.dropna(subset=['Date'])

# =============================
# 2️⃣ SIDEBAR FILTERS
# =============================
st.sidebar.header("Filters")

# --- Block Filter ---
blocks = ["All"] + sorted(df['Block'].dropna().unique())
selected_block = st.sidebar.selectbox("Select Block", blocks)

# --- Tank Filter ---
expected_tanks = ["T3", "T4", "T5"]
if selected_block == "All":
    tanks_available = df['Tank'].dropna().unique().tolist()
else:
    tanks_available = df[df['Block'] == selected_block]['Tank'].dropna().unique().tolist()
for t in expected_tanks:
    if t not in tanks_available:
        tanks_available.append(t)
tanks = ["All"] + tanks_available
selected_tank = st.sidebar.selectbox("Select Tank", tanks)

# --- View Mode ---
view_option = st.sidebar.radio("View Mode", ["Daily", "Weekly", "Monthly"])

# --- Date / Week / Month Selector ---
if view_option == "Daily":
    dates = ["All"] + sorted(df['Date'].dt.date.unique())
    selected_date = st.sidebar.selectbox("Select Date", dates)

elif view_option == "Weekly":
    df['Week_Start'] = df['Date'] - pd.to_timedelta(df['Date'].dt.weekday, unit='d')
    df['Week_End'] = df['Week_Start'] + pd.Timedelta(days=6)

    week_ranges = df[['Week_Start', 'Week_End']].drop_duplicates().sort_values('Week_Start')
    week_options = week_ranges.apply(lambda r: f"{r['Week_Start'].date()} to {r['Week_End'].date()}", axis=1).tolist()
    selected_week = st.sidebar.selectbox("Select Week", week_options)
    week_start, week_end = selected_week.split(" to ")
    week_start = pd.to_datetime(week_start)
    week_end = pd.to_datetime(week_end)

elif view_option == "Monthly":
    df['Month'] = df['Date'].dt.to_period('M')
    month_options = sorted(df['Month'].astype(str).unique())
    selected_month = st.sidebar.selectbox("Select Month", month_options)

# =============================
# 3️⃣ FILTER DATA
# =============================
view_df = df.copy()
if selected_block != "All":
    view_df = view_df[view_df['Block'] == selected_block]
if selected_tank != "All":
    view_df = view_df[view_df['Tank'] == selected_tank]

if view_option == "Daily" and selected_date != "All":
    view_df = view_df[view_df['Date'].dt.date == selected_date]

elif view_option == "Weekly":
    view_df = view_df[(view_df['Date'] >= week_start) & (view_df['Date'] <= week_end)]

elif view_option == "Monthly":
    view_df = view_df[view_df['Month'].astype(str) == selected_month]

# =============================
# 4️⃣ DAILY VIEW
# =============================
if view_option == "Daily":
    st.title("🦐 Shrimp Farm Dashboard (Daily)")

    view_df['ActualFeed_day_kg'] = (view_df['ActualFeed_day_g'] / 1000).round(2)
    view_df['ScheduledFeed_day_kg'] = (view_df['ScheduledFeed_day_g'] / 1000).round(2)
    view_df['LeftoverFeed_g'] = view_df['ScheduledFeed_day_g'] - view_df['ActualFeed_day_g']
    view_df['LeftoverFeed_kg'] = (view_df['LeftoverFeed_g'] / 1000).round(2)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    if not view_df.empty:
        col1.metric("Feed (g)", round(view_df['ActualFeed_day_g'].sum(), 2))
        col2.metric("Feed (kg)", round(view_df['ActualFeed_day_kg'].sum(), 2))
        col3.metric("Leftover Feed (g)", round(view_df['LeftoverFeed_g'].sum(), 2))
        col4.metric("Leftover Feed (kg)", round(view_df['LeftoverFeed_kg'].sum(), 2))
        col5.metric("Mortality %", round(view_df['Mortality_pct'].mean() * 100, 2) if 'Mortality_pct' in view_df.columns else 0)
        col6.metric("DeadCount", int(view_df['DeadCount_day'].sum()))
    else:
        for c in [col1, col2, col3, col4, col5, col6]:
            c.metric("No Data","No Data")

    # Worker performance & compliance
    view_df['DeadWeight_g'] = view_df['DeadWeight_g'].fillna(0)
    view_df['pH_OK'] = view_df['pH'].between(7.6, 8.0)
    view_df['Salinity_OK'] = view_df['Salinity'].between(25, 39)
    worker_summary = (
        view_df.groupby('WorkerName', as_index=False)
        .agg(
            Total_Records=('WorkerName','count'),
            pH_OK=('pH_OK','sum'),
            Salinity_OK=('Salinity_OK','sum'),
            ScheduledFeed_kg=('ScheduledFeed_day_g', lambda x: round(x.sum()/1000,2)),
            ActualFeed_kg=('ActualFeed_day_g', lambda x: round(x.sum()/1000,2)),
            Dead_Count=('DeadCount_day','sum'),
            Dead_Weight_g=('DeadWeight_g','sum')
        )
    )
    worker_summary['pH_%'] = ((worker_summary['pH_OK']/worker_summary['Total_Records'])*100).round(1)
    worker_summary['Salinity_%'] = ((worker_summary['Salinity_OK']/worker_summary['Total_Records'])*100).round(1)
    worker_summary['Leftover_kg'] = (worker_summary['ScheduledFeed_kg'] - worker_summary['ActualFeed_kg']).round(2)

    st.subheader("Worker Performance & Water Quality Compliance (Daily)")
    st.dataframe(worker_summary[['WorkerName','pH_%','Salinity_%','ScheduledFeed_kg','ActualFeed_kg','Leftover_kg','Dead_Count','Dead_Weight_g']], use_container_width=True)

    # ----------------------------
    # Water quality plot
    # ----------------------------
    st.subheader("Water Quality (Salinity & pH)")

    tank_colors = {"T3": "purple", "T4": "darkblue", "T5": "green"}
    metrics = ['Salinity','pH']
    df_plot = view_df.copy()

    if not df_plot.empty:
        df_plot["X_label"] = df_plot["Tank"].astype(str) + " | " + df_plot["Block"].astype(str)
        df_melt = df_plot.melt(
            id_vars=['X_label','Tank','Block','WorkerName'], 
            value_vars=metrics, 
            var_name='Metric', 
            value_name='Value'
        )
        fig = px.line(
            df_melt, 
            x='X_label', 
            y='Value', 
            color='Tank', 
            line_dash='Metric', 
            markers=True,
            color_discrete_map=tank_colors,
            labels={'X_label':'Tank | Block','Value':'Value','Metric':'Parameter'},
            hover_data=['WorkerName','Tank','Block','Metric','Value']
        )
        df_critical_ph = df_melt[(df_melt['Metric'] == 'pH') & ((df_melt['Value'] < 8.0) | (df_melt['Value'] > 8.3))]
        fig.add_trace(go.Scatter(
            x=df_critical_ph['X_label'],
            y=df_critical_ph['Value'],
            mode='markers',
            marker=dict(color='red', size=12, symbol='x'),
            name='Critical pH',
            customdata=df_critical_ph[['WorkerName','Tank','Block','Metric','Value']],
            hovertemplate="Worker: %{customdata[0]}<br>Tank: %{customdata[1]}<br>Block: %{customdata[2]}<br>Parameter: %{customdata[3]}<br>Value: %{customdata[4]}"
        ))
        df_critical_salinity = df_melt[(df_melt['Metric'] == 'Salinity') & ((df_melt['Value'] < 25) | (df_melt['Value'] > 30))]
        fig.add_trace(go.Scatter(
            x=df_critical_salinity['X_label'],
            y=df_critical_salinity['Value'],
            mode='markers',
            marker=dict(color='orange', size=12, symbol='x'),
            name='Critical Salinity',
            customdata=df_critical_salinity[['WorkerName','Tank','Block','Metric','Value']],
            hovertemplate="Worker: %{customdata[0]}<br>Tank: %{customdata[1]}<br>Block: %{customdata[2]}<br>Parameter: %{customdata[3]}<br>Value: %{customdata[4]}"
        ))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No water quality data available.")

    # ----------------------------
    # Feed trends
    # ----------------------------
    st.subheader("Feed Trends")
    df_feed = view_df.melt(
        id_vars=['Tank','Block','WorkerName'], 
        value_vars=['ScheduledFeed_day_g','ActualFeed_day_g'], 
        var_name='Metric', 
        value_name='Value'
    )
    if not df_feed.empty:
        df_feed["X_label"] = df_feed["Tank"].astype(str) + " | " + df_feed["Block"].astype(str)
        fig_feed = px.line(
            df_feed, 
            x='X_label', 
            y='Value', 
            color='Tank', 
            line_dash='Metric', 
            markers=True,
            color_discrete_map=tank_colors,
            labels={'X_label':'Tank | Block','Value':'Feed (g)','Metric':'Parameter'},
            hover_data=['WorkerName', 'Tank', 'Block', 'Value', 'Metric']
        )
        st.plotly_chart(fig_feed, use_container_width=True)
    else:
        st.info("No feed data available.")

    # ----------------------------
    # Mortality Trends
    # ----------------------------
    st.subheader("Mortality Trends")
    df_mort = view_df[['Tank','Block','DeadCount_day','DeadWeight_g','WorkerName']].copy()
    if not df_mort.empty:
        df_mort['X_label'] = df_mort["Tank"].astype(str) + " | " + df_mort["Block"].astype(str)
        df_total = df_mort.groupby('X_label').agg(
            Total_Dead=('DeadCount_day','sum'),
            Total_Weight=('DeadWeight_g','sum'),
            Workers=('WorkerName', lambda x: ', '.join(x.dropna().astype(str).unique()))
        ).reset_index()
        df_total['Critical'] = df_total['Total_Dead'].apply(lambda x: 'Yes' if x >= 5 else 'No')
        chart = alt.Chart(df_total).mark_bar().encode(
            x='X_label',
            y='Total_Dead',
            tooltip=['X_label','Total_Dead','Total_Weight','Workers'],
            color=alt.condition(alt.datum.Critical == 'Yes', alt.value('red'), alt.value('steelblue'))
        )
        text = chart.mark_text(align='center', baseline='bottom', dy=-2).encode(text='Total_Dead')
        st.altair_chart(chart + text, use_container_width=True)
    else:
        st.info("No mortality data available.")


# =============================
# 5️⃣ WEEKLY VIEW
# =============================
if view_option == "Weekly":
    st.title("🦐 Shrimp Farm Dashboard (Weekly)")

    weekly_df = view_df.copy()

    # --------------------------
    # Top metrics summary
    # --------------------------
    weekly_df['ActualFeed_day_kg'] = (weekly_df['ActualFeed_day_g'] / 1000).round(2)
    weekly_df['ScheduledFeed_day_kg'] = (weekly_df['ScheduledFeed_day_g'] / 1000).round(2)
    weekly_df['LeftoverFeed_g'] = weekly_df['ScheduledFeed_day_g'] - weekly_df['ActualFeed_day_g']
    weekly_df['LeftoverFeed_kg'] = (weekly_df['LeftoverFeed_g'] / 1000).round(2)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    if not weekly_df.empty:
        col1.metric("Feed (g)", round(weekly_df['ActualFeed_day_g'].sum(), 2))
        col2.metric("Feed (kg)", round(weekly_df['ActualFeed_day_kg'].sum(), 2))
        col3.metric("Leftover Feed (g)", round(weekly_df['LeftoverFeed_g'].sum(), 2))
        col4.metric("Leftover Feed (kg)", round(weekly_df['LeftoverFeed_kg'].sum(), 2))
        col5.metric("Mortality %", round(weekly_df['Mortality_pct'].mean() * 100, 2) if 'Mortality_pct' in weekly_df.columns else 0)
        col6.metric("DeadCount", int(weekly_df['DeadCount_day'].sum()))
    else:
        for c in [col1, col2, col3, col4, col5, col6]:
            c.metric("No Data","No Data")

    # --------------------------
    # Worker performance & compliance
    # --------------------------
    st.subheader("Weekly Worker Performance & Compliance")
    weekly_df['DeadWeight_g'] = weekly_df['DeadWeight_g'].fillna(0)
    weekly_df['pH_OK'] = weekly_df['pH'].between(8.0, 8.3)
    weekly_df['Salinity_OK'] = weekly_df['Salinity'].between(25, 30)
    
    worker_summary = (
        weekly_df.groupby('WorkerName', as_index=False)
        .agg(
            Total_Records=('WorkerName','count'),
            pH_OK=('pH_OK','sum'),
            Salinity_OK=('Salinity_OK','sum'),
            ScheduledFeed_kg=('ScheduledFeed_day_g', lambda x: round(x.sum()/1000,2)),
            ActualFeed_kg=('ActualFeed_day_g', lambda x: round(x.sum()/1000,2)),
            Dead_Count=('DeadCount_day','sum'),
            Dead_Weight_g=('DeadWeight_g','sum')
        )
    )
    worker_summary['pH_%'] = ((worker_summary['pH_OK']/worker_summary['Total_Records'])*100).round(1)
    worker_summary['Salinity_%'] = ((worker_summary['Salinity_OK']/worker_summary['Total_Records'])*100).round(1)
    worker_summary['Leftover_kg'] = (worker_summary['ScheduledFeed_kg'] - worker_summary['ActualFeed_kg']).round(2)

    st.dataframe(worker_summary[['WorkerName','pH_%','Salinity_%','ScheduledFeed_kg','ActualFeed_kg','Leftover_kg','Dead_Count','Dead_Weight_g']], use_container_width=True)

    # --------------------------
    # Weekly aggregation for plots (do not print this DataFrame)
    # --------------------------
    block_worker_map = weekly_df[['Block','WorkerName']].dropna().drop_duplicates().groupby('Block')['WorkerName'].first().to_dict()
    tank_colors = {"T3": "blue", "T4": "green", "T5": "red"}

    agg_cols = {
        'ScheduledFeed_day_g': 'sum',
        'ActualFeed_day_g': 'sum',
        'LeftoverFeed_g': 'sum',
        'DeadCount_day': 'sum',
        'DeadWeight_g': 'sum',
        'pH': 'mean',
        'Salinity': 'mean'
    }
    weekly_plot_df = weekly_df.groupby(['Tank','Block'], as_index=False).agg(agg_cols)
    weekly_plot_df['WorkerName'] = weekly_plot_df['Block'].map(block_worker_map)
    weekly_plot_df = weekly_plot_df[weekly_plot_df['Block'] != "Unknown"]
    weekly_plot_df['X_label'] = weekly_plot_df['Tank'] + " | " + weekly_plot_df['Block']

    # --------------------------
    # Weekly Water Quality
    # --------------------------
    st.subheader("Weekly Water Quality (Salinity & pH)")
    df_wq = weekly_plot_df.melt(
        id_vars=['X_label','Tank','Block','WorkerName'],
        value_vars=['Salinity','pH'],
        var_name='Metric',
        value_name='Value'
    )

    df_critical_wq = df_wq[((df_wq['Metric']=='pH') & ((df_wq['Value'] < 8.0) | (df_wq['Value'] > 8.3))) |
                            ((df_wq['Metric']=='Salinity') & ((df_wq['Value'] < 25) | (df_wq['Value'] > 30)))]

    fig_wq = px.line(df_wq, x='X_label', y='Value', color='Tank', line_dash='Metric', markers=True,
                     color_discrete_map=tank_colors,
                     hover_data=['WorkerName','Metric','Value','Tank','Block'])

    if not df_critical_wq.empty:
        fig_wq.add_scatter(
            x=df_critical_wq['X_label'],
            y=df_critical_wq['Value'],
            mode='markers',
            marker=dict(color='red', size=12, symbol='x'),
            name='Critical',
            hovertext=df_critical_wq.apply(lambda r: f"Worker: {r.WorkerName}<br>Metric: {r.Metric}<br>Value: {r.Value}", axis=1),
            hoverinfo='text'
        )
    st.plotly_chart(fig_wq, use_container_width=True)

    # --------------------------
    # Weekly Feed Trends
    # --------------------------
    st.subheader("Weekly Feed Trends")
    df_feed = weekly_plot_df.melt(
        id_vars=['X_label','Tank','Block','WorkerName'],
        value_vars=['ScheduledFeed_day_g','ActualFeed_day_g'],
        var_name='Metric',
        value_name='Value'
    )
    fig_feed = px.line(df_feed, x='X_label', y='Value', color='Tank', line_dash='Metric', markers=True,
                       color_discrete_map=tank_colors,
                       hover_data=['WorkerName','Metric','Value','Tank','Block'])
    st.plotly_chart(fig_feed, use_container_width=True)

    # --------------------------
    # Weekly Mortality
    # --------------------------
    st.subheader("Weekly Mortality")
    df_mort = weekly_plot_df[['X_label','DeadCount_day','DeadWeight_g','WorkerName']].copy()
    df_mort['DeadCount_day'] = df_mort['DeadCount_day'].fillna(0)

    df_critical_mort = df_mort[df_mort['DeadCount_day'] >= 5]

    mort_bar = alt.Chart(df_mort).mark_bar(opacity=0.8).encode(
        x=alt.X('X_label:N', title='Tank | Block'),
        y=alt.Y('DeadCount_day:Q', title='Dead Shrimp Count'),
        tooltip=[alt.Tooltip('WorkerName:N', title='Worker'),
                 alt.Tooltip('DeadCount_day:Q', title='Dead Count'),
                 alt.Tooltip('DeadWeight_g:Q', title='Dead Weight (g)')]
    )
    mort_hover = alt.Chart(df_mort).mark_point(opacity=0, size=100).encode(
        x='X_label:N',
        y='DeadCount_day:Q',
        tooltip=[alt.Tooltip('WorkerName:N', title='Worker'),
                 alt.Tooltip('DeadCount_day:Q', title='Dead Count'),
                 alt.Tooltip('DeadWeight_g:Q', title='Dead Weight (g)')]
    )
    mort_text = alt.Chart(df_mort).mark_text(dy=-5, fontWeight='bold').encode(
        x='X_label:N',
        y='DeadCount_day:Q',
        text=alt.Text('DeadCount_day:Q', format='.0f')
    )

    if not df_critical_mort.empty:
        mort_critical = alt.Chart(df_critical_mort).mark_circle(size=150, color='red').encode(
            x='X_label:N',
            y='DeadCount_day:Q',
            tooltip=[alt.Tooltip('WorkerName:N', title='Worker'),
                     alt.Tooltip('DeadCount_day:Q', title='Dead Count'),
                     alt.Tooltip('DeadWeight_g:Q', title='Dead Weight (g)')]
        )
        st.altair_chart(mort_bar + mort_hover + mort_text + mort_critical, use_container_width=True)
    else:
        st.altair_chart(mort_bar + mort_hover + mort_text, use_container_width=True)

# -------------------------------
# Performance summary
# -------------------------------
# Calculate daily metrics first
view_df['Survival_pct'] = (view_df['LiveCount']/view_df['InitialCount']*100).round(2)
view_df['Mortality_pct'] = (100 - view_df['Survival_pct']).round(2)
view_df['FeedUsedForScore'] = view_df[['ActualFeed_day_g','ScheduledFeed_day_g']].min(axis=1)
view_df['FeedEfficiency_pct'] = (view_df['FeedUsedForScore']/view_df['ScheduledFeed_day_g']*100).round(2)

def get_salinity_score(val):
    if 25 <= val <= 30: return 100
    elif 23 <= val <= 25 or 30 <= val <= 33: return 80
    else: return 50
def get_ph_score(val):
    if 8.0 <= val <= 8.3:return 100  # Ideal
    elif 7.8 <= val <= 8.0 or 8.3 <= val <= 8.5:return 80   # Acceptable
    else: return 50   # Danger    

view_df['SalinityScore'] = view_df['Salinity'].apply(get_salinity_score)
view_df['PHScore'] = view_df['pH'].apply(get_ph_score)
view_df['OverallPerformance_pct'] = view_df[['Survival_pct','FeedEfficiency_pct','SalinityScore','PHScore']].mean(axis=1).round(2)

# -------------------------------
# Performance Table based on sidebar View Mode
# -------------------------------
if view_option == "Daily":
    performance_table = view_df[['Date','Block','Tank','WorkerName','Survival_pct','Mortality_pct','FeedEfficiency_pct','SalinityScore','PHScore','OverallPerformance_pct']]

elif view_option == "Weekly":
    # Add Week column
    view_df['WeekRange'] = view_df['Date'] - pd.to_timedelta(view_df['Date'].dt.dayofweek, unit='d')
    view_df['WeekRangeEnd'] = view_df['WeekRange'] + pd.Timedelta(days=6)
    view_df['Week'] = view_df['WeekRange'].dt.date.astype(str) + " to " + view_df['WeekRangeEnd'].dt.date.astype(str)
    
    # Aggregate by Week + Block + Tank
    performance_table = view_df.groupby(['Week','Block','Tank'], as_index=False).agg(
        Survival_pct=('Survival_pct','mean'),
        Mortality_pct=('Mortality_pct','mean'),
        FeedEfficiency_pct=('FeedEfficiency_pct','mean'),
        SalinityScore=('SalinityScore','mean'),
        PHScore=('PHScore','mean'),
        OverallPerformance_pct=('OverallPerformance_pct','mean')
    ).round(2)
    
    # Combine Worker Names per Block & Tank
    workers = view_df.groupby(['Week','Block','Tank'])['WorkerName'].unique().apply(lambda x: ', '.join(x))
    performance_table['Workers'] = performance_table.set_index(['Week','Block','Tank']).index.map(workers).values
    
    # Sort by overall performance
    performance_table = performance_table.sort_values(by='OverallPerformance_pct', ascending=False)

st.subheader("Block & Tank Performance Summary")
st.dataframe(performance_table)



# =============================
# 6️⃣ RISK TABLE (Updated with Alert Levels + Details)
# =============================
if 'X_label' not in view_df.columns:
    view_df['X_label'] = view_df['Date'].dt.date

# Existing Alert_Level logic (kept unchanged)
def get_alert_level(row):
    alerts = []
    if row['pH'] <= 8.0 or row['pH'] >= 8.3:
        alerts.append("pH")
    if row['Salinity'] <= 25 or row['Salinity'] >= 30:
        alerts.append("Salinity")
    if row['WaterTemperature'] <= 28 or row['WaterTemperature'] >= 30:
        alerts.append("Temp")
    if row['DeadCount_day'] >= 5:
        alerts.append("Mortality")
    
    if not alerts:
        return "Normal ✅"
    elif len(alerts) <= 2:
        return "Warning ⚠"
    else:
        return "Critical 🔴"

view_df['Alert_Level'] = view_df.apply(get_alert_level, axis=1)

# ----------------------------
# New column: Alert_Details
# ----------------------------
def get_alert_details(row):
    details = []

    # pH
    if 8.0 <= row['pH'] <= 8.3:
        details.append("pH ✅")
    elif 7.9 <= row['pH'] < 8.0 or 8.3 < row['pH'] <= 8.4:
        details.append("pH ⚠")
    else:
        details.append("pH 🔴")

    # Salinity
    if 25 <= row['Salinity'] <= 30:
        details.append("Salinity ✅")
    elif 24 <= row['Salinity'] < 25 or 30 < row['Salinity'] <= 31:
        details.append("Salinity ⚠")
    else:
        details.append("Salinity 🔴")

    # Water Temperature
    if 28 <= row['WaterTemperature'] <= 30:
        details.append("Temp ✅")
    elif 27 <= row['WaterTemperature'] < 28 or 30 < row['WaterTemperature'] <= 31:
        details.append("Temp ⚠")
    else:
        details.append("Temp 🔴")

    # Mortality
    if row['DeadCount_day'] < 5:
        details.append("Mortality ✅")
    elif 5 <= row['DeadCount_day'] <= 6:
        details.append("Mortality ⚠")
    else:
        details.append("Mortality 🔴")

    return ", ".join(details)

view_df['Alert_Details'] = view_df.apply(get_alert_details, axis=1)

# Columns to display
risk_display_cols = [
    'X_label','Block','Tank','pH','Salinity','WaterTemperature','DeadCount_day',
    'ScheduledFeed_day_g','ActualFeed_day_g','Alert_Level','Alert_Details'
]

if not view_df.empty:
    display_df = view_df[risk_display_cols].rename(columns={
        'X_label':'Date/Week',
        'ScheduledFeed_day_g':'Scheduled Feed (g)',
        'ActualFeed_day_g':'Actual Feed (g)',
        'DeadCount_day':'Dead Shrimp'
    })

    # Existing coloring functions (kept unchanged)
    def color_alert(val):
        if val == "Critical 🔴":
            return "background-color: #FF0000; color: white; font-weight: bold"
        elif val == "Warning ⚠":
            return "background-color: #FFA500; color: black; font-weight: bold"
        elif val == "Normal ✅":
            return "background-color: #90EE90; color: black; font-weight: bold"
        return ""

    def color_ph(val):
        if val <= 8.0 or val >= 8.3: return "background-color: #FF0000"
        elif val <= 8.1 or val >= 8.2: return "background-color: #FF8000"
        return ""
    def color_salinity(val):
        if val <= 25 or val >= 30: return "background-color: #FF0000"
        elif val <= 26 or val >= 29: return "background-color: #FF8000"
        return ""
    def color_dead(val):
        if val >= 5: return "background-color: #FF0000"
        elif val >= 4: return "background-color: #FF8000"
        return ""
    def color_feed(val):
        if val == 1: return "background-color: #FFA500"
        return ""

    st.subheader("Tank Risk & Alerts")
    st.dataframe(
        display_df.style
        .applymap(color_alert, subset=['Alert_Level'])
        .applymap(color_ph, subset=['pH'])
        .applymap(color_salinity, subset=['Salinity'])
        .applymap(color_dead, subset=['Dead Shrimp'])
        .applymap(color_feed, subset=['Scheduled Feed (g)']),
        height=500
    )
else:
    st.info("No data available for selected filters.")
