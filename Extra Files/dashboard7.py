import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(page_title="Shrimp Farm Dashboard", layout="wide")

# ============================================================
# 1️⃣ COLUMN MAPPING
# ============================================================
column_mapping = {
    "Date": "Date",
    "Block": "Block",
    "Tank": "Tank",
    "Salinity": "Salinity",
    "pH": "pH",
    "Mortality_pct": "Mortality_pct",
    "ActualFeed_day_g": "ActualFeed_day_g",
    "ScheduledFeed_day_g": "ScheduledFeed_day_g",
    "DeadCount_day": "DeadCount_day",
    "Requires_Attention": "Requires_Attention"
}
required_columns = list(column_mapping.values())

# ============================================================
# 2️⃣ LOAD EXCEL FILE
# ============================================================
excel_file = "tank_block_consolidated_report_2025-12-03_colored.xlsx"
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
    week_ranges = ["All"] + [
        f"{ws.date()} - {(ws + pd.Timedelta(days=6)).date()}"
        for ws in df['Week_Start'].unique()
    ]
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
    view_df = view_df[view_df['Week_Start'] == wk_start]

# ------------------------------
# X-label and Data Reshaping Logic
# ------------------------------

if view_option == "Daily":
    # Daily → show individual dates
    view_df["X_label"] = view_df["Date"].dt.date

elif view_option == "Weekly" and selected_date != "All":
    # Weekly + SINGLE WEEK SELECTED → Show all 7 days of that week
    wk_start = pd.to_datetime(selected_date.split(" - ")[0])
    wk_end = wk_start + pd.Timedelta(days=6)

    # keep only 7 days inside that week
    view_df = view_df[(view_df["Date"] >= wk_start) & (view_df["Date"] <= wk_end)]

    # show DATE-wise trend
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

    # Keep Tank & Block in groupby → necessary for risk markers
    group_cols = ["Week_Start", "Block", "Tank"]

    # Use filtered view_df instead of df
    weekly_df = view_df.groupby(group_cols).agg(agg_cols).reset_index()

    weekly_df["Week_End"] = weekly_df["Week_Start"] + pd.Timedelta(days=6)

    weekly_df["X_label"] = (
        weekly_df["Week_Start"].dt.date.astype(str)
        + " - " +
        weekly_df["Week_End"].dt.date.astype(str)
    )

    # Replace view_df with aggregated weekly data
    view_df = weekly_df.copy()


# ------------------------------
# KPI Metrics
# ------------------------------
# Convert Feed to kg
view_df['ActualFeed_day_kg'] = (view_df['ActualFeed_day_g'] / 1000).round(2)
view_df['ScheduledFeed_day_kg'] = (view_df['ScheduledFeed_day_g'] / 1000).round(2)

# Calculate leftover feed
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
        if val < 7.7 or val > 8.2:
            return "red"
        elif val < 7.8 or val > 8.1:
            return "orange"
    elif metric == "Salinity":
        if val < 25 or val > 29:
            return "red"
        elif val < 26 or val > 28:
            return "orange"
    elif metric == "DeadCount_day":
        if val > 45:
            return "red"
        elif val > 40:
            return "orange"
    elif leftover:  # Leftover feed
        if val == 1:
            return "orange"
    return None

# ------------------------------
# Compute Risk Columns Safely
# ------------------------------
if not view_df.empty:
    if 'pH' in view_df.columns:
        view_df['pH_Risk'] = ((view_df['pH'] < 7.7) | (view_df['pH'] > 8.2)).astype(int)
    if 'Salinity' in view_df.columns:
        view_df['Salinity_Risk'] = ((view_df['Salinity'] < 25) | (view_df['Salinity'] > 29)).astype(int)
    if 'DeadCount_day' in view_df.columns:
        view_df['DeadCount_Risk'] = (view_df['DeadCount_day'] > 45).astype(int)
    if 'ScheduledFeed_day_g' in view_df.columns and 'ActualFeed_day_g' in view_df.columns:
        view_df['Feed_Risk'] = ((view_df['ScheduledFeed_day_g'] - view_df['ActualFeed_day_g']) > 0).astype(int)

# ------------------------------
# Prepare df_melt
# ------------------------------
metrics_all = ['Salinity', 'pH', 'ScheduledFeed_day_g', 'ActualFeed_day_g', 'DeadCount_day']
metrics_present = [m for m in metrics_all if m in view_df.columns]

