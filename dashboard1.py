# ==============================
# 🦐 SHRIMP FARM DASHBOARD – TABS
# ==============================
st.set_page_config(page_title="Shrimp Farm Dashboard", layout="wide")

# Create tabs
tab1, tab2 = st.tabs(["Dashboard", "Score Card"])

# ------------------------------
# 1️⃣ Main Dashboard Tab
# ------------------------------
with tab1:
    st.header("🦐 Main Dashboard")
    # Place your existing dashboard code here
    # (Daily/Weekly/Monthly views, worker performance, water quality plots, feed/mortality trends)
    st.info("Main dashboard content goes here...")

# ------------------------------
# 2️⃣ Score Card Tab
# ------------------------------
with tab2:
    st.header("📊 Shrimp Farm Score Card")

    # --------------------------
    # Filters (reuse your existing sidebar filters if needed)
    blocks = ["All"] + sorted(df['Block'].dropna().unique())
    selected_block = st.selectbox("Select Block for Score Card", blocks)

    tanks = ["All"] + sorted(df['Tank'].dropna().unique())
    selected_tank = st.selectbox("Select Tank for Score Card", tanks)

    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")

    # --------------------------
    # Filter dataframe
    score_df = df.copy()
    if selected_block != "All":
        score_df = score_df[score_df['Block'] == selected_block]
    if selected_tank != "All":
        score_df = score_df[score_df['Tank'] == selected_tank]

    score_df = score_df[(score_df['Date'] >= pd.to_datetime(start_date)) & 
                        (score_df['Date'] <= pd.to_datetime(end_date))]

    if score_df.empty:
        st.warning("No data available for selected filters.")
    else:
        # --------------------------
        # Metrics
        score_df['Survival_pct'] = (score_df['LiveCount']/score_df['InitialCount']*100).round(2)
        score_df['Mortality_pct'] = (100 - score_df['Survival_pct']).round(2)
        score_df['FCR'] = (score_df['ActualFeed_day_g'] / score_df['ABW']).round(2)
        score_df['ABW_week'] = score_df['ABW']  # Or calculate weekly ABW if needed
        score_df['Uneven_Growth'] = score_df['ABW'].max() - score_df['ABW'].min()

        # Define target values (for comparison)
        TARGETS = {
            "Survival_pct": 90,
            "FCR": 1.5,
            "ABW_week": 10
        }

        # Create comparison columns
        score_df['Survival_vs_Target'] = score_df['Survival_pct'] - TARGETS['Survival_pct']
        score_df['FCR_vs_Target'] = TARGETS['FCR'] - score_df['FCR']
        score_df['ABW_vs_Target'] = score_df['ABW_week'] - TARGETS['ABW_week']

        # --------------------------
        # Display Score Card
        display_cols = [
            'Date', 'Block', 'Tank', 'InitialCount', 'ABW', 'ABW_week', 'Uneven_Growth',
            'Survival_pct', 'Survival_vs_Target',
            'FCR', 'FCR_vs_Target',
            'ABW_vs_Target'
        ]
        st.dataframe(score_df[display_cols].round(2), use_container_width=True)

        # --------------------------
        # Optional: Generate PDF Report
        import tempfile
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4

        def generate_pdf(df):
            buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            c = canvas.Canvas(buffer.name, pagesize=A4)
            width, height = A4
            y = height - 50
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y, "Shrimp Farm Score Card Report")
            y -= 30
            c.setFont("Helvetica", 10)

            for i, row in df.iterrows():
                line = f"{row['Date'].date()} | {row['Block']} | {row['Tank']} | ABW: {row['ABW']:.2f} | Survival: {row['Survival_pct']:.2f}% | FCR: {row['FCR']:.2f}"
                c.drawString(50, y, line)
                y -= 15
                if y < 50:
                    c.showPage()
                    y = height - 50
            c.save()
            return buffer.name

        pdf_file = generate_pdf(score_df)
        with open(pdf_file, "rb") as f:
            st.download_button("📥 Download Score Card PDF", f, file_name="score_card.pdf")

