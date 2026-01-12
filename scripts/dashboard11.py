
import streamlit as st
import pandas as pd
import plotly.express as px
import altair as alt
import plotly.graph_objects as go
import plotly.io as pio
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
import tempfile
import os
from streamlit_autorefresh import st_autorefresh


# ---------------------------
# 1️⃣ Page config
# ---------------------------
st.set_page_config(page_title="Shrimp Farm Dashboard", layout="wide")

# 🔄 Auto refresh every 30 seconds
st_autorefresh(interval=30 * 1000, key="datarefresh")

# ---------------------------
# 2️⃣ Folder to watch (GitHub-safe)
# ---------------------------

import os
import glob
import pandas as pd
import streamlit as st

# ---------------------------
# Path to your tank summary file in the repo root
# ---------------------------

# Check if running on Streamlit Cloud, otherwise fallback to local path logic
if os.path.exists("/mount/src/shrimp-dashboard"):
    repo_root = "/mount/src/shrimp-dashboard"
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # folder of this script (e.g., /scripts)
    repo_root = os.path.abspath(os.path.join(BASE_DIR, "..")) # go up one level to shrimp-dashboard root

# Look for files matching Tank_Consolidated_Report_*.xlsx directly in the root
files = glob.glob(os.path.join(repo_root, "Tank_Consolidated_Report_*.xlsx"))

if not files:
    st.error(f"❌ No tank summary files found in the root directory: {repo_root}")
    # Optional: list files to see what is actually there for debugging
    st.write("Files found in root:", os.listdir(repo_root))
    st.stop()

# Pick the latest file by modification time
latest_file = max(files, key=os.path.getmtime)

# ---------------------------
# Load the Excel file
# ---------------------------
try:
    df = pd.read_excel(latest_file)
    st.success(f"✅ Loaded file: {os.path.basename(latest_file)}")
except Exception as e:
    st.error(f"Failed to load Excel file: {latest_file}\nError: {e}")
    st.stop()


# Example: show dataframe
#st.dataframe(df)

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
    week_options = ["All"] + week_options
    selected_week = st.sidebar.selectbox("Select Week", week_options)
    # Determine start & end dates
    if selected_week == "All":
       week_start = df['Date'].min()
       week_end = df['Date'].max()
    else:
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

    # ----------------------------
    # Feed calculations
    # ----------------------------
    view_df['ActualFeed_day_kg'] = (view_df['ActualFeed_day_g'] / 1000).round(2)
    view_df['ScheduledFeed_day_kg'] = (view_df['ScheduledFeed_day_g'] / 1000).round(2)
    view_df['LeftoverFeed_g'] = view_df['ScheduledFeed_day_g'] - view_df['ActualFeed_day_g']
    view_df['LeftoverFeed_kg'] = (view_df['LeftoverFeed_g'] / 1000).round(2)
    # Get first day per batch
    
    min_date = view_df['Date'].min()
    first_day_records = view_df[view_df['Date'] == min_date]
    total_initial = first_day_records.groupby('Batch ID')['InitialCount'].sum().sum()
    total_dead = view_df['DeadCount_day'].sum()

# 3. Calculation
    if total_initial > 0:
        mortality_pct = round((total_dead / total_initial) * 100, 2)
    else:
        mortality_pct = 0.0

# DEBUG PRINT (Optional - remove once fixed)
    st.write(f"Total Dead: {total_dead} | Total Initial: {total_initial}")