if not view_df.empty and metrics_present:
    id_vars = ['X_label'] + [c for c in ['Tank', 'Block'] if c in view_df.columns]
    df_melt = view_df.melt(id_vars=id_vars,
                           value_vars=metrics_present,
                           var_name='Metric',
                           value_name='Value')

    # Remove spaces in Tank/Block if present
    if 'Tank' in df_melt.columns:
        df_melt['Tank'] = df_melt['Tank'].astype(str).str.strip()
    if 'Block' in df_melt.columns:
        df_melt['Block'] = df_melt['Block'].astype(str).str.strip()

    # ------------------------------
    # Plot Water Quality (Salinity & pH)
    # ------------------------------
    st.subheader("Water Quality (Salinity & pH)")

# Pick available metrics
metrics = [c for c in ["Salinity", "pH"] if c in view_df.columns]

if not view_df.empty and metrics:
    # Filter df_melt for only water quality metrics
    df_melt_metrics = df_melt[df_melt['Metric'].isin(metrics)].copy()

    # Ensure 'Tank' and 'Block' exist
    if 'Tank' not in df_melt_metrics.columns:
        df_melt_metrics['Tank'] = '-'
    if 'Block' not in df_melt_metrics.columns:
        df_melt_metrics['Block'] = '-'

    # Base line chart
    fig_water = px.line(
        df_melt_metrics,
        x="X_label",
        y="Value",
        color="Tank",  # safe because we ensured 'Tank' exists
        line_dash="Metric",
        markers=True,
        color_discrete_map=tank_colors,
        labels={"X_label": "Date/Week", "Value": "Value", "Metric": "Parameter", "Tank": "Tank"}
    )

    # Map colors to legend names
    color_to_name = {"red": "Risk 5", "orange": "Risk 4"}

    # Add risk markers for each metric
    for metric in metrics:
        # Filter for current metric
        df_metric = df_melt_metrics[df_melt_metrics['Metric'] == metric].copy()

        # Compute RiskColor for this metric
        df_metric['RiskColor'] = df_metric['Value'].apply(lambda v: get_risk_color(metric, v))

        # Filter points with risk
        risk_points = df_metric[df_metric['RiskColor'].notna()]

        # Add scatter markers split by color for legend
        for color in risk_points['RiskColor'].unique():
            subset = risk_points[risk_points['RiskColor'] == color]
            fig_water.add_scatter(
                x=subset['X_label'],
                y=subset['Value'],
                mode='markers',
                marker=dict(symbol='triangle-up', size=12, color=color),
                name=color_to_name.get(color, f"Risk ({color})"),
                customdata=subset[['Tank', 'Block']].to_numpy(),
                hovertemplate=(
                    "Date: %{x}<br>"
                    "Tank: %{customdata[0]}<br>"
                    "Block: %{customdata[1]}<br>"
                    f"{metric}: %{{y}}<br>"
                    f"Risk Score: {5 if color=='red' else 4 if color=='orange' else '-'}<extra></extra>"
                )
            )

    st.plotly_chart(fig_water, use_container_width=True)

else:
    st.info("No water quality data available.")


# ------------------------------
# Feed Trends
# ------------------------------
st.subheader("Feed Trends")

# Filter df_melt for feed metrics and ensure Tank/Block exist
df_feed = df_melt[df_melt['Metric'].isin(['ScheduledFeed_day_g', 'ActualFeed_day_g'])].copy()
if 'Tank' not in df_feed.columns:
    df_feed['Tank'] = '-'
if 'Block' not in df_feed.columns:
    df_feed['Block'] = '-'

if not df_feed.empty:
    fig_feed = px.line(
        df_feed,
        x='X_label',
        y='Value',
        color='Tank',
        line_dash='Metric',
        markers=True,
        color_discrete_map=tank_colors,
        labels={"X_label": "Date/Week", "Value": "Feed (g)", "Metric": "Parameter", "Tank": "Tank"}
    )

    # Leftover feed risk markers
    if 'Feed_Risk' in view_df.columns:
        risk_points = view_df[view_df['Feed_Risk'] == 1].copy()
        if not risk_points.empty:
            # Ensure Tank/Block exist
            for col in ['Tank','Block']:
                if col not in risk_points.columns:
                    risk_points[col] = '-'
            
            # Compute rounded leftover feed
            risk_points['LeftoverFeed'] = (risk_points['ScheduledFeed_day_g'] - risk_points['ActualFeed_day_g']).round(2)

            fig_feed.add_scatter(
                x=risk_points['X_label'],
                y=risk_points['ScheduledFeed_day_g'],
                mode='markers',
                marker=dict(symbol='triangle-up', size=12, color='orange'),  # always orange
                name="Risk 4",
                customdata=risk_points[['Tank','Block','ActualFeed_day_g','LeftoverFeed']].to_numpy(),
                hovertemplate=(
                    "Date: %{x}<br>"
                    "Tank: %{customdata[0]}<br>"
                    "Block: %{customdata[1]}<br>"
                    "Scheduled Feed: %{y}<br>"
                    "Actual Feed: %{customdata[2]}<br>"
                    "Leftover Feed: %{customdata[3]}<br>"
                    "Risk Score: 4<extra></extra>"
                )
            )

    st.plotly_chart(fig_feed, use_container_width=True)
