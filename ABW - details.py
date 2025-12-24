ABW - details

import streamlit as st
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import pandas as pd
from reportlab.pdfbase.pdfmetrics import stringWidth
from textwrap import wrap

# -----------------------------
# Helper function to wrap text
# -----------------------------
def draw_wrapped_text(c, text, x, y, max_width, line_height=14):
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

# -----------------------------
# Ensure dashboard dataframe exists
# -----------------------------
required_cols = ['Date','WorkerName','Tank','Block','pH','Salinity','WaterTemperature',
                 'DeadCount_day','DeadWeight_g','ScheduledFeed_day_g','ActualFeed_day_g',
                 'pH_OK','Salinity_OK','LiveCount','InitialCount']
for col in required_cols:
    if col not in view_df.columns:
        st.error(f"Missing column: {col}")
        st.stop()

# -----------------------------
# Select Report Parameters
# -----------------------------
st.title("🦐 Shrimp Farm Dashboard – Executive Summary Report")
start_date = st.date_input("Start Date", key="start_date_report")
end_date = st.date_input("End Date", key="end_date_report")

# -----------------------------
# Filter Data
# -----------------------------
filtered_df = view_df[
    (view_df['Date'] >= pd.to_datetime(start_date)) &
    (view_df['Date'] <= pd.to_datetime(end_date))
].copy()

if filtered_df.empty:
    st.warning("No data available for the selected date range.")
