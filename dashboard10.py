import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Shrimp Farm Dashboard", layout="wide")

# ============================================================
# 1️⃣ COLUMN MAPPING
# ============================================================
column_mapping = {
    "Date": "Date",
    "Worker Name": "WorkerName",
    "Worker Name_water": "WorkerName_Water",
    "Block": "Block",
    "Tank No.": "Tank",
    "Scheduled Feed (g)": "ScheduledFeed_day_g",
    "Adjusted Feed (g)": "ActualFeed_day_g",
    "Leftover_g": "LeftoverFeed_g",
    "Leftover_pct": "Leftover_pct",
    "Dead Shrimp Count": "DeadCount_day",
    "Dead Shrimp Weight (g)": "DeadWeight_g",
    "InitialCount": "InitialCount",
    "LiveCount": "LiveCount",
    "Mortality_pct": "Mortality_pct",
    "Water Temperature": "WaterTemperature",
    "Room Temperature": "RoomTemperature",
    "Humidity": "Humidity",
    "Water condition (Y/N)": "WaterCondition",
    "Salinity (ppt)": "Salinity",
    "pH Value": "pH",
    "Aeration (OK)": "Aeration",
    "Water Circulation (Y/N)": "WaterCirculation",
    "Requires_Attention": "Requires_Attention",
    "Problem_Type": "Problem_Type"
}
required_columns = list(column_mapping.values())

# ============================================================
# 2️⃣ LOAD EXCEL FILE
# ============================================================
excel_file = "tank_block_consolidated_report_2025-12-11_colored.xlsx"
df = pd.read_excel(excel_file)
df = df.rename(columns=column_mapping)

# ============================================================
# 3️⃣ CHECK FOR MISSING COLUMNS
# ============================================================
missing = [c for c in required_columns if c not in df.columns]
if missing:
    st.error(f"❌ ERROR: Your Excel file is missing these required columns:\n\n{missing}")
    st.stop()

# ============================================================
# 4️⃣ PREPROCESSING
# ============================================================
df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
df = df.dropna(subset=['Date'])
df['Week_Start'] = df['Date'] - pd.to_timedelta(df['Date'].dt.weekday, unit='d')

# ------------------------------
# Sidebar Filters
# ------------------------------
st.sidebar.header("Filters")
blocks = ["All"] + list(df['Block'].dropna().unique())
selected_block = st.sidebar.selectbox("Select Block", blocks)
if selected_block == "All":
    tanks = ["All"] + list(df['Tank'].dropna().unique())
else:
    tanks = ["All"] + list(df[df['Block'] == selected_block]['Tank'].dropna().unique())
selected_tank = st.sidebar.selectbox("Select Tank", tanks)

view_option = st.sidebar.radio("View Mode", options=["Daily", "Weekly"])

if view_option == "Weekly":
    week_ranges = ["All"] + [f"{ws.date()} - {(ws + pd.Timedelta(days=6)).date()}" for ws in df['Week_Start'].unique()]
    selected_date = st.sidebar.selectbox("Select Week", week_ranges)
else:
    dates = ["All"] + [d.date() for d in df['Date'].unique()]
    selected_date = st.sidebar.selectbox("Select Date", dates)

# ------------------------------
# Filter dataframe
# ------------------------------
view_df = df.copy()
if selected_block != "All":
    view_df = view_df[view_df['Block'] == selected_block]
if selected_tank != "All":
    view_df = view_df[view_df['Tank'] == selected_tank]

if view_option == "Daily" and selected_date != "All":
    view_df = view_df[view_df['Date'].dt.date == selected_date]
elif view_option == "Weekly" and selected_date != "All":
    wk_start = pd.to_datetime(selected_date.split(" - ")[0])
    wk_end = wk_start + pd.Timedelta(days=6)
    view_df = view_df[(view_df["Date"] >= wk_start) & (view_df["Date"] <= wk_end)]

# ------------------------------
# X-label and Data Reshaping Logic
# ------------------------------
if view_option == "Daily":
    view_df["X_label"] = view_df["Date"].dt.date