else:
    st.info("No feed data available.")

# ------------------------------
# Mortality Trends
# ------------------------------
st.subheader("Mortality Trends")

# Filter df_melt for DeadCount_day and ensure Tank/Block exist
df_mort = df_melt[df_melt['Metric'] == 'DeadCount_day'].copy()
if 'Tank' not in df_mort.columns:
    df_mort['Tank'] = '-'
if 'Block' not in df_mort.columns:
    df_mort['Block'] = '-'

if not df_mort.empty:
    fig_mort = px.line(
        df_mort,
        x='X_label',
        y='Value',
        color='Tank',
        markers=True,
        color_discrete_map=tank_colors,
        labels={"X_label": "Date/Week", "Value": "Dead Count", "Tank": "Tank"}
    )

    # Add risk markers
    df_mort['RiskColor'] = df_mort['Value'].apply(lambda v: get_risk_color('DeadCount_day', v))
    risk_points = df_mort[df_mort['RiskColor'].notna()]
    
    color_to_name = {"red": "Risk 5", "orange": "Risk 4"}

    for color in risk_points['RiskColor'].unique():
        subset = risk_points[risk_points['RiskColor'] == color]
        fig_mort.add_scatter(
            x=subset['X_label'],
            y=subset['Value'],
            mode='markers',
            marker=dict(symbol='triangle-up', size=12, color=color),
            name=color_to_name.get(color, f"Risk ({color})"),
            customdata=subset[['Tank','Block']].to_numpy(),
            hovertemplate=(
                "Date: %{x}<br>"
                "Tank: %{customdata[0]}<br>"
                "Block: %{customdata[1]}<br>"
                "DeadCount: %{y}<br>"
                f"Risk Score: {5 if color=='red' else 4 if color=='orange' else '-'}<extra></extra>"
            )
        )

    st.plotly_chart(fig_mort, use_container_width=True)
else:
    st.info("No mortality data available.")

 # ------------------------------
# Risk Table
# ------------------------------
st.subheader("Risk Table (Individual Alerts)")

if not view_df.empty:
    risk_df = view_df.copy()

    # ------------------------------
    # Compute individual flags
    # ------------------------------
    risk_df['Feed_Leftover_Risk'] = (risk_df.get('ScheduledFeed_day_g', 0) - risk_df.get('ActualFeed_day_g', 0) > 0).astype(int)
    risk_df['DeadCount_Risk'] = (risk_df.get('DeadCount_day', 0) > 0).astype(int)

    # ------------------------------
    # Display columns
    # ------------------------------
    display_cols = ['X_label','pH','Salinity','DeadCount_day','ActualFeed_day_g','ScheduledFeed_day_g','Feed_Leftover_Risk']
    for col in ['Block','Tank']:
        if col in risk_df.columns:
            display_cols.insert(0, col)

    display_df = risk_df[display_cols]

    display_df = display_df.rename(columns={
        'X_label': 'Date/Week',
        'ActualFeed_day_g': 'Actual Feed (g)',
        'ScheduledFeed_day_g': 'Scheduled Feed (g)',
        'DeadCount_day': 'Dead Shrimp',
        'Feed_Leftover_Risk': 'Leftover Feed'
    })

    # ------------------------------
    # Individual coloring functions
    # ------------------------------
    def color_ph(val):
        if val < 7.7 or val > 8.2:  # high risk
            return "background-color: #FF0000"
        elif val < 7.8 or val > 8.1:  # medium risk
            return "background-color: #FF8000"
        return ""

    def color_salinity(val):
        if val < 25 or val > 29:
            return "background-color: #FF0000"
        elif val < 26 or val > 28:
            return "background-color: #FF8000"
        return ""

    def color_dead(val):
        if val > 45:  # example threshold for high dead count
            return "background-color: #FF0000"
        elif val > 40:
            return "background-color: #FF8000"
        return ""

    def color_feed(val):
        if val == 1:
            return "background-color: #FF0000"  # you can keep feed risk if needed
        return ""

    def color_leftover(val):
        if val == 1:
            return "background-color: #FFA500"  # leftover feed = orange
        return ""

    # ------------------------------
    # Apply coloring
    # ------------------------------
    st.dataframe(
        display_df.style
        .applymap(color_ph, subset=['pH'])
        .applymap(color_salinity, subset=['Salinity'])
        .applymap(color_dead, subset=['Dead Shrimp'])
        .applymap(color_feed, subset=['Actual Feed (g)'])
        .applymap(color_leftover, subset=['Leftover Feed']),
        height=500
    )
else:
    st.info("No data available for selected filters.")
