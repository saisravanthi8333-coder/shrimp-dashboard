import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="🦐 Shrimp Farm Dashboard", layout="wide")

# ------------------------------
# 1️⃣ COLUMN MAPPING
# ------------------------------
column_mapping = {
    "Date": "Date",
    "Block": "Block",
    "Tank": "Tank",
    "Salinity": "Salinity",
    "pH": "pH",
    "Mortality_pct": "Mortality_pct",
    "ActualFeed_day_g": "ActualFeed_day_g",
    "ScheduledFeed_day_g": "ScheduledFeed_day_g",
    "DeadCount_day": "DeadCount_day"
}
required_columns = list(column_mapping.values())

# ------------------------------
# 2️⃣ LOAD DATA
# ------------------------------
excel_file = "tank_block_consolidated_report_2025-12-03_colored.xlsx"
df = pd.read_excel(excel_file)
df = df.rename(columns=column_mapping)

missing = [c for c in required_columns if c not in df.columns]
if missing:
    st.error(f"❌ ERROR: Missing columns:\n{missing}")
    st.stop()

df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
df = df.dropna(subset=['Date'])
df['Week_Start'] = df['Date'] - pd.to_timedelta(df['Date'].dt.weekday, unit='d')

# ------------------------------
# 3️⃣ SIDEBAR FILTERS
# ------------------------------
st.sidebar.header("Filters")

blocks = ["All"] + list(df['Block'].dropna().unique())
selected_block = st.sidebar.selectbox("Select Block", blocks)

if selected_block == "All":
    tanks = ["All"] + list(df['Tank'].dropna().unique())
else:
    tanks = ["All"] + list(df[df['Block'] == selected_block]['Tank'].dropna().unique())
selected_tank = st.sidebar.selectbox("Select Tank", tanks)

view_option = st.sidebar.radio("View Mode", ["Daily", "Weekly"])

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
# 4️⃣ FILTER DATA
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

if view_option == "Daily":
    view_df["X_label"] = view_df["Date"].dt.date
else:
    view_df["X_label"] = (
        view_df["Week_Start"].dt.date.astype(str) + " - " +
        (view_df["Week_Start"] + pd.Timedelta(days=6)).dt.date.astype(str)
    )

# ------------------------------
# 5️⃣ KPI METRICS
# ------------------------------
st.title("🦐 Shrimp Farm Dashboard")
col1, col2, col3 = st.columns(3)

feed_data = view_df[view_df['ActualFeed_day_g'] > 0] if not view_df.empty else pd.DataFrame()
mortality_data = view_df[view_df['Mortality_pct'] > 0] if not view_df.empty else pd.DataFrame()

if not view_df.empty:
    if view_option == "Daily":
        col1.metric("Feed (g)", round(feed_data['ActualFeed_day_g'].sum(), 2))
        col2.metric("Mortality %", round(mortality_data['Mortality_pct'].mean() * 100, 2) if not mortality_data.empty else 0)
        col3.metric("DeadCount", int(feed_data['DeadCount_day'].sum()))
    else:
        col1.metric("Weekly Feed (g)", round(feed_data['ActualFeed_day_g'].sum(), 2))
        col2.metric("Weekly Avg Mortality %", round(mortality_data['Mortality_pct'].mean() * 100, 2) if not mortality_data.empty else 0)
        col3.metric("Weekly DeadCount", int(feed_data['DeadCount_day'].sum()))
else:
    col1.metric("Feed (g)", "No Data")
    col2.metric("Mortality %", "No Data")
    col3.metric("DeadCount", "No Data")

# ------------------------------
# 6️⃣ WATER QUALITY GRAPH
# ------------------------------
st.subheader("Water Quality (Salinity & pH)")