elif view_option == "Weekly" and selected_date == "All":
    agg_cols = {
        "Salinity": "mean",
        "pH": "mean",
        "Mortality_pct": "mean",
        "DeadCount_day": "sum",
        "ActualFeed_day_g": "sum",
        "ScheduledFeed_day_g": "sum"
    }
    group_cols = ["Week_Start", "Block", "Tank"]
    weekly_df = view_df.groupby(group_cols).agg(agg_cols).reset_index()
    weekly_df["Week_End"] = weekly_df["Week_Start"] + pd.Timedelta(days=6)
    weekly_df["X_label"] = (weekly_df["Week_Start"].dt.date.astype(str) + " - " +
                             weekly_df["Week_End"].dt.date.astype(str))
    view_df = weekly_df.copy()

# ------------------------------
# KPI Metrics
# ------------------------------
view_df['ActualFeed_day_kg'] = (view_df['ActualFeed_day_g'] / 1000).round(2)
view_df['ScheduledFeed_day_kg'] = (view_df['ScheduledFeed_day_g'] / 1000).round(2)
view_df['LeftoverFeed_g'] = view_df['ScheduledFeed_day_g'] - view_df['ActualFeed_day_g']
view_df['LeftoverFeed_kg'] = (view_df['LeftoverFeed_g'] / 1000).round(2)

# ------------------------------
# Dashboard KPIs
# ------------------------------
st.title("🦐 Shrimp Farm Dashboard")
col1, col2, col3, col4, col5, col6 = st.columns(6)
feed_data = view_df[view_df['ActualFeed_day_g'] > 0] if not view_df.empty else pd.DataFrame()
mortality_data = view_df[view_df['Mortality_pct'] > 0] if not view_df.empty else pd.DataFrame()

if not view_df.empty:
    if view_option == "Daily":
        col1.metric("Feed (g)", round(feed_data['ActualFeed_day_g'].sum(), 2))
        col2.metric("Feed (kg)", round(feed_data['ActualFeed_day_kg'].sum(), 2))
        col3.metric("Leftover Feed (g)", round(view_df['LeftoverFeed_g'].sum(), 2))
        col4.metric("Leftover Feed (kg)", round(view_df['LeftoverFeed_kg'].sum(), 2))
        col5.metric("Mortality %", round(mortality_data['Mortality_pct'].mean() * 100, 2) if not mortality_data.empty else 0)
        col6.metric("DeadCount", int(feed_data['DeadCount_day'].sum()))
    else:
        col1.metric("Weekly Feed (g)", round(feed_data['ActualFeed_day_g'].sum(), 2))
        col2.metric("Weekly Feed (kg)", round(feed_data['ActualFeed_day_kg'].sum(), 2))
        col3.metric("Weekly Leftover Feed (g)", round(view_df['LeftoverFeed_g'].sum(), 2))
        col4.metric("Weekly Leftover Feed (kg)", round(view_df['LeftoverFeed_kg'].sum(), 2))
        col5.metric("Weekly Avg Mortality %", round(mortality_data['Mortality_pct'].mean() * 100, 2) if not mortality_data.empty else 0)
        col6.metric("Weekly DeadCount", int(feed_data['DeadCount_day'].sum()))
else:
    col1.metric("Feed (g)", "No Data")
    col2.metric("Feed (kg)", "No Data")
    col3.metric("Leftover Feed (g)", "No Data")
    col4.metric("Leftover Feed (kg)", "No Data")
    col5.metric("Mortality %", "No Data")
    col6.metric("DeadCount", "No Data")

# ------------------------------
# Tank colors
# ------------------------------
tank_colors = {"T3": "purple", "T4": "darkblue", "T5": "green"}

# ------------------------------
# Risk color function
# ------------------------------
def get_risk_color(metric, val, leftover=False):
    if metric == "pH":
        if val < 7.7 or val > 8.0:
            return "red"
        elif val < 7.8 or val > 7.9:
            return "orange"
    elif metric == "Salinity":
        if val < 25 or val > 30:
            return "red"
        elif val < 26 or val > 29:
            return "orange"
    elif metric == "DeadCount_day":
        if val > 5:
            return "red"
        elif val > 4:
            return "orange"
    elif leftover:
        if val == 1:
            return "orange"
    return None

