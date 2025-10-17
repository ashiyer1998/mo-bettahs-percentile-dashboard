# seaker_percentile_app_v6_3.py
# Seaker Percentile & Comparable Visualizer — Label Edition (Final)

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os, tempfile
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

st.set_page_config(page_title="Seaker Percentile & Comparable Visualizer", layout="wide")

# Required columns
REQUIRED_COLS = [
    "Site Name", "Real Estate Type", "Visits", "Visitors",
    "Daytime Population", "Trade Area Population", "Trade Area Size"
]

METRIC_LABELS = [
    "Visits", "Visitors", "Daytime Population",
    "Trade Area Population", "Trade Area Size"
]

# Branding and colors
BRAND_COLOR = "#5458c3"
COLOR_PALETTE = ["#5458c3", "#26a0fc", "#ffba08", "#f94144", "#90be6d"]

@st.cache_data
def load_file(uploaded_file):
    if uploaded_file is None:
        return pd.DataFrame(columns=REQUIRED_COLS)
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    elif name.endswith(".xls") or name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
    else:
        st.error("Unsupported file type. Please upload a CSV or Excel file.")
        return pd.DataFrame(columns=REQUIRED_COLS)
    df.columns = [c.strip() for c in df.columns]
    for c in METRIC_LABELS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def compute_percentile(df, metric, rtype, value):
    subset = df[df["Real Estate Type"] == rtype][metric].dropna()
    if subset.empty or pd.isna(value): return np.nan
    sorted_vals = np.sort(subset.values)
    return (np.searchsorted(sorted_vals, value) / len(sorted_vals))

def get_row(df, site):
    row = df.loc[df["Site Name"] == site]
    return row.iloc[0] if not row.empty else None

# Header with logo
logo_path = os.path.join(os.path.dirname(__file__), "seaker_logo.png")
hcols = st.columns([0.15, 0.85])
with hcols[0]:
    if os.path.exists(logo_path): st.image(logo_path, use_container_width=True)
with hcols[1]:
    st.title("Seaker Percentile & Comparable Visualizer")

st.markdown("### Please upload your fleet data to begin.")
uploaded = st.sidebar.file_uploader("Upload Fleet Data", type=["csv", "xls", "xlsx"])
df = load_file(uploaded)

if not df.empty:
    st.markdown("#### Interactive benchmarking of a potential site against fleet comparables, with within-type percentiles.")
    type_options = sorted(df["Real Estate Type"].dropna().unique())
    selected_type = st.sidebar.selectbox("Real Estate Type", type_options)
    type_df = df[df["Real Estate Type"] == selected_type]
    sites = sorted(type_df["Site Name"].dropna().unique())
    potential_site = st.sidebar.selectbox("Potential Site", sites)
    comps = st.sidebar.multiselect("Comparables", [s for s in sites if s != potential_site], max_selections=3)
    metrics = st.sidebar.multiselect("Metrics", METRIC_LABELS, default=METRIC_LABELS)
    orientation = st.radio("Chart orientation", ["Vertical", "Horizontal"], horizontal=True)

    pot_row = get_row(type_df, potential_site)
    comp_rows = [get_row(type_df, s) for s in comps if get_row(type_df, s) is not None]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Traffic & Trade Area Metrics Comparison — Potential vs Comparables")
        vt = pd.DataFrame({"Metric": metrics})
        vt["Potential"] = [pot_row.get(m, np.nan) for m in metrics]
        for i, r in enumerate(comp_rows): vt[f"Comp {i+1}"] = [r.get(m, np.nan) for m in metrics]
        label_map = {"Potential": f"{potential_site} (Potential)"}
        for i, s in enumerate(comps): label_map[f"Comp {i+1}"] = f"{s} (Comp {i+1})"
        vt.rename(columns=label_map, inplace=True)
        plot_df = vt.melt(id_vars="Metric", var_name="Site", value_name="Value")

        if orientation == "Vertical":
            fig_val = px.bar(plot_df, x="Metric", y="Value", color="Site", color_discrete_sequence=COLOR_PALETTE,
                             barmode="group", text_auto=".2s", height=460)
            fig_val.update_traces(textposition="outside", width=0.3)
        else:
            fig_val = px.bar(plot_df, x="Value", y="Metric", color="Site", color_discrete_sequence=COLOR_PALETTE,
                             orientation="h", barmode="group", text_auto=".2s", height=460)
            fig_val.update_traces(textposition="outside", width=0.3)
        st.plotly_chart(fig_val, use_container_width=True)
        st.dataframe(vt.set_index("Metric"))

    with col2:
        st.subheader("Fleet Percentile — Potential Site (within selected type)")
        pct_df = pd.DataFrame([
            {"Metric": m, "Percentile %": round(compute_percentile(df, m, selected_type, pot_row.get(m))*100, 1)}
            for m in metrics
        ])
        fig_pct = px.bar(pct_df, x="Percentile %", y="Metric", orientation="h", range_x=[0,100],
                         color_discrete_sequence=COLOR_PALETTE, height=460)
        fig_pct.update_traces(texttemplate="%{x}%", textposition="outside", cliponaxis=False, width=0.3)
        st.plotly_chart(fig_pct, use_container_width=True)
        st.dataframe(pct_df.set_index("Metric"))

    def build_pdf():
        tmp = tempfile.mkdtemp()
        value_img = os.path.join(tmp, "vchart.png")
        pct_img = os.path.join(tmp, "pchart.png")
        fig_val.write_image(value_img, scale=2, engine="kaleido")
        fig_pct.write_image(pct_img, scale=2, engine="kaleido")
        pdf_path = os.path.join(tmp, "seaker_snapshot.pdf")
        doc = SimpleDocTemplate(pdf_path, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="Body", fontSize=9, leading=11))
        story = []
        charts = Table([[RLImage(value_img, width=380, height=220), RLImage(pct_img, width=380, height=220)]], colWidths=[380,380])
        charts.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        story += [Spacer(1,18), charts, Spacer(1,10)]
        vt_table = [vt.columns.tolist()] + vt.fillna("").values.tolist()
        vt_tbl = Table(vt_table)
        vt_tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor("#f0f0f0")), ('GRID',(0,0),(-1,-1),0.4,colors.HexColor("#cccccc"))]))
        story += [Paragraph("Value Comparison Table", styles["Body"]), vt_tbl, Spacer(1,10)]
        pt_table = [["Metric","Percentile %"]] + pct_df.fillna("").values.tolist()
        pt_tbl = Table(pt_table)
        pt_tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor("#f0f0f0")), ('GRID',(0,0),(-1,-1),0.4,colors.HexColor("#cccccc"))]))
        story += [Paragraph("Percentile Table", styles["Body"]), pt_tbl, Spacer(1,8),
                  Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Body"]),
                  Paragraph("© 2025 The Seaker Group LLC — All rights reserved.", styles["Body"]),
                  Paragraph("Developed & Maintained by Ashirwad Ramakrishnan Iyer — Data Analyst, The Seaker Group LLC", styles["Body"])]
        def on_page(canvas, doc):
            w,h = landscape(letter)
            canvas.saveState()
            canvas.setFillColor(colors.HexColor(BRAND_COLOR))
            canvas.rect(0,h-55,w,55,fill=1,stroke=0)
            if os.path.exists(logo_path):
                canvas.drawImage(logo_path,20,h-50,width=75,height=30,mask='auto')
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold",14)
            canvas.drawString(110,h-35,"Seaker Percentile & Comparable Visualizer — Fleet Analytics Report")
            canvas.restoreState()
        doc.build(story,onFirstPage=on_page,onLaterPages=on_page)
        return open(pdf_path,"rb").read()

    pdf_bytes = build_pdf()
    st.download_button("Download PDF snapshot", data=pdf_bytes, file_name="seaker_percentile_snapshot.pdf")
    # --- Webpage Snapshot (Charts Only) ---