if not view_df.empty:
    fig_water = go.Figure()
    tanks_list = view_df['Tank'].unique()
    colors = px.colors.qualitative.Set1

    for i, tank in enumerate(tanks_list):
        df_tank = view_df[view_df['Tank'] == tank]
        # Salinity line
        fig_water.add_trace(go.Scatter(
            x=df_tank['X_label'], y=df_tank['Salinity'], mode='lines+markers',
            name=f"Salinity - {tank}", line=dict(color=colors[i % len(colors)], width=2)
        ))
        # pH line
        fig_water.add_trace(go.Scatter(
            x=df_tank['X_label'], y=df_tank['pH'], mode='lines+markers',
            name=f"pH - {tank}", line=dict(color=colors[i % len(colors)], width=2, dash='dot')
        ))
        # Salinity alerts
        alert_s = df_tank[(df_tank['Salinity'] < 26) | (df_tank['Salinity'] > 28)]
        fig_water.add_trace(go.Scatter(
            x=alert_s['X_label'], y=alert_s['Salinity'], mode='markers',
            marker=dict(symbol='triangle-up', color='red', size=12),
            name=f"Salinity Alert - {tank}", showlegend=True
        ))
        # pH alerts
        alert_pH = df_tank[(df_tank['pH'] < 7.8) | (df_tank['pH'] > 8.0)]
        fig_water.add_trace(go.Scatter(
            x=alert_pH['X_label'], y=alert_pH['pH'], mode='markers',
            marker=dict(symbol='triangle-down', color='orange', size=12),
            name=f"pH Alert - {tank}", showlegend=True
        ))

    fig_water.update_layout(xaxis_title="Date/Week", yaxis_title="Value")
    st.plotly_chart(fig_water, use_container_width=True)
else:
    st.info("No water quality data available.")

# ------------------------------
# 7️⃣ FEED TRENDS
# ------------------------------
st.subheader("Feed Trends")
if not view_df.empty:
    fig_feed = go.Figure()
    for i, tank in enumerate(tanks_list):
        df_tank = view_df[view_df['Tank'] == tank]
        fig_feed.add_trace(go.Scatter(
            x=df_tank['X_label'], y=df_tank['ScheduledFeed_day_g'],
            mode='lines+markers', line=dict(color='darkblue', width=2), name=f"Scheduled Feed - {tank}"
        ))
        fig_feed.add_trace(go.Scatter(
            x=df_tank['X_label'], y=df_tank['ActualFeed_day_g'],
            mode='lines+markers', line=dict(color='lightblue', width=2), name=f"Actual Feed - {tank}"
        ))
        # Feed Risk Markers
        df_risk = df_tank[df_tank['ScheduledFeed_day_g'] - df_tank['ActualFeed_day_g'] > 0]
        fig_feed.add_trace(go.Scatter(
            x=df_risk['X_label'], y=df_risk['ActualFeed_day_g'], mode='markers',
            marker=dict(symbol='triangle-up', size=12, color='orange'),
            name=f"Feed Risk - {tank}", showlegend=True
        ))
    st.plotly_chart(fig_feed, use_container_width=True)
else:
    st.info("No feed data available.")

# ------------------------------
# 8️⃣ MORTALITY TRENDS
# ------------------------------
st.subheader("Mortality Trends")
if not view_df.empty:
    fig_mort = go.Figure()
    for i, tank in enumerate(tanks_list):
        df_tank = view_df[view_df['Tank'] == tank]
        fig_mort.add_trace(go.Scatter(
            x=df_tank['X_label'], y=df_tank['DeadCount_day'],
            mode='lines+markers', line=dict(color='darkblue', width=2), name=f"Dead Shrimp - {tank}"
        ))
        fig_mort.add_trace(go.Scatter(
            x=df_tank['X_label'], y=df_tank['Mortality_pct'],
            mode='lines+markers', line=dict(color='lightblue', width=2), name=f"Mortality % - {tank}"
        ))
        # Mortality Risk
        df_risk = df_tank[df_tank['Mortality_pct'] > 0]
        df_risk['Risk_Level'] = 3  # light orange for example, you can adjust based on thresholds
        fig_mort.add_trace(go.Scatter(
            x=df_risk['X_label'], y=df_risk['Mortality_pct'], mode='markers',
            marker=dict(symbol='triangle-up', size=12, color='orange'),
            name=f"Mortality Risk - {tank}", showlegend=True
        ))
    st.plotly_chart(fig_mort, use_container_width=True)
else:
    st.info("No mortality data available.")