# ============================================================
# 5️⃣ MELT DATA FOR PLOTTING
# ============================================================
metrics_all = ['Salinity', 'pH', 'ScheduledFeed_day_g', 'ActualFeed_day_g', 'DeadCount_day']
metrics_present = [m for m in metrics_all if m in view_df.columns]

if not view_df.empty and metrics_present:
    id_vars = ['X_label'] + [c for c in ['Tank', 'Block', 'WorkerName', 'WorkerName_Water'] if c in view_df.columns]
    df_melt = view_df.melt(id_vars=id_vars, value_vars=metrics_present, var_name='Metric', value_name='Value')
    for col in ['Tank','Block','WorkerName','WorkerName_Water']:
        if col in df_melt.columns:
            df_melt[col] = df_melt[col].astype(str).str.strip()

# ============================================================
# ⭐ DAILY & WEEKLY WATER COMPLIANCE CALCULATION
# ============================================================
# Define acceptable ranges
ph_min, ph_max = 7.7, 8.0
sal_min, sal_max = 25, 30

# Default percentages
ph_percentage = 0.0
sal_percentage = 0.0
ph_total_count = 0
sal_total_count = 0

if not view_df.empty:
    # pH Compliance
    if "pH" in view_df.columns:
        ph_total_count = view_df["pH"].notna().sum()
        ph_valid_count = view_df[(view_df["pH"] >= ph_min) & (view_df["pH"] <= ph_max)].shape[0]
        ph_percentage = (ph_valid_count / ph_total_count * 100) if ph_total_count > 0 else 0.0

    # Salinity Compliance
    if "Salinity" in view_df.columns:
        sal_total_count = view_df["Salinity"].notna().sum()
        sal_valid_count = view_df[(view_df["Salinity"] >= sal_min) & (view_df["Salinity"] <= sal_max)].shape[0]
        sal_percentage = (sal_valid_count / sal_total_count * 100) if sal_total_count > 0 else 0.0