else:
    # -----------------------------
    # ABW - manually defined per block
    # -----------------------------
    abw_dict = {
        'H1':0.08,'H2':0.09,'H3':0.085,'H4':0.082,
        'I1':0.087,'I2':0.089,'I3':0.088,'I4':0.086,
        'J1':0.09,'J2':0.091,'J3':0.088,'J4':0.087,
        'E1':0.083,'E2':0.084,'E3':0.085,'E4':0.083,
        'F1':0.082,'F2':0.084,'F3':0.086,'F4':0.085,
        'G1':0.087,'G2':0.088,'G3':0.089,'G4':0.086,
        'A1':0.08,'A2':0.081,'A3':0.082,'A4':0.08,
        'B1':0.083,'B2':0.084,'B3':0.082,'B4':0.081,
        'C1':0.085,'C2':0.084,'C3':0.083,'C4':0.082,
        'D1':0.081,'D2':0.082,'D3':0.083,'D4':0.084,
        'K1':0.085,'K2':0.086,'K3':0.087,'K4':0.088,'K5':0.089,'K6':0.09,'K7':0.088,'K8':0.087
    }
    filtered_df['ABW'] = filtered_df['Block'].map(abw_dict).fillna(0)

    # -----------------------------
    # KPIs
    # -----------------------------
    total_feed_scheduled = filtered_df['ScheduledFeed_day_g'].sum() / 1000
    total_feed_actual = filtered_df['ActualFeed_day_g'].sum() / 1000
    total_leftover_feed = total_feed_scheduled - total_feed_actual
    total_mortality = filtered_df['DeadCount_day'].sum()
    mortality_pct = round(total_mortality / filtered_df['InitialCount'].sum() * 100,1)
    ph_compliance = round(filtered_df['pH_OK'].mean()*100,1)
    salinity_compliance = round(filtered_df['Salinity_OK'].mean()*100,1)

    # -----------------------------
    # Assign Worker Labels
    # -----------------------------
    hikaru_blocks = ['H','I','J']
    jimmy_blocks = ['E','F','G']
    other_blocks = ['A','B','C','D','K']

    def assign_worker(block):
        if block[0] in hikaru_blocks:
            return "Hikaru"
        elif block[0] in jimmy_blocks:
            return "Jimmy"
        else:
            return "Other"
    filtered_df['Worker_Label'] = filtered_df['Block'].apply(assign_worker)

    # -----------------------------
    # Tank/Block Risk Summary
    # -----------------------------
    def get_status(row):
        details = []
        # pH
        if 8.0 <= row['pH'] <= 8.3:
            details.append("✅")
        elif 7.9 <= row['pH'] < 8.0 or 8.3 < row['pH'] <= 8.4:
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
    tank_summary = filtered_df.groupby(['Worker_Label','Tank','Block']).agg({
        'pH_status':'max',
        'Sal_status':'max',
        'Temp_status':'max',
        'Mort_status':'max',
        'pH':'first',
        'Salinity':'first',
        'WaterTemperature':'first',
        'DeadCount_day':'first',
        'ABW':'first'  # include ABW per block
    }).reset_index()

    # -----------------------------
    # Worker Performance Summary (Latest Date & Wrapped Blocks)
    # -----------------------------
    worker_summary_list = []
    latest_date = filtered_df['Date'].max()
    latest_df = filtered_df[filtered_df['Date'] == latest_date]

    for worker in ['Hikaru','Jimmy','Other']:
        w_df = latest_df[latest_df['Worker_Label'] == worker]
        if w_df.empty:
            continue

        # Blocks list
        blocks_list = w_df['Block'].tolist()
        blocks_text = ','.join(blocks_list)
        blocks_lines = wrap(blocks_text, width=40)

        scheduled_feed = round(w_df['ScheduledFeed_day_g'].sum()/1000,2)
        actual_feed = round(w_df['ActualFeed_day_g'].sum()/1000,2)
        leftover_feed = round(scheduled_feed - actual_feed,2)
        dead_count = w_df['DeadCount_day'].sum()
        dead_weight = round(w_df['DeadWeight_g'].sum(),2)
        total_blocks = w_df['Block'].nunique()
        live_count = w_df['LiveCount'].sum()
        initial_stock = w_df['InitialCount'].sum()
        survival_pct = round(live_count / initial_stock * 100,2) if initial_stock else 0
        mortality_pct_worker = round(100 - survival_pct,2)
        ph_comp = round(w_df['pH_OK'].mean()*100,1)
        sal_comp = round(w_df['Salinity_OK'].mean()*100,1)

        # ABW average per worker
        avg_abw = round(w_df['ABW'].mean(),4)

        worker_summary_list.append({
            'WorkerName': worker,
            'Blocks_Lines': blocks_lines,
            'ScheduledFeed_kg': scheduled_feed,
            'ActualFeed_kg': actual_feed,
            'Leftover_kg': leftover_feed,
            'Dead_Count': dead_count,
            'Dead_Weight_g': dead_weight,
            'Total_Blocks': total_blocks,
            'Live_Count': live_count,
            'Initial_Count': initial_stock,
            'Survival_%': survival_pct,
            'Mortality_%': mortality_pct_worker,
            'pH_%': ph_comp,
            'Salinity_%': sal_comp,
            'Avg_ABW': avg_abw
        })

    worker_summary_df = pd.DataFrame(worker_summary_list)

    # -----------------------------
    # Generate PDF
    # -----------------------------
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4

    # Title & Info
    c.setFont("Times-Bold", 18)
    c.drawCentredString(width/2, height-50, "🦐 PJ Site Executive Summary Report 🦐")
    c.setFont("Times-Roman", 12)
    c.drawString(50, height-80, f"Reporting Period: {start_date} to {end_date}")
    c.drawString(50, height-100, "Prepared By: Sai")
    c.drawString(50, height-120, "Data Source: Shrimp Farm Dashboard")

    # Key KPIs
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

    # Worker Performance
    c.setFont("Times-Bold", 14)
    c.drawString(50, y-10, "2️⃣ Worker Performance Summary")
    y -= 30

    for _, row in worker_summary_df.iterrows():
        c.setFont("Times-Bold", 12)
        c.drawString(60, y, f"Worker: {row['WorkerName']}")
        y -= 16
        # Draw wrapped block lines
        c.setFont("Times-Roman", 12)
        for line in row['Blocks_Lines']:
            c.drawString(80, y, f"Blocks: {line}")
            y -= 14
            if y < 50:
                c.showPage()
                y = height-50
        # Metrics bullets
        bullets = [
            f"• Live Count: {row['Live_Count']}/{row['Initial_Count']}",
            f"• Survival %: {row['Survival_%']}",
            f"• Mortality %: {row['Mortality_%']}",
            f"• Scheduled Feed (kg): {row['ScheduledFeed_kg']}",
            f"• Actual Feed (kg): {row['ActualFeed_kg']}",
            f"• Leftover Feed (kg): {row['Leftover_kg']}",
            f"• Dead Count: {row['Dead_Count']}",
            f"• Dead Weight (g): {row['Dead_Weight_g']}",
            f"• Blocks Managed: {row['Total_Blocks']}",
            f"• Avg ABW: {row['Avg_ABW']}"
        ]
        for b in bullets:
            c.drawString(80, y, b)
            y -= 14
            if y < 50:
                c.showPage()
                y = height-50
        y -= 8

    # Tank/Block Risk Summary side-by-side symbols
    c.setFont("Times-Bold", 14)
    c.drawString(50, y-10, "3️⃣ Tank/Block Risk Summary")
    y -= 30
    colors_map = {"✅": colors.green, "⚠": colors.orange, "🔴": colors.red}

    for worker in ["Hikaru","Jimmy","Other"]:
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

    c.save()
    pdf_buffer.seek(0)

    st.success("✅ PDF generated successfully!")
    st.download_button(
        label="⬇️ Download Executive Summary PDF",
        data=pdf_buffer,
        file_name="PJ_Site_Executive_Summary.pdf",
        mime="application/pdf"
    )
