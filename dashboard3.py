import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(page_title="Shrimp Farm Dashboard", layout="wide")

# ============================================================
# 1️⃣ COLUMN MAPPING (You can edit these names anytime)
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

# Apply column mapping
df = df.rename(columns=column_mapping)

# ============================================================
# 3️⃣ CHECK FOR MISSING COLUMNS
# ============================================================
missing = [c for c in required_columns if c not in df.columns]

if missing:
    st.error(f"❌ ERROR: Your Excel file is missing these required columns:\n\n{missing}\n\n"
             f"Please correct column names or update the mapping dictionary.")
    st.stop()

# ============================================================
# 4️⃣ CONTINUE WITH YOUR ORIGINAL CODE
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
# X-label for charts
# ------------------------------
if view_option == "Daily":
    view_df["X_label"] = view_df["Date"].dt.date
else:
    view_df["X_label"] = (
        view_df["Week_Start"].dt.date.astype(str) + " - " +
        (view_df["Week_Start"] + pd.Timedelta(days=6)).dt.date.astype(str)
    )

# ------------------------------
# KPI Metrics (Without Tank Rating)
# ------------------------------
st.title("🦐 Shrimp Farm Dashboard")
col1, col2, col3 = st.columns(3)  # Only 3 columns now

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
# Water quality chart
# ------------------------------
st.subheader("Water Quality (Salinity & pH)")

if not view_df.empty:
    fig_water = px.line(
        view_df,
        x="X_label",
        y=["Salinity", "pH"],
        markers=True,
        labels={"X_label": "Date/Week", "value": "Value", "variable": "Parameter"}
    )
    st.plotly_chart(fig_water, use_container_width=True)
else:
    st.info("No water quality data available.")

# ------------------------------
# Feed & Mortality Charts
# ------------------------------
st.subheader("Feed Trends")

if not view_df.empty:
    fig_feed = px.line(view_df, x="X_label",
                       y=["ScheduledFeed_day_g", "ActualFeed_day_g"],
                       markers=True)
    st.plotly_chart(fig_feed, use_container_width=True)
else:
    st.info("No feed data available.")


st.subheader("Mortality Trends")

if not view_df.empty:
    fig_mort = px.line(view_df, x="X_label",
                       y=["DeadCount_day", "Mortality_pct"],
                       markers=True)
    st.plotly_chart(fig_mort, use_container_width=True)
else:
    st.info("No mortality data available.")

# ------------------------------
# Risk Table
# ------------------------------
st.subheader("Risk Table (Only Tanks with Risk)")

if not view_df.empty:
    risk_df = view_df.copy()

    risk_df['pH_Risk'] = ((risk_df['pH'] < 7.8) | (risk_df['pH'] > 8.0)).astype(int)
    risk_df['Salinity_Risk'] = ((risk_df['Salinity'] < 26) | (risk_df['Salinity'] > 28)).astype(int)
    risk_df['Mortality_Risk'] = (risk_df['Mortality_pct'] > 0).astype(int)
    risk_df['Feed_Risk'] = ((risk_df['ScheduledFeed_day_g'] - risk_df['ActualFeed_day_g']) > 0).astype(int)
    risk_df['Feed_Leftover_Risk'] = risk_df['Feed_Risk']

    risk_df['Risk_Level'] = risk_df[['pH_Risk','Salinity_Risk','Mortality_Risk','Feed_Risk','Feed_Leftover_Risk']].sum(axis=1)

    def get_risk_factors(row):
        f = []
        if row['pH_Risk']: f.append("pH")
        if row['Salinity_Risk']: f.append("Salinity")
        if row['Mortality_Risk']: f.append("Mortality")
        if row['Feed_Risk']: f.append("Feed")
        if row['Feed_Leftover_Risk']: f.append("Leftover Feed")
        return ", ".join(f)

    risk_df['Risk_Factors'] = risk_df.apply(get_risk_factors, axis=1)

    display_cols = [
        'Block','Tank','X_label','pH','Salinity','Mortality_pct',
        'DeadCount_day','ActualFeed_day_g','ScheduledFeed_day_g',
        'Feed_Leftover_Risk','Risk_Level','Risk_Factors'
    ]

    display_df = risk_df[risk_df['Risk_Level'] > 0][display_cols]

    display_df = display_df.rename(columns={
        'X_label': 'Date/Week',
        'ActualFeed_day_g': 'Actual Feed (g)',
        'ScheduledFeed_day_g': 'Scheduled Feed (g)',
        'Mortality_pct': 'Mortality %',
        'DeadCount_day': 'Dead Shrimp',
        'Feed_Leftover_Risk': 'Feed Leftover Risk'
    })

   # Colors
    def color_risk(val):
        if val == 5:
          return "background-color: #FF0000"  # Red - High risk
        elif val == 4:
          return "background-color: #FF8000"  # Orange - Medium-High risk
        elif val == 3:
          return "background-color: #FFD580"  # Light Orange - Medium risk
        else:
          return ""  # No color for low/no risk

    def color_leftover(val):
        if val == 1:
          return "background-color: #FFA500"  # Orange alert
        else:
          return ""

    st.dataframe(
        display_df.style.applymap(color_risk, subset=['Risk_Level'])
                        .applymap(color_leftover, subset=['Feed Leftover Risk']),
        height=500
    )
else:
    st.info("No data available for selected filters.")