# ============================================================
# ⭐ DISPLAY COMPLIANCE ABOVE WATER QUALITY GRAPH
# ============================================================
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    <div style="background-color:#f2f2f2; padding:14px; border-radius:8px; text-align:center; box-shadow:0px 1px 4px rgba(0,0,0,0.06);">
        <h4 style="margin:0 0 6px 0;">📌 pH Compliance</h4>
        <p style="font-size:26px; margin:0;"><b>{ph_percentage:.1f}%</b></p>
        <p style="font-size:12px; color:#666; margin-top:6px;">Range: {ph_min} – {ph_max}</p>
        <p style="font-size:11px; color:#888; margin-top:4px;">(valid {int(ph_total_count)} readings)</p>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div style="background-color:#f2f2f2; padding:14px; border-radius:8px; text-align:center; box-shadow:0px 1px 4px rgba(0,0,0,0.06);">
        <h4 style="margin:0 0 6px 0;">📌 Salinity Compliance</h4>
        <p style="font-size:26px; margin:0;"><b>{sal_percentage:.1f}%</b></p>
        <p style="font-size:12px; color:#666; margin-top:6px;">Range: {sal_min} – {sal_max}</p>
        <p style="font-size:11px; color:#888; margin-top:4px;">(valid {int(sal_total_count)} readings)</p>
    </div>
    """, unsafe_allow_html=True)
#------Water quality--------#

st.subheader("Water Quality (Salinity & pH)")

metrics = [c for c in ["Salinity", "pH"] if c in view_df.columns]

if not view_df.empty and metrics:
    df_temp = view_df.copy()
    
    # --- DAILY MODE ---
    if view_option == "Daily":
        df_temp["X_label"] = df_temp["Block"].astype(str) + " | " + df_temp["Tank"].astype(str)
    
    # --- WEEKLY MODE ---
    elif view_option == "Weekly":
        # Use selected week range or all weeks
        if selected_date != "All":
            wk_start = pd.to_datetime(selected_date.split(" - ")[0])
            wk_end = pd.to_datetime(selected_date.split(" - ")[1])
            df_temp = df_temp[(df_temp["Date"] >= wk_start) & (df_temp["Date"] <= wk_end)].copy()
        # Ensure Date column is datetime
        df_temp["Date"] = pd.to_datetime(df_temp["Date"], errors="coerce")
        df_temp["X_label"] = df_temp["Date"].dt.date.astype(str) + " | " + df_temp["Block"].astype(str) + " | " + df_temp["Tank"].astype(str)
    
    df_plot = df_temp.melt(
        id_vars=["X_label", "Tank", "Block", "WorkerName_Water"],
        value_vars=metrics,
        var_name="Metric",
        value_name="Value"
    )

    # Ensure required columns exist
    for col in ["Tank", "Block", "WorkerName_Water"]:
        if col in df_plot.columns:
            df_plot[col] = df_plot[col].astype(str).str.strip()
        else:
            df_plot[col] = "Unknown"

    # Plot
    fig_water = px.line(
        df_plot,
        x="X_label",
        y="Value",
        color="Tank",
        line_dash="Metric",
        markers=True,
        color_discrete_map=tank_colors,
        labels={"X_label":"Block | Tank", "Value":"Value", "Metric":"Parameter", "Tank":"Tank"},
        hover_data={
            "Tank": True,
            "Block": True,
            "Metric": True,
            "Value": True,
            "WorkerName_Water": True,
        }
    )

    # Add RISK markers
    color_to_name = {"red": "Risk 5", "orange": "Risk 4"}

    for metric in metrics:
        df_metric = df_plot[df_plot["Metric"] == metric].copy()
        df_metric["RiskColor"] = df_metric["Value"].apply(lambda v: get_risk_color(metric, v))
        risk_points = df_metric[df_metric["RiskColor"].notna()]

        for color in risk_points["RiskColor"].unique():
            subset = risk_points[risk_points["RiskColor"] == color]
            fig_water.add_scatter(
                x=subset["X_label"],
                y=subset["Value"],
                mode="markers",
                marker=dict(symbol="triangle-up", size=12, color=color),
                name=color_to_name.get(color, f"Risk ({color})"),
                customdata=subset[["Tank", "Block", "WorkerName_Water"]].to_numpy(),
                hovertemplate=(
                    "Block | Tank: %{x}<br>"
                    "Metric: %{customdata[2]}<br>"
                    f"{metric}: %{{y}}<br>"
                    "Tank: %{customdata[0]}<br>"
                    "Block: %{customdata[1]}<br>"
                    "Worker: %{customdata[2]}<br>"
                    f"Risk Score: " + ("5" if color=="red" else "4") + "<extra></extra>"
                )
            )

    st.plotly_chart(fig_water, use_container_width=True)
else:
    st.info("No water quality data available.")


#--------Feed trends-----------#
st.subheader("Feed Trends")

df_feed = df_melt[df_melt['Metric'].isin(['ScheduledFeed_day_g','ActualFeed_day_g'])].copy()
if 'WorkerName' not in df_feed.columns:
    df_feed['WorkerName'] = 'Unknown'
for col in ['Tank','Block']:
    if col not in df_feed.columns:
        df_feed[col] = '-'

if not df_feed.empty:
    # X-axis as Block | Tank or Date | Block | Tank for weekly
    if view_option == "Daily":
        df_feed["X_label"] = df_feed["Block"].astype(str) + " | " + df_feed["Tank"].astype(str)
    elif view_option == "Weekly":
        df_feed["X_label"] = df_feed["Date"].dt.date.astype(str) + " | " + df_feed["Block"].astype(str) + " | " + df_feed["Tank"].astype(str)

    fig_feed = px.line(
        df_feed,
        x='X_label',
        y='Value',
        color='Tank',
        line_dash='Metric',
        markers=True,
        color_discrete_map=tank_colors,
        labels={"X_label":"Block | Tank","Value":"Feed (g)","Metric":"Parameter","Tank":"Tank"},
        hover_data={"Tank": True,"Block": True,"Metric": True,"Value": True,"WorkerName": True}
    )

    # Leftover Feed Risk
    if 'ScheduledFeed_day_g' in view_df.columns and 'ActualFeed_day_g' in view_df.columns:
        view_df['Feed_Risk'] = ((view_df['ScheduledFeed_day_g'] - view_df['ActualFeed_day_g'])>0).astype(int)
        risk_points = view_df[view_df['Feed_Risk']==1].copy()
        if not risk_points.empty:
            for col in ['Tank','Block','WorkerName']:
                if col not in risk_points.columns:
                    risk_points[col] = 'Unknown'
            risk_points['LeftoverFeed'] = (risk_points['ScheduledFeed_day_g'] - risk_points['ActualFeed_day_g']).round(2)
            if view_option == "Daily":
                risk_points["X_label"] = risk_points["Block"].astype(str) + " | " + risk_points["Tank"].astype(str)
            elif view_option == "Weekly":
                
                risk_points["X_label"] = risk_points["Date"].dt.date.astype(str) + " | " + risk_points["Block"].astype(str) + " | " + risk_points["Tank"].astype(str)

            fig_feed.add_scatter(
                x=risk_points['X_label'],
                y=risk_points['ScheduledFeed_day_g'],
                mode='markers',
                marker=dict(symbol='triangle-up', size=12, color='orange'),
                name="Risk 4",
                customdata=risk_points[['Tank','Block','WorkerName','ActualFeed_day_g','LeftoverFeed']].to_numpy(),
                hovertemplate=(
                    "Block | Tank: %{x}<br>"
                    "Scheduled Feed: %{y}<br>"
                    "Actual Feed: %{customdata[3]}<br>"
                    "Leftover Feed: %{customdata[4]}<br>"
                    "Risk Score: 4<br>"
                    "Worker: %{customdata[2]}<extra></extra>"
                )
            )

    st.plotly_chart(fig_feed,use_container_width=True)
else:
    st.info("No feed data available.")


# ============================================================
# 8️⃣ MORTALITY TRENDS
# ============================================================
st.subheader("Mortality Trends")
required_cols = ['X_label','DeadCount_day','WorkerName_Water']
if all(col in view_df.columns for col in required_cols):
    df_mort = view_df[required_cols].copy()
    if not df_mort.empty:
        # For weekly, create X_label per day if needed
        if view_option == "Weekly":
            df_mort["X_label"] = df_mort["Date"].dt.date.astype(str) + " | " + df_mort["Block"].astype(str) + " | " + df_mort["Tank"].astype(str)
        
        df_total = df_mort.groupby('X_label').agg(
            TotalDead=('DeadCount_day','sum'),
            Workers=('WorkerName_Water', lambda x: ', '.join(x.dropna().unique()))
        ).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_total['X_label'],
            y=df_total['TotalDead'],
            name='Total Dead Shrimp',
            marker_color='lightblue',
            text=df_total['TotalDead'],
            textposition='outside',
            customdata=df_total['Workers'],
            hovertemplate="Date: %{x}<br>Total Dead Shrimp: %{y}<br>Workers: %{customdata}<extra></extra>"
        ))

        fig.add_trace(go.Scatter(
            x=df_total['X_label'],
            y=df_total['TotalDead'],
            mode='markers',
            marker=dict(symbol='circle', size=10, color='blue'),
            name='Total Count',
            customdata=df_total['Workers'],
            hovertemplate="Date: %{x}<br>Total Dead Shrimp: %{y}<br>Workers: %{customdata}<extra></extra>"
        ))

        max_dead = df_total['TotalDead'].max()
        tick_step = 5
        fig.update_yaxes(title_text="Dead Shrimp", tickvals=list(range(0, int(max_dead)+tick_step, tick_step)))
        fig.update_layout(barmode='group', xaxis_title="Date/Week", yaxis_title="Dead Shrimp", hovermode='closest')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No mortality data available for selected filters.")
else:
    missing = [c for c in required_cols if c not in view_df.columns]
    st.warning(f"Required columns missing: {', '.join(missing)}")

# ============================================================
# 9️⃣ TEMPERATURE & HUMIDITY GRAPHS — DAILY + WEEKLY (per tank)
# ============================================================
st.subheader("Temperature & Humidity Trends")

# Column mapping
metric_map = {
    "Water Temperature": "WaterTemperature",
    "Room Temperature": "RoomTemperature",
    "Humidity": "Humidity",
    "Worker Name_water": "WorkerName_Water"
}

metrics_temp = [v for k,v in metric_map.items() if v in view_df.columns]

if not view_df.empty and metrics_temp:
    df_temp_plot = view_df.copy()
    
    # Ensure WorkerName_Water exists
    if "WorkerName_Water" not in df_temp_plot.columns:
        df_temp_plot["WorkerName_Water"] = "Unknown"
    else:
        df_temp_plot["WorkerName_Water"] = df_temp_plot["WorkerName_Water"].fillna("Unknown")

    # Create X_label depending on view
    if view_option == "Daily":
        df_temp_plot["X_label"] = df_temp_plot["Block"].astype(str) + " | " + df_temp_plot["Tank"].astype(str)
        df_plot = df_temp_plot.melt(
            id_vars=["X_label","Tank","Block","WorkerName_Water"],
            value_vars=metrics_temp,
            var_name="Metric",
            value_name="Value"
        )

    elif view_option == "Weekly":
        # Create weekly range label for each date
        df_temp_plot["Week"] = df_temp_plot["Date"].dt.to_period("W").apply(lambda r: f"{r.start_time.date()} - {r.end_time.date()}")
        df_plot = df_temp_plot.melt(
            id_vars=["Week","Tank","Block","WorkerName_Water"],
            value_vars=metrics_temp,
            var_name="Metric",
            value_name="Value"
        )
        # Aggregate per tank, block, worker, metric
        df_plot = df_plot.groupby(["Week","Tank","Block","WorkerName_Water","Metric"], as_index=False).agg({"Value":"mean"})
        df_plot = df_plot.rename(columns={"Week":"X_label"})

    # Replace metric column with friendly names
    df_plot["Metric"] = df_plot["Metric"].map({v:k for k,v in metric_map.items()})

    # Plot line graph
    fig_temp = px.line(
        df_plot,
        x="X_label",
        y="Value",
        color="Tank",
        line_dash="Metric",
        markers=True,
        labels={"X_label":"Block | Tank / Week","Value":"Value","Metric":"Parameter","Tank":"Tank"},
        hover_data={"Tank":True,"Block":True,"Metric":True,"Value":True,"WorkerName_Water":True}
    )

    st.plotly_chart(fig_temp,use_container_width=True)
else:
    st.info("No temperature or humidity data available.")


# -------------------------------
# 1️⃣ Survival & Mortality Rate (%)
# -------------------------------
view_df['Survival_pct'] = (view_df['LiveCount'] / view_df['InitialCount'] * 100).round(2)
view_df['Mortality_pct'] = (100 - view_df['Survival_pct']).round(2)

# -------------------------------
# 2️⃣ Feed Efficiency (%)
# -------------------------------
# Cap actual feed to scheduled feed for performance calculation
view_df['FeedUsedForScore'] = view_df[['ActualFeed_day_g', 'ScheduledFeed_day_g']].min(axis=1)
view_df['FeedEfficiency_pct'] = (view_df['FeedUsedForScore'] / view_df['ScheduledFeed_day_g'] * 100).round(2)

# -------------------------------
# 3️⃣ Water Scores (Salinity & pH)
# -------------------------------
def get_salinity_score(val):
    if 25 <= val <= 30:
        return 100
    elif 23 <= val < 25 or 30 < val <= 33:  # slightly outside ideal range
        return 80
    else:
        return 50

def get_ph_score(val):
    if 7.7 <= val <= 8.0:
        return 100
    elif 7.5 <= val < 7.7 or 8.0 < val <= 8.2:  # slightly outside ideal range
        return 80
    else:
        return 50


view_df['SalinityScore'] = view_df['Salinity'].apply(get_salinity_score)
view_df['PHScore'] = view_df['pH'].apply(get_ph_score)

# -------------------------------
# 4️⃣ Overall Performance (%)
# -------------------------------
view_df['OverallPerformance_pct'] = (
    view_df[['Survival_pct','FeedEfficiency_pct','SalinityScore','PHScore']].mean(axis=1)
).round(2)

# -------------------------------
# 5️⃣ Performance Table
# -------------------------------
# Choose daily or weekly view
view_option = st.selectbox("Select View Option", ["Daily", "Weekly"])

if view_option == "Daily":
    performance_table = view_df[[
        'Date','Block','Tank','WorkerName','WorkerName_Water',
        'Survival_pct','Mortality_pct','FeedEfficiency_pct','SalinityScore','PHScore','OverallPerformance_pct'
    ]]

elif view_option == "Weekly":
    # Create week label: e.g., "Week 50, 2025"
    view_df['Week'] = view_df['Date'].dt.isocalendar().week.astype(str) + ", " + view_df['Date'].dt.year.astype(str)

    # Aggregate metrics weekly by Block & Tank
    performance_table = view_df.groupby(['Week','Block','Tank'], as_index=False).agg(
        Survival_pct=('Survival_pct','mean'),
        Mortality_pct=('Mortality_pct','mean'),
        FeedEfficiency_pct=('FeedEfficiency_pct','mean'),
        SalinityScore=('SalinityScore','mean'),
        PHScore=('PHScore','mean'),
        OverallPerformance_pct=('OverallPerformance_pct','mean')
    ).round(2)

    # Optional: you can include worker names by joining unique names per week
    performance_table['Workers'] = view_df.groupby(['Week','Block','Tank'])['WorkerName_Water'].apply(lambda x: ', '.join(x.dropna().unique())).values

# Optional: sort by overall performance
performance_table = performance_table.sort_values(by='OverallPerformance_pct', ascending=False)

# Display table
st.subheader("Block & Tank Performance Summary")
st.dataframe(performance_table)



# ============================================================
# 9️⃣ RISK TABLE
# ============================================================
if 'X_label' not in view_df.columns:
    view_df['X_label'] = view_df['Date'].dt.date  # Daily fallback

if 'ScheduledFeed_day_g' in view_df.columns and 'ActualFeed_day_g' in view_df.columns:
    view_df['Feed_Risk'] = ((view_df['ScheduledFeed_day_g'] - view_df['ActualFeed_day_g']) > 0).astype(int)
if 'DeadCount_day' in view_df.columns:
    view_df['DeadCount_Risk'] = (view_df['DeadCount_day'] > 45).astype(int)
if 'pH' in view_df.columns:
    view_df['pH_Risk'] = ((view_df['pH'] < 7.6) | (view_df['pH'] > 8.0)).astype(int)
if 'Salinity' in view_df.columns:
    view_df['Salinity_Risk'] = ((view_df['Salinity'] < 25) | (view_df['Salinity'] > 29)).astype(int)

risk_display_cols = [
    'X_label', 'Block', 'Tank', 'pH', 'Salinity', 'DeadCount_day', 'ScheduledFeed_day_g', 'ActualFeed_day_g', 'Feed_Risk'
]

if not view_df.empty:
    display_df = view_df[risk_display_cols].rename(columns={
        'X_label': 'Date/Week',
        'ScheduledFeed_day_g': 'Scheduled Feed (g)',
        'ActualFeed_day_g': 'Actual Feed (g)',
        'DeadCount_day': 'Dead Shrimp',
        'Feed_Risk': 'Leftover Feed'
    })

    def color_ph(val):
        if val < 7.7 or val > 8.0: return "background-color: #FF0000"
        elif val < 7.6 or val > 7.9: return "background-color: #FF8000"
        return ""
    def color_salinity(val):
        if val < 25 or val > 30: return "background-color: #FF0000"
        elif val < 26 or val > 29: return "background-color: #FF8000"
        return ""
    def color_dead(val):
        if val > 5: return "background-color: #FF0000"
        elif val > 4: return "background-color: #FF8000"
        return ""
    def color_feed(val):
        if val == 1: return "background-color: #FFA500"
        return ""

    st.dataframe(
        display_df.style
        .applymap(color_ph, subset=['pH'])
        .applymap(color_salinity, subset=['Salinity'])
        .applymap(color_dead, subset=['Dead Shrimp'])
        .applymap(color_feed, subset=['Leftover Feed']),
        height=500
    )
else:
    st.info("No data available for selected filters.")