from PIL import Image, ImageDraw

def build_snapshot(fig_val, fig_pct):
    tmp = tempfile.mkdtemp()
    value_img = os.path.join(tmp, "vchart.png")
    pct_img = os.path.join(tmp, "pchart.png")
    combined_img = os.path.join(tmp, "seaker_snapshot.png")

    # Export both charts as PNGs
    fig_val.write_image(value_img, scale=2, engine="kaleido")
    fig_pct.write_image(pct_img, scale=2, engine="kaleido")

    # Open both images and merge side by side
    img1 = Image.open(value_img)
    img2 = Image.open(pct_img)
    w1, h1 = img1.size
    w2, h2 = img2.size
    merged_width = w1 + w2 + 60
    merged_height = max(h1, h2) + 120

    new_img = Image.new("RGB", (merged_width, merged_height), "white")

    # Paste both charts onto one image
    new_img.paste(img1, (20, 60))
    new_img.paste(img2, (w1 + 40, 60))

    # Add title text
    draw = ImageDraw.Draw(new_img)
    draw.text((20, 20), "Seaker Percentile & Comparable Visualizer — Snapshot", fill=(0, 0, 0))

    new_img.save(combined_img)
    return combined_img

# Generate the snapshot
snapshot_path = build_snapshot(fig_val, fig_pct)
with open(snapshot_path, "rb") as snap_file:
    st.download_button(
        "Download PNG Snapshot (for REC Package)",
        data=snap_file,
        file_name="seaker_visual_snapshot.png",
        mime="image/png"
    )


    # Footer
    st.markdown("<hr style='margin-top:40px;margin-bottom:10px;border:0.5px solid #ccc'>", unsafe_allow_html=True)
    footer_html = '''
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div style="font-size:11px; color:black; text-align:left;">
            © 2025 <b>The Seaker Group LLC</b> — All rights reserved. 
            This tool and its contents are proprietary and confidential. 
            Unauthorized distribution or external use is strictly prohibited.
        </div>
        <div style="font-size:11px; color:black; text-align:right;">
            Developed & Maintained by <b>Ashirwad Ramakrishnan Iyer</b> — Business Intelligence & Data Analyst, The Seaker Group LLC
        </div>
    </div>
    '''
    st.markdown(footer_html, unsafe_allow_html=True)