# Mortality %
    mortality_pct = round((total_dead / total_initial) * 100, 2) if total_initial > 0 else 0

    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    if not view_df.empty:
        col1.metric("Feed (g)", round(view_df['ActualFeed_day_g'].sum(), 2))
        col2.metric("Feed (kg)", round(view_df['ActualFeed_day_kg'].sum(), 2))
        col3.metric("Leftover Feed (g)", round(view_df['LeftoverFeed_g'].sum(), 2))
        col4.metric("Leftover Feed (kg)", round(view_df['LeftoverFeed_kg'].sum(), 2))
        col5.metric("Mortality %", mortality_pct)
        col6.metric("Dead Count", int(total_dead))
    else:
        for c in [col1, col2, col3, col4, col5, col6]:
            c.metric("No Data","No Data")

    # ----------------------------
    # Worker performance & compliance (only 6 blocks)
    # ----------------------------

    # Strip column names
    view_df.columns = view_df.columns.str.strip()

    # Ensure pH & Salinity are numeric
    view_df['pH'] = pd.to_numeric(view_df['pH'], errors='coerce')
    view_df['Salinity'] = pd.to_numeric(view_df['Salinity'], errors='coerce')

    view_df['DeadWeight_g'] = view_df['DeadWeight_g'].fillna(0)
    view_df['pH_OK'] = view_df['pH'].between(7.6, 8.3).astype(int)
    view_df['Salinity_OK'] = view_df['Salinity'].between(25, 30).astype(int)
    view_df['WorkerName'] = view_df['WorkerName'].astype(str).str.strip().str.title()

    # Extract block letter E-J
    view_df['Block_Letter'] = view_df['Block'].astype(str).str.upper().str.extract(r'([E-J])', expand=False)

    # Map blocks to workers
    block_worker_map = {
        'E': 'Jimmy', 'F': 'Jimmy', 'G': 'Jimmy',
        'H': 'Flora', 'I': 'Flora', 'J': 'Flora'
    }
    view_df['Worker_Assigned'] = view_df['Block_Letter'].map(block_worker_map)

    # Keep only Jimmy & Flora blocks
    worker_df = view_df[view_df['Worker_Assigned'].isin(['Jimmy','Flora'])].copy()

    # Use WorkerName if present; otherwise fallback
    worker_df['Worker_Display'] = worker_df['WorkerName'].where(worker_df['WorkerName'].notna(), worker_df['Worker_Assigned'])

    # Group by worker
    worker_summary = (
        worker_df.groupby('Worker_Display', as_index=False)
        .agg(
            Total_Records=('Worker_Display','count'),
            pH_OK=('pH_OK','sum'),
            Salinity_OK=('Salinity_OK','sum'),
            ScheduledFeed_kg=('ScheduledFeed_day_g', lambda x: round(x.sum()/1000,2)),
            ActualFeed_kg=('ActualFeed_day_g', lambda x: round(x.sum()/1000,2)),
            Dead_Count=('DeadCount_day','sum'),
            Dead_Weight_g=('DeadWeight_g','sum')
        )
    )

    worker_summary['pH_%'] = ((worker_summary['pH_OK'] / worker_summary['Total_Records'])*100).round(1)
    worker_summary['Salinity_%'] = ((worker_summary['Salinity_OK'] / worker_summary['Total_Records'])*100).round(1)
    worker_summary['Leftover_kg'] = (worker_summary['ScheduledFeed_kg'] - worker_summary['ActualFeed_kg']).round(2)

    st.subheader("Worker Performance & Water Quality Compliance (Daily)")
    st.dataframe(
        worker_summary[['Worker_Display','pH_%','Salinity_%','ScheduledFeed_kg',
                        'ActualFeed_kg','Leftover_kg','Dead_Count','Dead_Weight_g']],
        use_container_width=True
    )

    # ----------------------------
    # Water quality plot (all blocks)
    # ----------------------------
    st.subheader("Water Quality (Salinity & pH)")
    tank_colors = {"T3": "purple", "T4": "darkblue", "T5": "green"}
    metrics = ['Salinity','pH']
    df_plot = view_df.copy()  # Use full dataset for graphs

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
        # Critical pH markers
        df_critical_ph = df_melt[(df_melt['Metric'] == 'pH') & ((df_melt['Value'] < 7.6) | (df_melt['Value'] > 8.3))]
        fig.add_trace(go.Scatter(
            x=df_critical_ph['X_label'],
            y=df_critical_ph['Value'],
            mode='markers',
            marker=dict(color='red', size=12, symbol='x'),
            name='Critical pH',
            hovertemplate="Worker: %{customdata[0]}<br>Tank: %{customdata[1]}<br>Block: %{customdata[2]}<br>Parameter: %{customdata[3]}<br>Value: %{customdata[4]}",
            customdata=df_critical_ph[['WorkerName','Tank','Block','Metric','Value']]
        ))
        # Critical Salinity markers
        df_critical_salinity = df_melt[(df_melt['Metric'] == 'Salinity') & ((df_melt['Value'] < 25) | (df_melt['Value'] > 30))]
        fig.add_trace(go.Scatter(
            x=df_critical_salinity['X_label'],
            y=df_critical_salinity['Value'],
            mode='markers',
            marker=dict(color='orange', size=12, symbol='x'),
            name='Critical Salinity',
            hovertemplate="Worker: %{customdata[0]}<br>Tank: %{customdata[1]}<br>Block: %{customdata[2]}<br>Parameter: %{customdata[3]}<br>Value: %{customdata[4]}",
            customdata=df_critical_salinity[['WorkerName','Tank','Block','Metric','Value']]
        ))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No water quality data available.")

    # ----------------------------
    # Feed trends (all blocks)
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
            hover_data=['WorkerName','Tank','Block','Value','Metric']
        )
        st.plotly_chart(fig_feed, use_container_width=True)
    else:
        st.info("No feed data available.")

    # ----------------------------
    # Mortality Trends (all blocks)
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
        df_total['Critical'] = df_total['Total_Dead'].apply(lambda x: 'Yes' if x > 5 else 'No')
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

    total_dead_weekly = weekly_df['DeadCount_day'].sum()
    active_batches = weekly_df['Batch ID'].unique()
    batch_start_data = view_df[view_df['Batch ID'].isin(active_batches)]
    absolute_min_date = batch_start_data['Date'].min()

    first_day_records = batch_start_data[batch_start_data['Date'] == absolute_min_date]
    total_initial_weekly = first_day_records.groupby('Batch ID')['InitialCount'].sum().sum()

    if total_initial_weekly > 0:
        mortality_pct_weekly = round((total_dead_weekly / total_initial_weekly) * 100, 2)
    else:
        mortality_pct_weekly = 0.0
    # DEBUG: Use this to see if the numbers match your expectations
    st.write(f"DEBUG: Deaths={total_dead_weekly}, Initial={total_initial_weekly}")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    if not weekly_df.empty:
        col1.metric("Feed (g)", round(weekly_df['ActualFeed_day_g'].sum(), 2))
        col2.metric("Feed (kg)", round(weekly_df['ActualFeed_day_kg'].sum(), 2))
        col3.metric("Leftover Feed (g)", round(weekly_df['LeftoverFeed_g'].sum(), 2))
        col4.metric("Leftover Feed (kg)", round(weekly_df['LeftoverFeed_kg'].sum(), 2))
        col5.metric("Mortality %", mortality_pct_weekly)
        col6.metric("DeadCount", int(total_dead_weekly))
    else:
        for c in [col1, col2, col3, col4, col5, col6]:
            c.metric("No Data","No Data")

    # --------------------------
    # Worker performance & compliance
    # --------------------------
    st.subheader("Weekly Worker Performance & Compliance")
    weekly_df = view_df.copy()
    weekly_df['DeadWeight_g'] = weekly_df['DeadWeight_g'].fillna(0)
    weekly_df['pH_OK'] = weekly_df['pH'].between(7.6, 8.3)
    weekly_df['Salinity_OK'] = weekly_df['Salinity'].between(25, 30)
    weekly_df['WorkerName'] = weekly_df['WorkerName'].astype(str).str.strip().str.title()

    # Extract block letter E-J
    weekly_df['Block_Letter'] = weekly_df['Block'].astype(str).str.upper().str.extract(r'([E-J])', expand=False)
    # Map blocks to workers
    block_worker_map = {
         'E': 'Jimmy', 'F': 'Jimmy', 'G': 'Jimmy',
         'H': 'Flora', 'I': 'Flora', 'J': 'Flora'
    }

    weekly_df['Worker_Assigned'] = weekly_df['Block_Letter'].map(block_worker_map)
    worker_df = weekly_df[weekly_df['Worker_Assigned'].isin(['Jimmy','Flora'])].copy()
    # Add Week column for aggregation
    worker_df['WeekRangeStart'] = worker_df['Date'] - pd.to_timedelta(worker_df['Date'].dt.dayofweek, unit='d')
    worker_df['WeekRangeEnd'] = worker_df['WeekRangeStart'] + pd.Timedelta(days=6)
    worker_df['Week'] = worker_df['WeekRangeStart'].dt.date.astype(str) + " to " + worker_df['WeekRangeEnd'].dt.date.astype(str)

    worker_df = worker_df[(worker_df['Date'] >= week_start) & (worker_df['Date'] <= week_end)]
    worker_df['Worker_Display'] = worker_df['WorkerName'].where(worker_df['WorkerName'].notna(), worker_df['Worker_Assigned'])
    if selected_week == "All":
       group_cols = ['Worker_Display']
       
    else: 
       group_cols = ['Week', 'Worker_Display']

    if selected_week != "All":
       worker_df = worker_df[(worker_df['Date'] >= week_start) & (worker_df['Date'] <= week_end)]
      
    worker_summary_weekly = (
        worker_df.groupby(group_cols, as_index=False)
        .agg(
            Total_Records=('Worker_Display','count'),
            pH_OK=('pH_OK','sum'),
            Salinity_OK=('Salinity_OK','sum'),
            ScheduledFeed_kg=('ScheduledFeed_day_g', lambda x: round(x.sum()/1000,2)),
            ActualFeed_kg=('ActualFeed_day_g', lambda x: round(x.sum()/1000,2)),
            Dead_Count=('DeadCount_day','sum'),
            Dead_Weight_g=('DeadWeight_g','sum')
        )
    )
    worker_summary_weekly['pH_%'] = ((worker_summary_weekly['pH_OK']/worker_summary_weekly['Total_Records'])*100).round(1)
    worker_summary_weekly['Salinity_%'] = ((worker_summary_weekly['Salinity_OK']/worker_summary_weekly['Total_Records'])*100).round(1)
    worker_summary_weekly['Leftover_kg'] = (worker_summary_weekly['ScheduledFeed_kg'] - worker_summary_weekly['ActualFeed_kg']).round(2)

    st.dataframe(worker_summary_weekly[group_cols+['pH_%','Salinity_%','ScheduledFeed_kg','ActualFeed_kg','Leftover_kg','Dead_Count','Dead_Weight_g']], use_container_width=True)

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

    df_critical_wq = df_wq[((df_wq['Metric']=='pH') & ((df_wq['Value'] < 7.6) | (df_wq['Value'] > 8.3))) |
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

    df_critical_mort = df_mort[df_mort['DeadCount_day'] > 5]

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

# =============================
# 6️⃣ MONTHLY VIEW
# =============================
if view_option == "Monthly":
    st.title("🦐 Shrimp Farm Dashboard (Monthly)")

    # Aggregate monthly data
    monthly_df = view_df.groupby(['Block','Tank'], as_index=False).agg(
        ScheduledFeed_g=('ScheduledFeed_day_g','sum'),
        ActualFeed_g=('ActualFeed_day_g','sum'),
        LeftoverFeed_g=('ScheduledFeed_day_g', lambda x: x.sum() - view_df.loc[x.index,'ActualFeed_day_g'].sum()),
        DeadCount=('DeadCount_day','sum'),
        DeadWeight_g=('DeadWeight_g','sum'),
        Salinity_avg=('Salinity','mean'),
        pH_avg=('pH','mean'),
        Mortality_pct=('Mortality_pct','mean')
    )
    monthly_df['ScheduledFeed_kg'] = (monthly_df['ScheduledFeed_g']/1000).round(2)
    monthly_df['ActualFeed_kg'] = (monthly_df['ActualFeed_g']/1000).round(2)
    monthly_df['Leftover_kg'] = (monthly_df['LeftoverFeed_g']/1000).round(2)
    
    # Metrics summary
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    if not monthly_df.empty:
        col1.metric("Feed (kg)", f"{monthly_df['ActualFeed_kg'].sum():.2f}")
        col2.metric("Scheduled Feed (kg)", f"{monthly_df['ScheduledFeed_kg'].sum():.2f}")
        col3.metric("Leftover Feed (kg)", f"{monthly_df['Leftover_kg'].sum():.2f}")
        col4.metric("Dead Count", monthly_df['DeadCount'].sum())
        col5.metric("Dead Weight (g)", monthly_df['DeadWeight_g'].sum())
        col6.metric("Avg Mortality %", round(monthly_df['Mortality_pct'].mean()*100,2))
    else:
        for c in [col1, col2, col3, col4, col5, col6]:
            c.metric("No Data","No Data")

    # ----------------------------
    # Monthly Worker Performance
    # ----------------------------
    view_df['pH_OK'] = view_df['pH'].between(7.6,8.3)
    view_df['Salinity_OK'] = view_df['Salinity'].between(25,30)
    view_df['WorkerName'] = view_df['WorkerName'].astype(str).str.strip().str.title()
    view_df['Block_Letter'] = view_df['Block'].astype(str).str.upper().str.extract(r'([E-J])', expand=False)
    block_worker_map = {'E': 'Jimmy', 'F': 'Jimmy', 'G': 'Jimmy', 'H': 'Flora', 'I': 'Flora', 'J': 'Flora'}
    view_df['Worker_Assigned'] = view_df['Block_Letter'].map(block_worker_map)
    worker_df = view_df[view_df['Worker_Assigned'].isin(['Jimmy','Flora'])].copy()
    worker_df['Worker_Display'] = worker_df['WorkerName'].where(worker_df['WorkerName'].notna(), worker_df['Worker_Assigned'])

    worker_summary = (
        worker_df.groupby('Worker_Display', as_index=False)
        .agg(
            Total_Records=('Worker_Display','count'),
            pH_OK=('pH_OK','sum'),
            Salinity_OK=('Salinity_OK','sum'),
            ScheduledFeed_kg=('ScheduledFeed_day_g', lambda x: round(x.sum()/1000,2)),
            ActualFeed_kg=('ActualFeed_day_g', lambda x: round(x.sum()/1000,2)),
            Dead_Count=('DeadCount_day','sum'),
            Dead_Weight_g=('DeadWeight_g','sum')
        )
    )
    worker_summary['pH_%'] = ((worker_summary['pH_OK'] / worker_summary['Total_Records'])*100).round(1)
    worker_summary['Salinity_%'] = ((worker_summary['Salinity_OK'] / worker_summary['Total_Records'])*100).round(1)
    worker_summary['Leftover_kg'] = (worker_summary['ScheduledFeed_kg'] - worker_summary['ActualFeed_kg']).round(2)

    st.subheader("Worker Performance & Water Quality Compliance (Monthly)")
    st.dataframe(
        worker_summary[['Worker_Display','pH_%','Salinity_%','ScheduledFeed_kg',
                        'ActualFeed_kg','Leftover_kg','Dead_Count','Dead_Weight_g']],
        use_container_width=True
    )

    # ----------------------------
    # Monthly Water Quality Plot (Line) – WorkerName included
    # ----------------------------
    st.subheader("Monthly Water Quality (Avg Salinity & pH)")
    monthly_df_plot = view_df.groupby(['Tank','Block'], as_index=False).agg(
        Salinity_avg=('Salinity','mean'),
        pH_avg=('pH','mean'),
        WorkerName=('WorkerName','first')  # Ensure WorkerName present
    )
    monthly_df_plot["X_label"] = monthly_df_plot["Tank"].astype(str) + " | " + monthly_df_plot["Block"].astype(str)
    df_melt = monthly_df_plot.melt(
        id_vars=['X_label','WorkerName','Tank','Block'],
        value_vars=['Salinity_avg','pH_avg'],
        var_name='Metric',
        value_name='Value'
    )
    fig = px.line(
        df_melt,
        x='X_label',
        y='Value',
        color='Metric',
        markers=True,
        labels={'X_label':'Tank | Block','Value':'Value','Metric':'Parameter'},
        hover_data=['WorkerName','Tank','Block','Value','Metric']
    )

    # Critical markers
    df_critical_ph = df_melt[(df_melt['Metric']=='pH_avg') & ((df_melt['Value']<7.6)|(df_melt['Value']>8.3))]
    fig.add_trace(go.Scatter(
        x=df_critical_ph['X_label'],
        y=df_critical_ph['Value'],
        mode='markers',
        marker=dict(color='red', size=12, symbol='x'),
        name='Critical pH',
        hovertemplate="Worker: %{customdata[0]}<br>Tank: %{customdata[1]}<br>Block: %{customdata[2]}<br>Parameter: %{customdata[3]}<br>Value: %{customdata[4]}",
        customdata=df_critical_ph[['WorkerName','Tank','Block','Metric','Value']]
    ))
    df_critical_salinity = df_melt[(df_melt['Metric']=='Salinity_avg') & ((df_melt['Value']<25)|(df_melt['Value']>30))]
    fig.add_trace(go.Scatter(
        x=df_critical_salinity['X_label'],
        y=df_critical_salinity['Value'],
        mode='markers',
        marker=dict(color='orange', size=12, symbol='x'),
        name='Critical Salinity',
        hovertemplate="Worker: %{customdata[0]}<br>Tank: %{customdata[1]}<br>Block: %{customdata[2]}<br>Parameter: %{customdata[3]}<br>Value: %{customdata[4]}",
        customdata=df_critical_salinity[['WorkerName','Tank','Block','Metric','Value']]
    ))
    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------
    # Monthly Feed Trends (Line) – WorkerName included
    # ----------------------------
    st.subheader("Monthly Feed Trends")
    monthly_feed = view_df.groupby(['Tank','Block'], as_index=False).agg(
        ScheduledFeed_g=('ScheduledFeed_day_g','sum'),
        ActualFeed_g=('ActualFeed_day_g','sum'),
        WorkerName=('WorkerName','first')
    )
    monthly_feed["X_label"] = monthly_feed["Tank"].astype(str) + " | " + monthly_feed["Block"].astype(str)
    df_feed = monthly_feed.melt(
        id_vars=['X_label','WorkerName','Tank','Block'],
        value_vars=['ScheduledFeed_g','ActualFeed_g'],
        var_name='Metric',
        value_name='Value'
    )
    fig_feed = px.line(
        df_feed,
        x='X_label',
        y='Value',
        color='Metric',
        markers=True,
        labels={'X_label':'Tank | Block','Value':'Feed (g)','Metric':'Parameter'},
        hover_data=['WorkerName','Tank','Block','Value','Metric']
    )
    st.plotly_chart(fig_feed, use_container_width=True)

    # ----------------------------
    # Monthly Mortality Trends – WorkerName included
    # ----------------------------
    st.subheader("Monthly Mortality Trends")
    monthly_mort = view_df.groupby(['Tank','Block'], as_index=False).agg(
        Total_Dead=('DeadCount_day','sum'),
        Total_Weight=('DeadWeight_g','sum'),
        WorkerName=('WorkerName','first')
    )
    monthly_mort["X_label"] = monthly_mort["Tank"].astype(str) + " | " + monthly_mort["Block"].astype(str)
    chart = alt.Chart(monthly_mort).mark_bar().encode(
        x='X_label',
        y='Total_Dead',
        tooltip=['X_label','Total_Dead','Total_Weight','WorkerName'],
        color=alt.condition(alt.datum.Total_Dead >= 5, alt.value('red'), alt.value('steelblue'))
    )
    text = chart.mark_text(align='center', baseline='bottom', dy=-2).encode(text='Total_Dead')
    st.altair_chart(chart + text, use_container_width=True)


# ==========================================
# 1️⃣ PERFORMANCE TABLE (Daily / Weekly / Monthly)
# ==========================================
# Calculate daily metrics
view_df['Survival_pct'] = (view_df['LiveCount']/view_df['InitialCount']*100).round(2)
view_df['Mortality_pct'] = (100 - view_df['Survival_pct']).round(2)
view_df['FeedUsedForScore'] = view_df[['ActualFeed_day_g','ScheduledFeed_day_g']].min(axis=1)
view_df['FeedEfficiency_pct'] = (view_df['FeedUsedForScore']/view_df['ScheduledFeed_day_g']*100).round(2)

def get_salinity_score(val):
    if 25 <= val <= 30: return 100
    elif 23 <= val <= 25 or 30 <= val <= 33: return 80
    else: return 50

def get_ph_score(val):
    if 7.6 <= val <= 8.3:return 100  # Ideal
    elif 7.4 <= val <= 7.6 or 8.3 <= val <= 8.5:return 80   # Acceptable
    else: return 50   # Danger    

view_df['SalinityScore'] = view_df['Salinity'].apply(get_salinity_score)
view_df['PHScore'] = view_df['pH'].apply(get_ph_score)
view_df['OverallPerformance_pct'] = view_df[['Survival_pct','FeedEfficiency_pct','SalinityScore','PHScore']].mean(axis=1).round(2)


# -------------------------------
# Block & Tank Performance Summary
# -------------------------------

view_df['pH_OK'] = view_df['pH'].between(7.6, 8.3).astype(int)
view_df['Salinity_OK'] = view_df['Salinity'].between(25, 30).astype(int)

# -------------------------------
# Block & Tank Performance Summary
# -------------------------------
agg_dict = {
    'Survival_pct': 'mean',
    'Mortality_pct': 'mean',
    'FeedEfficiency_pct': 'mean',
    'pH_%': lambda x: round((x.sum()/len(x))*100, 1),
    'Salinity_%': lambda x: round((x.sum()/len(x))*100, 1),
    'OverallPerformance_pct': 'mean'
}

# Add placeholder for aggregation
view_df['pH_%'] = view_df['pH_OK']
view_df['Salinity_%'] = view_df['Salinity_OK']

if view_option == "Daily":
    performance_table = view_df.groupby(['Date','Block','Tank'], as_index=False).agg(agg_dict)

elif view_option == "Weekly":
    view_df['WeekRange'] = view_df['Date'] - pd.to_timedelta(view_df['Date'].dt.dayofweek, unit='d')
    view_df['WeekRangeEnd'] = view_df['WeekRange'] + pd.Timedelta(days=6)
    view_df['Week'] = view_df['WeekRange'].dt.date.astype(str) + " to " + view_df['WeekRangeEnd'].dt.date.astype(str)
    performance_table = view_df.groupby(['Week','Block','Tank'], as_index=False).agg(agg_dict)

elif view_option == "Monthly":
    view_df['Month'] = view_df['Date'].dt.to_period('M').astype(str)
    performance_table = view_df.groupby(['Month','Block','Tank'], as_index=False).agg(agg_dict)

# -------------------------------
# Add Workers
# -------------------------------
if view_option == "Daily":
    workers = view_df.groupby(['Date','Block','Tank'])['WorkerName'].unique().apply(lambda x: ', '.join(x))
    performance_table['Workers'] = performance_table.set_index(['Date','Block','Tank']).index.map(workers).values
elif view_option == "Weekly":
    workers = view_df.groupby(['Week','Block','Tank'])['WorkerName'].unique().apply(lambda x: ', '.join(x))
    performance_table['Workers'] = performance_table.set_index(['Week','Block','Tank']).index.map(workers).values
elif view_option == "Monthly":
    workers = view_df.groupby(['Month','Block','Tank'])['WorkerName'].unique().apply(lambda x: ', '.join(x))
    performance_table['Workers'] = performance_table.set_index(['Month','Block','Tank']).index.map(workers).values

# Sort table
performance_table = performance_table.sort_values(by='OverallPerformance_pct', ascending=False)

st.subheader("Block & Tank Performance Summary")
st.dataframe(performance_table)


# =============================
# 6️⃣ RISK TABLE (Fixed for TypeError)
# =============================
if 'X_label' not in view_df.columns:
    view_df['X_label'] = view_df['Date'].dt.date

# --- Ensure columns are numeric and replace non-numeric entries ---
numeric_cols_defaults = {
    #'pH': 8.1,
    #'Salinity': 27,
    #'WaterTemperature': 29,
    'DeadCount_day': 0
}

for col, default in numeric_cols_defaults.items():
    if col in view_df.columns:
        # Convert to numeric, coerce errors to NaN, then fill with default
        view_df[col] = pd.to_numeric(view_df[col], errors='coerce').fillna(default)
for col in ['pH','Salinity','WaterTemperature']:
    if col in view_df.columns:
        view_df[col] = pd.to_numeric(view_df[col], errors='coerce')
# ----------------------------------------------------------------------
# Alert_Level logic
def get_alert_level(row):
    alerts = []
    try:
        if row['pH'] <= 7.6 or row['pH'] >= 8.3:
            alerts.append("pH")
        if row['Salinity'] <= 25 or row['Salinity'] >= 30:
            alerts.append("Salinity")
        if row['WaterTemperature'] <= 28 or row['WaterTemperature'] >= 30:
            alerts.append("Temp")
        if row['DeadCount_day'] > 5:
            alerts.append("Mortality")
        if row.get('Has_Water_Data',1) == 0:
            return "No Water Data ❌"
    except TypeError:
        # In case there is still an invalid value, treat as normal
        return "Normal ✅"

    if not alerts:
        return "Normal ✅"
    elif len(alerts) <= 2:
        return "Warning ⚠"
    else:
        return "Critical 🔴"

view_df['Alert_Level'] = view_df.apply(get_alert_level, axis=1)

# Alert_Details logic
def get_alert_details(row):
    details = []

    # pH
    if 7.6 <= row['pH'] <= 8.3:
        details.append("pH ✅")
    elif 7.5 <= row['pH'] < 7.6 or 8.2 < row['pH'] <= 8.3:
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

    # Styling
    def color_alert(val):
        if val == "Critical 🔴":
            return "background-color: #FF0000; color: white; font-weight: bold"
        elif val == "Warning ⚠":
            return "background-color: #FFA500; color: black; font-weight: bold"
        elif val == "Normal ✅":
            return "background-color: #90EE90; color: black; font-weight: bold"
        return ""

    def color_ph(val):
        if val < 7.6 or val > 8.3:
            return "background-color: #FF0000"
        elif val < 7.6 or val > 8.2:
            return "background-color: #FF8000"
        return ""

    def color_salinity(val):
        if val < 25 or val > 30:
            return "background-color: #FF0000"
        elif val < 25 or val > 29:
            return "background-color: #FF8000"
        return ""

    def color_dead(val):
        if val > 5:
            return "background-color: #FF0000"
        elif val > 4:
            return "background-color: #FF8000"
        return ""

    st.subheader("Tank Risk & Alerts")
    st.dataframe(
        display_df.style
        .applymap(color_alert, subset=['Alert_Level'])
        .applymap(color_ph, subset=['pH'])
        .applymap(color_salinity, subset=['Salinity'])
        .applymap(color_dead, subset=['Dead Shrimp']),
        height=500
    )
else:
    st.info("No data available for selected filters.")




# action item dashboard
import streamlit as st
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import pandas as pd
from reportlab.pdfbase.pdfmetrics import stringWidth

def draw_wrapped_text(c, text, x, y, max_width, line_height=14):
    """
    Draws text in the PDF with wrapping if it exceeds max_width.
    Returns the updated y-coordinate after drawing.
    """
    words = text.split()
    line = ""
    for word in words:
        test_line = line + " " + word if line else word
        if stringWidth(test_line, c._fontname, c._fontsize) < max_width:
            line = test_line
        else:
            c.drawString(x, y, line)
            y -= line_height
            line = word
    if line:
        c.drawString(x, y, line)
        y -= line_height
    return y

# ==============================
# 1️⃣ Ensure dashboard dataframe exists
# ==============================
required_cols = ['Date','WorkerName','Tank','Block','pH','Salinity','WaterTemperature',
                 'DeadCount_day','DeadWeight_g','ScheduledFeed_day_g','ActualFeed_day_g',
                 'pH_OK','Salinity_OK']
for col in required_cols:
    if col not in view_df.columns:
        st.error(f"Missing column: {col}")
        st.stop()

# ==============================
# 2️⃣ Select Report Parameters
# ==============================
st.title("🦐 Shrimp Farm Dashboard – Executive Summary Report")
start_date = st.date_input("Start Date")
end_date = st.date_input("End Date")

# ==============================
# 3️⃣ Filter Data
# ==============================
filtered_df = view_df[
    (view_df['Date'] >= pd.to_datetime(start_date)) &
    (view_df['Date'] <= pd.to_datetime(end_date))
].copy()

if filtered_df.empty:
    st.warning("No data available for the selected date range.")
else:

    # -----------------------------
    # KPIs
    # -----------------------------
    total_feed_scheduled = filtered_df['ScheduledFeed_day_g'].sum() / 1000
    total_feed_actual = filtered_df['ActualFeed_day_g'].sum() / 1000
    total_leftover_feed = total_feed_scheduled - total_feed_actual
    total_mortality = filtered_df['DeadCount_day'].sum()
    initial_stock_estimate = 1000
    mortality_pct = (total_mortality / initial_stock_estimate) * 100
    ph_compliance = round(filtered_df['pH_OK'].mean()*100,1)
    salinity_compliance = round(filtered_df['Salinity_OK'].mean()*100,1)

    # -----------------------------
    # Worker Performance Summary (only Flora & Jimmy blocks)
    # -----------------------------
    Flora_blocks = ['H','I','J']
    jimmy_blocks = ['E','F','G']

    worker_df = filtered_df[filtered_df['Block'].str[0].isin(Flora_blocks + jimmy_blocks)].copy()

    worker_summary = (
        worker_df.groupby('WorkerName', as_index=False)
        .agg(
            ScheduledFeed_kg=('ScheduledFeed_day_g', lambda x: round(x.sum()/1000,2)),
            ActualFeed_kg=('ActualFeed_day_g', lambda x: round(x.sum()/1000,2)),
            Dead_Count=('DeadCount_day','sum'),
            Dead_Weight_g=('DeadWeight_g','sum'),
            pH_OK=('pH_OK','sum'),
            Salinity_OK=('Salinity_OK','sum'),
            Total_Records=('WorkerName','count'),
            Total_Blocks=('Block','nunique')
        )
    )
    worker_summary['pH_%'] = ((worker_summary['pH_OK']/worker_summary['Total_Records'])*100).round(1)
    worker_summary['Salinity_%'] = ((worker_summary['Salinity_OK']/worker_summary['Total_Records'])*100).round(1)
    worker_summary['Leftover_kg'] = (worker_summary['ScheduledFeed_kg'] - worker_summary['ActualFeed_kg']).round(2)
    worker_summary['Mortality_%'] = ((worker_summary['Dead_Count']/worker_summary['Total_Records'])*100).round(1)

    # -----------------------------
    # Tank/Block Risk Summary (all blocks)
    # -----------------------------
    def get_status(row):
        details = []
        # pH
        if 7.6 <= row['pH'] <= 8.3:
            details.append("✅")
        elif 7.6 <= row['pH'] < 7.6 or 8.3 < row['pH'] <= 8.4:
            details.append("⚠")
        else:
            details.append("🔴")
        # Salinity
        if 25 <= row['Salinity'] <= 30:
            details.append("✅")
        elif 24 <= row['Salinity'] < 25 or 30 < row['Salinity'] <= 31:
            details.append("⚠")
        else:
            details.append("🔴")
        # Temp
        if 28 <= row['WaterTemperature'] <= 30:
            details.append("✅")
        elif 27 <= row['WaterTemperature'] < 28 or 30 < row['WaterTemperature'] <= 31:
            details.append("⚠")
        else:
            details.append("🔴")
        # Mortality
        if row['DeadCount_day'] < 5:
            details.append("✅")
        elif 5 <= row['DeadCount_day'] <= 6:
            details.append("⚠")
        else:
            details.append("🔴")
        return details

    filtered_df[['pH_status','Sal_status','Temp_status','Mort_status']] = filtered_df.apply(lambda r: pd.Series(get_status(r)), axis=1)

    tank_summary = filtered_df.groupby(['WorkerName','Tank','Block']).agg({
        'pH_status':'max',
        'Sal_status':'max',
        'Temp_status':'max',
        'Mort_status':'max',
        'pH':'first',
        'Salinity':'first',
        'WaterTemperature':'first',
        'DeadCount_day':'first'
    }).reset_index()

    # Assign Worker Label for Tank/Block Risk Summary
    other_blocks = ['A','B','C','D','K']
    def assign_worker(block):
        if block[0] in Flora_blocks:
            return "Flora"
        elif block[0] in jimmy_blocks:
            return "Jimmy"
        else:
            return "Other"
    tank_summary['Worker_Label'] = tank_summary['Block'].apply(assign_worker)

    # -----------------------------
    # 4️⃣ Generate PDF
    # -----------------------------
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4

    # Title & Info
    c.setFont("Times-Bold", 18)
    c.drawCentredString(width/2, height-50, "🦐PJ Site Executive Summary Report🦐")
    c.setFont("Times-Roman", 12)
    c.drawString(50, height-80, f"Reporting Period: {start_date} to {end_date}")
    c.drawString(50, height-100, "Prepared By: Sai")
    c.drawString(50, height-120, "Data Source: Shrimp Farm Dashboard")

    # KPIs
    c.setFont("Times-Bold", 14)
    c.drawString(50, height-150, "1️⃣ Key KPIs")
    y = height-170
    for line in [
        f"Total Feed Scheduled: {total_feed_scheduled:.2f} kg",
        f"Total Feed Actual: {total_feed_actual:.2f} kg",
        f"Total Leftover Feed: {total_leftover_feed:.2f} kg",
        f"Total Mortality: {total_mortality} shrimps ({mortality_pct:.1f}%)",
        f"pH Compliance: {ph_compliance}%",
        f"Salinity Compliance: {salinity_compliance}%"
    ]:
        c.setFont("Times-Roman", 12)
        c.drawString(70, y, line)
        y -= 18

    # Worker Performance (Flora & Jimmy only)
    c.setFont("Times-Bold", 14)
    c.drawString(50, y-10, "2️⃣ Worker Performance Summary")
    y -= 30
    for _, row in worker_summary.iterrows():
        c.setFont("Times-Bold", 12)
        c.drawString(60, y, f"Worker: {row['WorkerName']}")
        y -= 18
        c.setFont("Times-Roman", 12)
        bullets = [
            f"• Scheduled Feed (kg): {row['ScheduledFeed_kg']}",
            f"• Actual Feed (kg): {row['ActualFeed_kg']}",
            f"• Leftover Feed (kg): {row['Leftover_kg']}",
            f"• Dead Count: {row['Dead_Count']}",
            f"• Dead Weight (g): {round(row['Dead_Weight_g'],2)}",
            f"• Mortality %: {row['Mortality_%']}%",
            f"• Blocks Managed: {row['Total_Blocks']}",
            f"• pH Compliance: {row['pH_%']}%",
            f"• Salinity Compliance: {row['Salinity_%']}%"
        ]
        for b in bullets:
            c.drawString(80, y, b)
            y -= 16
        y -= 8

    # Tank/Block Risk Summary by Worker_Label
    c.setFont("Times-Bold", 14)
    c.drawString(50, y-10, "3️⃣ Tank/Block Risk Summary")
    y -= 30

    for worker in ["Flora","Jimmy","Other"]:
        worker_df = tank_summary[tank_summary['Worker_Label']==worker]
        if not worker_df.empty:
            c.setFont("Times-Bold", 12)
            c.drawString(60, y, f"Worker: {worker}")
            y -= 18
            for _, t in worker_df.iterrows():
                x_pos = 80
                c.setFont("Times-Roman", 12)
                c.drawString(x_pos, y, f"• Tank/Block: {t['Tank']}/{t['Block']}")
                x_pos += 130

                colors_map = {"✅": colors.green, "⚠": colors.orange, "🔴": colors.red}
                symbol_spacing = 20
                label_spacing = 50

                for status, label in zip([t['pH_status'], t['Sal_status'], t['Temp_status'], t['Mort_status']],
                                         ["pH", "Salinity", "Temp", "Mortality"]):
                    c.setFont("Times-Bold", 12)
                    c.setFillColor(colors_map[status])
                    c.drawString(x_pos, y, status)
                    x_pos += symbol_spacing

                    c.setFont("Times-Roman", 12)
                    c.setFillColor(colors.black)
                    c.drawString(x_pos, y, label)
                    x_pos += label_spacing

                y -= 16
                if y < 100:
                    c.showPage()
                    y = height-50

    # Action Plan / Recommendations (all blocks)
    c.setFont("Times-Bold", 14)
    c.drawString(50, y-10, "4️⃣ Action Plan / Recommendations")
    y -= 30
    c.setFont("Times-Bold", 12)
    c.drawString(70, y, "Tank/Block")
    c.drawString(180, y, "Parameter")
    c.drawString(240, y, "Value")
    c.drawString(280, y, "Status")
    c.drawString(350, y, "Recommended Action")
    y -= 20
    c.setFont("Times-Roman", 12)

    for _, t in tank_summary.iterrows():
        for status, param, val in zip([t['pH_status'], t['Sal_status'], t['Temp_status'], t['Mort_status']],
                                     ["pH","Salinity","Temp","Mortality"],
                                     [t['pH'], t['Salinity'], t['WaterTemperature'], t['DeadCount_day']]):
            if status != "✅":
                c.drawString(70, y, f"{t['Tank']}/{t['Block']}")
                c.drawString(180, y, param)
                c.drawString(240, y, str(val))
                c.setFillColor(colors_map[status])
                c.drawString(280, y, status)
                c.setFillColor(colors.black)

                if param == "pH":
                    action = "Follow SOP: maintain pH between 7.6–8.3"
                elif param == "Salinity":
                    action = "Follow SOP: maintain salinity between 25–30 ppt"
                elif param == "Temp":
                    action = "Follow SOP: maintain temperature between 28–30°C"
                else:
                    action = "Follow SOP: investigate cause and monitor mortality"

                y = draw_wrapped_text(c, action, 350, y, max_width=200, line_height=16)

            if y < 100:
                c.showPage()
                y = height-50
                c.setFont("Times-Roman", 12)

    c.save()
    pdf_buffer.seek(0)

    st.success("✅ PDF generated successfully!")
    st.download_button(
        label="⬇️ Download Executive Summary PDF",
        data=pdf_buffer,
        file_name="PJ_Site_Executive_Summary.pdf",
        mime="application/pdf"
    )



# ==============================
# 🦐 Shrimp Farm Scorecard – Unified Streamlit App
# ==============================
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
from io import BytesIO
from fpdf import FPDF

# -----------------------------
# 1. KPI & TARGET CONFIGURATION
# -----------------------------
TARGET_FCR_MAX = 1.0
TARGET_SURVIVAL_MIN = 95.0
PH_MIN, PH_MAX = 7.6, 8.3
SALINITY_MIN, SALINITY_MAX = 25, 30

def get_target_weight(days):
    if days <= 30: return 2.0
    if days <= 60: return 8.0
    return 15.0

def assign_worker(block):
    Flora_blocks = ['H','I','J']
    jimmy_blocks = ['E','F','G']
    b = str(block).strip().upper()
    if not b: return "Other"
    if b[0] in Flora_blocks: return "Flora"
    elif b[0] in jimmy_blocks: return "Jimmy"
    else: return "Other"
    

# -----------------------------
# 2. DATA LOADING & AUTOMATIC ABW LOGIC
# -----------------------------
st.set_page_config(page_title="Shrimp Farm Hub", layout="wide")
st.title("🦐 Shrimp Farm Performance Scorecard")

abw_df = pd.DataFrame()
abw_file = r"C:\Users\123\Desktop\PJSite_Dashboard\data\daily_reports\ABW\AvgBW.xlsx"

try:
    if not os.path.exists(abw_file):
        st.error(f"ABW File not found: {abw_file}")
        st.stop()
        
    abw_df = pd.read_excel(abw_file)
    abw_df.columns = abw_df.columns.str.strip()
    
    # Standardize types
    abw_df['Block'] = abw_df['Block'].astype(str).str.strip().str.upper()
    abw_df['Tank'] = abw_df['Tank'].astype(str).str.strip().str.upper()
    abw_df['Date'] = pd.to_datetime(abw_df['Date'])
    
    # 1️⃣ CLEAN Avg Weight ONLY
    if 'Avg Weight' in abw_df.columns:
        abw_df['Avg Weight'] = pd.to_numeric(
            abw_df['Avg Weight'].astype(str).str.replace('g','',regex=False).replace('no shrimp','0'),
            errors='coerce'
        )

# -----------------------------
# 2️⃣ AUTOMATIC LOOK-BACK (Finding Start and End weights from Avg Weight only)
# -----------------------------
    abw_df = abw_df.sort_values(['Tank', 'Block', 'Date'])

# ABW_end = current date's Avg Weight
    abw_df['ABW_end'] = abw_df['Avg Weight']

# ABW_start = previous date's Avg Weight (per Tank/Block)
    abw_df['ABW_start'] = abw_df.groupby(['Tank','Block'])['Avg Weight'].shift(1)

# CV_pct (if S/M/L weights exist)
    if all(x in abw_df.columns for x in ['S-Weight','M-Weight','L-Weight']):
        for col in ['S-Weight', 'M-Weight', 'L-Weight']:
            abw_df[col] = pd.to_numeric(
                abw_df[col].astype(str).str.replace('g','',regex=False).replace('no shrimp','0'),
                errors='coerce'
            )
        abw_df['Est_SD'] = (abw_df['L-Weight'] - abw_df['S-Weight']) / 4
        abw_df['CV_pct'] = (abw_df['Est_SD'] / abw_df['ABW_end'] * 100).fillna(0)
    else:
        abw_df['CV_pct'] = 0

except Exception as e:
    st.error(f"ABW Excel Load Error: {e}")
    st.stop()

# Date Selectors
c1, c2 = st.columns(2)
with c1:
    start_date = st.date_input("Start Date", value=abw_df['Date'].min() if not abw_df.empty else datetime.today())
with c2:
    end_date = st.date_input("End Date", value=abw_df['Date'].max() if not abw_df.empty else datetime.today())

# -----------------------------
# 3. CORE PROCESSING (Restored Original Logic)
# -----------------------------
if 'view_df' in globals() and not abw_df.empty:
    view_df['Block'] = view_df['Block'].str.strip().str.upper()
    view_df['Tank'] = view_df['Tank'].str.strip().str.upper()
    view_df['Date'] = pd.to_datetime(view_df['Date'])
    
    for col in ['DeadWeight_g','ActualFeed_day_g','InitialCount','LiveCount']:
        view_df[col] = pd.to_numeric(view_df[col], errors='coerce').fillna(0)
    for col in ['pH','Salinity']:
        view_df[col] = pd.to_numeric(view_df[col], errors='coerce')

    days_elapsed = max((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days, 1)
    current_target_abw = get_target_weight(days_elapsed)

    # Filter daily logs
    filtered_df = view_df[(view_df['Date'] >= pd.to_datetime(start_date)) & 
                          (view_df['Date'] <= pd.to_datetime(end_date))].copy()
    
    if filtered_df.empty:
        st.warning("No data found for the selected date range.")
        st.stop()

    # Filter the automated ABW values for the selected range
    latest_abw = abw_df[(abw_df['Date'] >= pd.to_datetime(start_date)) & 
                   (abw_df['Date'] <= pd.to_datetime(end_date))].copy()
    latest_abw = latest_abw.sort_values(['Block', 'Tank', 'Date'])

    abw_summary = latest_abw.groupby(['Block','Tank']).agg(
        ABW_start=('Avg Weight', 'first'),
        ABW_end=('Avg Weight', 'last'),
        CV_pct=('CV_pct', 'last')
    ).reset_index()

    # MERGING (Your original logic, but including CV_pct for uneven growth)
    merged_df = filtered_df.merge(latest_abw[['Block','Tank','ABW_start','ABW_end','CV_pct']], on=['Block','Tank'], how='left')

    # Aggregation (Exactly as you requested)
    tank_df = merged_df.sort_values(['Block', 'Tank', 'Date']).groupby(['Block', 'Tank']).agg({
        'ABW_start': 'first',
        'ABW_end': 'last',
        'CV_pct': 'last',
        'InitialCount': 'first',
        'LiveCount': 'last',
        'ActualFeed_day_g': 'sum',
        'DeadWeight_g': 'sum',
        'pH': 'mean',
        'Salinity': 'mean'
    }).reset_index()

    # --- YOUR ORIGINAL TANK CALCULATIONS ---
    tank_df['Dead_Count'] = tank_df['InitialCount'] - tank_df['LiveCount']
    tank_df['Feed_kg'] = (tank_df['ActualFeed_day_g']/1000).round(2)
    tank_df['Biomass_start_kg'] = (tank_df['InitialCount'] * tank_df['ABW_start']/1000).round(2)
    tank_df['Biomass_kg'] = (tank_df['LiveCount'] * tank_df['ABW_end']/1000).round(2)
    tank_df['Weight_Gain_kg'] = (tank_df['Biomass_kg'] - tank_df['Biomass_start_kg']).round(2)
    tank_df['Weekly_Gain'] = (tank_df['ABW_end'] - tank_df['ABW_start']).round(3)
    tank_df['ADG (g/day)'] = (tank_df['Weekly_Gain'] / days_elapsed).round(3)
    tank_df['Survival_%'] = (tank_df['LiveCount'] / tank_df['InitialCount'].replace(0,1) * 100).round(2)
    tank_df['Worker'] = tank_df['Block'].apply(assign_worker)
    tank_df['FCR'] = np.where(tank_df['Weight_Gain_kg']>0, (tank_df['Feed_kg']/tank_df['Weight_Gain_kg']).round(2), 0)

    # Uneven Growth Logic Label
    def get_growth_status(cv):
        if pd.isna(cv) or cv == 0:
            return "–"          # No data / missing
        elif cv > 25:
            return "🚨 Uneven"  # High variation
        else:
            return "✅ Uniform" # Low variation
    tank_df['Growth_Status'] = tank_df['CV_pct'].apply(get_growth_status)

    # -----------------------------
    # 4. FARM CONSOLIDATED REPORT (Hidden Counts)
    # -----------------------------
    full_metric_list = ["ABW_start","ABW_end","Weekly_Gain","InitialCount","LiveCount",
                        "ActualFeed_day_g","DeadWeight_g","Dead_Count","DeadWeight_kg","Feed_kg",
                        "Biomass_start_kg","Biomass_kg","Weight_Gain_kg","ADG (g/day)","Survival %",
                        "FCR","Avg pH","Avg Salinity"]

    display_p_list = ["ABW_start","ABW_end","Weekly_Gain","ActualFeed_day_g","DeadWeight_g",
                      "Dead_Count","DeadWeight_kg","Feed_kg","Biomass_start_kg","Biomass_kg",
                      "Weight_Gain_kg","ADG (g/day)","Survival %","FCR","Avg pH","Avg Salinity"]

    total_gain = tank_df['Weight_Gain_kg'].sum()
    ov_fcr = round(tank_df['Feed_kg'].sum() / total_gain, 2) if total_gain > 0 else 0

    all_cons_vals = {
        "ABW_start": round(tank_df['ABW_start'].mean(), 2),
        "ABW_end": round(tank_df['ABW_end'].mean(), 2),
        "Weekly_Gain": round(tank_df['Weekly_Gain'].mean(), 3),
        "InitialCount": tank_df['InitialCount'].sum(),
        "LiveCount": tank_df['LiveCount'].sum(),
        "ActualFeed_day_g": tank_df['ActualFeed_day_g'].sum(),
        "DeadWeight_g": tank_df['DeadWeight_g'].sum(),
        "Dead_Count": tank_df['Dead_Count'].sum(),
        "DeadWeight_kg": round(tank_df['DeadWeight_g'].sum()/1000, 2),
        "Feed_kg": round(tank_df['Feed_kg'].sum(), 2),
        "Biomass_start_kg": round(tank_df['Biomass_start_kg'].sum(), 2),
        "Biomass_kg": round(tank_df['Biomass_kg'].sum(), 2),
        "Weight_Gain_kg": round(tank_df['Weight_Gain_kg'].sum(), 2),
        "ADG (g/day)": round(tank_df['ADG (g/day)'].mean(), 3),
        "Survival %": round(tank_df['Survival_%'].mean(), 2),
        "FCR": ov_fcr,
        "Avg pH": round(tank_df['pH'].mean(), 2),
        "Avg Salinity": round(tank_df['Salinity'].mean(), 1)
    }

    cons_vals = [all_cons_vals[m] for m in display_p_list]
    
    target_map = {
        "ABW_end": current_target_abw, "Survival %": TARGET_SURVIVAL_MIN, 
        "FCR": TARGET_FCR_MAX, "Avg pH": f"{PH_MIN}-{PH_MAX}", "Avg Salinity": f"{SALINITY_MIN}-{SALINITY_MAX}"
    }
    target_vals = [target_map.get(m, "-") for m in display_p_list]

    status_vals = [
        "YES" if m == "ABW_end" and all_cons_vals[m] >= current_target_abw else
        "YES" if m == "Survival %" and all_cons_vals[m] >= TARGET_SURVIVAL_MIN else
        "YES" if m == "FCR" and all_cons_vals[m] <= TARGET_FCR_MAX else
        "YES" if m == "Avg pH" and PH_MIN <= all_cons_vals[m] <= PH_MAX else
        "YES" if m == "Avg Salinity" and SALINITY_MIN <= all_cons_vals[m] <= SALINITY_MAX else
        "NO" if m in target_map else "-"
        for m in display_p_list
    ]

    consolidated_v = pd.DataFrame({"Metric": display_p_list, "Actual": cons_vals, "Target": target_vals, "Status": status_vals}).set_index("Metric")

    # -----------------------------
    # 5. WORKER SUMMARY (Hidden Counts)
    # -----------------------------
    worker_raw = tank_df.groupby('Worker').agg({
        'ABW_start':'mean','ABW_end':'mean','Weekly_Gain':'mean',
        'InitialCount':'sum', 'LiveCount':'sum', 'ActualFeed_day_g':'sum',
        'DeadWeight_g':'sum','Dead_Count':'sum','Feed_kg':'sum','Biomass_start_kg':'sum',
        'Biomass_kg':'sum','Weight_Gain_kg':'sum','ADG (g/day)':'mean','Survival_%':'mean','pH':'mean','Salinity':'mean'
    }).reset_index()

    w_dfs = []
    for _, row in worker_raw.iterrows():
        wfcr = round(row['Feed_kg']/row['Weight_Gain_kg'], 2) if row['Weight_Gain_kg'] > 0 else 0
        
        w_all_vals = {
            "ABW_start": round(row['ABW_start'], 2), "ABW_end": round(row['ABW_end'], 2),
            "Weekly_Gain": round(row['Weekly_Gain'], 3), "ActualFeed_day_g": round(row['ActualFeed_day_g'], 1),
            "DeadWeight_g": round(row['DeadWeight_g'], 1), "Dead_Count": row['Dead_Count'],
            "DeadWeight_kg": round(row['DeadWeight_g']/1000, 2), "Feed_kg": round(row['Feed_kg'], 2),
            "Biomass_start_kg": round(row['Biomass_start_kg'], 2), "Biomass_kg": round(row['Biomass_kg'], 2),
            "Weight_Gain_kg": round(row['Weight_Gain_kg'], 2), "ADG (g/day)": round(row['ADG (g/day)'], 3),
            "Survival %": round(row['Survival_%'], 2), "FCR": wfcr, "Avg pH": round(row['pH'], 2), "Avg Salinity": round(row['Salinity'], 1)
        }
        
        wvals = [w_all_vals[m] for m in display_p_list]
        wstat = [
            "YES" if m == "ABW_end" and w_all_vals[m] >= current_target_abw else
            "YES" if m == "Survival %" and w_all_vals[m] >= TARGET_SURVIVAL_MIN else
            "YES" if m == "FCR" and w_all_vals[m] <= TARGET_FCR_MAX else
            "YES" if m == "Avg pH" and PH_MIN <= w_all_vals[m] <= PH_MAX else
            "YES" if m == "Avg Salinity" and SALINITY_MIN <= w_all_vals[m] <= SALINITY_MAX else
            "NO" if m in target_map else "-"
            for m in display_p_list
        ]
        
        w_dfs.append(pd.DataFrame({"Metric": display_p_list, f"{row['Worker']} Act": wvals, f"{row['Worker']} Stat": wstat}).set_index("Metric"))

    worker_v = pd.concat(w_dfs, axis=1)


    # -----------------------------
    # 6. DASHBOARD DISPLAY
    # -----------------------------
    st.subheader("PJ Site Score Card")
    st.table(consolidated_v)
    st.subheader("Worker Summary")
    st.table(worker_v)
    
    # Detailed Tank view - we also drop the columns here for visual consistency
    st.subheader("Detailed Tank Scorecard")
    st.dataframe(tank_df.drop(columns=['InitialCount', 'LiveCount']), use_container_width=True)

   
    # -----------------------------
    # 7. EXCEL EXPORT
    # -----------------------------
    def to_excel(tank_df, worker_v, consolidated_v):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            tank_df.to_excel(writer, index=False, sheet_name='Tank_Detailed_Scorecard')
            worker_v.to_excel(writer, sheet_name='Worker_Summary')
            consolidated_v.to_excel(writer, sheet_name='Consolidated_Report')
        return output.getvalue()
    
    excel_file = to_excel(tank_df, worker_v, consolidated_v)
    st.download_button("📥 Download Excel Report", excel_file, f"Shrimp_Farm_Report_{end_date}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    # -----------------------------
    # 8. PDF EXPORT
    # -----------------------------
    def create_pdf(cons_df, worker_v_df, start_d, end_d):
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, txt="PJ Site Score Card", ln=True, align="C")
        pdf.set_font("Arial","",10)
        pdf.cell(0,5,txt=f"Period: {start_d} to {end_d}",ln=True,align="C")
        pdf.ln(5)

        # Consolidated Table
        pdf.set_font("Arial","B",10)
        pdf.set_fill_color(200,200,200)
        pdf.cell(60,8,"Metric",1,0,fill=True)
        pdf.cell(40,8,"Actual",1,0,align='C',fill=True)
        pdf.cell(40,8,"Target",1,0,align='C',fill=True)
        pdf.cell(40,8,"Status",1,1,align='C',fill=True)
        pdf.set_font("Arial","",9)
        for idx,row in cons_df.iterrows():
            pdf.cell(60,6,str(idx),1)
            pdf.cell(40,6,str(row['Actual']),1,0,'C')
            pdf.cell(40,6,str(row['Target']),1,0,'C')
            pdf.cell(40,6,str(row['Status']),1,1,'C')

        # Worker Table
        pdf.add_page()
        pdf.set_font("Arial","B",12)
        pdf.cell(0,10,"Worker Performance Summary",ln=True)
        col_w = 260/(len(worker_v_df.columns)+1)
        pdf.set_font("Arial","B",8)
        pdf.set_fill_color(200,200,200)
        pdf.cell(col_w,8,"Metric",1,0,fill=True)
        for col in worker_v_df.columns:
            pdf.cell(col_w,8,str(col),1,0,'C',fill=True)
        pdf.ln()
        pdf.set_font("Arial","",8)
        for idx,row in worker_v_df.iterrows():
            pdf.cell(col_w,6,str(idx),1)
            for val in row:
                pdf.cell(col_w,6,str(val),1,0,'C')
            pdf.ln()
        return pdf.output(dest='S').encode('latin-1')
    
    pdf_bytes = create_pdf(consolidated_v, worker_v, start_date, end_date)
    st.download_button("📄 Download PDF Report", pdf_bytes, "Farm_Report.pdf","application/pdf")
