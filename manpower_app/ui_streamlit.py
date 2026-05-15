from __future__ import annotations

import base64
import io
import math

import pandas as pd
import pulp
import plotly.graph_objects as go
import streamlit as st

from manpower_app.config import APP_TITLE, CLIENT_LOGO_PATH
from manpower_app.costs import (
    calculate_inhouse_cost_split,
    calculate_inhouse_fully_loaded_employee_cost,
    calculate_outsource_base_employee_cost,
    calculate_outsource_employee_cost,
)
from manpower_app.mappings import (
    JOB_FAMILY_MAPPING,
    NORMALIZED_ACTIVITY_MAPPING,
    NORMALIZED_PROFESSION_MAPPING,
    TOTAL_CONFIGURED_JOB_FAMILIES,
    get_job_family_with_fallback,
)
from manpower_app.optimization import (
    calculate_payroll_v2_plan,
    calculate_payroll_v3_plan,
    calculate_payroll_v4_plan,
    calculate_payroll_v5_plan,
)
from manpower_app.pipeline import read_manpower_workbook
from manpower_app.ratios import (
    build_current_ratio_display,
    calculate_driver_values,
    calculate_minimum_headcount_needed,
    calculate_outsourced_v1,
    load_ratio_rules,
    lookup_ratio_rule,
    resolve_average_costs,
)
from manpower_app.results import build_payroll_v5_results
from manpower_app.rules import MAXIMUM_RATIO_RULES, OUTSOURCEABILITY_RULES
from manpower_app.service import calculate_target_split_from_data
from manpower_app.tenure import derive_tenure_years, detect_tenure_column, summarize_tenured_inhouse
from manpower_app.utils import (
    clean_lookup_text,
    detect_service_fee_column,
    is_blank,
    normalize_lookup_text,
    safe_divide,
    safe_numeric,
)


def run_app() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    if "stage" not in st.session_state:
        st.session_state.stage = "upload_raw"
    # ===== CUSTOM CSS =====
    st.markdown("""
    <style>
        :root {
            --ink-900: #0f1110;
            --ink-800: #171a19;
            --ink-700: #232826;
            --mist-100: #f5f1e8;
            --mist-200: #ece5d8;
            --mist-300: #ddd4c4;
            --sage-500: #8fbfa7;
            --sage-600: #6ea488;
            --pine-700: #28473a;
            --steel-500: #6e8795;
            --sand-500: #b89863;
            --text-main: #f5f1e8;
            --text-soft: #cdc7bb;
            --text-dark: #1a1f1d;
            --text-mid: #44504a;
            --line-soft: rgba(245, 241, 232, 0.12);
            --shadow-deep: 0 22px 60px rgba(0, 0, 0, 0.32);
            --shadow-card: 0 18px 40px rgba(9, 10, 10, 0.18);
        }

        .stApp {
            background:
                linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
                radial-gradient(circle at top left, rgba(143, 191, 167, 0.15), transparent 26%),
                radial-gradient(circle at top right, rgba(184, 152, 99, 0.12), transparent 22%),
                linear-gradient(180deg, #111311 0%, #171a19 48%, #111311 100%);
            background-size: 34px 34px, 34px 34px, auto, auto, auto;
            color: var(--text-main);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        html, body, [data-testid="stAppViewContainer"], .stApp {
            color-scheme: light;
        }

        [data-testid="stAppViewContainer"] {
            background: transparent;
        }

        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] span,
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p,
        .stCaption,
        [data-testid="stCaptionContainer"] {
            color: inherit !important;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #141715 0%, #191d1b 100%);
            border-right: 1px solid var(--line-soft);
        }

        [data-testid="stSidebar"] * {
            color: var(--text-main) !important;
        }

        hr {
            border: none;
            border-top: 1px solid var(--line-soft);
            margin: 26px 0;
        }

        h1, h2, h3 {
            color: var(--text-main) !important;
            font-weight: 600 !important;
        }

        p, li, label, [data-testid="stCaptionContainer"] {
            color: var(--text-soft);
        }

        .app-hero {
            position: relative;
            background:
                linear-gradient(135deg, rgba(245, 241, 232, 0.08), rgba(245, 241, 232, 0.03)),
                linear-gradient(180deg, #141715 0%, #1a1f1d 100%);
            border: 1px solid rgba(245, 241, 232, 0.12);
            border-radius: 30px;
            padding: 30px 32px;
            min-height: 170px;
            overflow: hidden;
            box-shadow: var(--shadow-deep);
        }

        .app-hero::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(125deg, transparent 0 54%, rgba(143, 191, 167, 0.12) 54% 62%, transparent 62%);
            pointer-events: none;
        }

        .hero-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
            margin-bottom: 16px;
            position: relative;
            z-index: 1;
        }

        .app-hero .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: var(--mist-100);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.18em;
            text-transform: uppercase;
        }

        .app-hero .eyebrow::before {
            content: "";
            width: 34px;
            height: 1px;
            background: linear-gradient(90deg, var(--sage-600), transparent);
        }

        .hero-chip {
            display: inline-flex;
            align-items: center;
            padding: 8px 12px;
            border-radius: 999px;
            background: rgba(245, 241, 232, 0.08);
            border: 1px solid rgba(245, 241, 232, 0.12);
            color: var(--mist-100);
            font-size: 11px;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .app-hero .title {
            position: relative;
            z-index: 1;
            color: #ffffff;
            font-family: Georgia, "Times New Roman", serif;
            font-size: 40px;
            line-height: 1.02;
            font-weight: 600;
            margin: 0;
            max-width: 760px;
        }

        .hero-body {
            position: relative;
            z-index: 1;
            display: grid;
            grid-template-columns: minmax(0, 1.7fr) minmax(220px, 0.8fr);
            gap: 24px;
            align-items: end;
            margin-top: 16px;
        }

        .app-hero .subtitle {
            color: var(--text-soft);
            font-size: 14px;
            line-height: 1.7;
            margin: 0;
            max-width: 720px;
        }

        .hero-callout {
            justify-self: end;
            background: rgba(245, 241, 232, 0.92);
            color: var(--text-dark);
            border-radius: 22px;
            padding: 16px 18px;
            min-width: 220px;
            box-shadow: var(--shadow-card);
        }

        .hero-callout .label {
            color: var(--text-mid);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 6px;
        }

        .hero-callout .value {
            color: var(--text-dark);
            font-size: 18px;
            font-weight: 700;
            margin: 0;
        }

        .hero-callout .note {
            color: #5c6761;
            font-size: 12px;
            margin-top: 6px;
        }

        .logo-panel {
            background:
                radial-gradient(circle at top, rgba(143, 191, 167, 0.18), transparent 34%),
                linear-gradient(180deg, #131614 0%, #1a1e1c 100%);
            border: 1px solid rgba(245, 241, 232, 0.12);
            border-radius: 30px;
            padding: 24px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 170px;
            box-shadow: var(--shadow-deep);
            position: relative;
            overflow: hidden;
        }

        .logo-panel::after {
            content: "";
            position: absolute;
            inset: 14px;
            border: 1px solid rgba(245, 241, 232, 0.08);
            border-radius: 22px;
            pointer-events: none;
        }

        .section-heading {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 16px;
            align-items: center;
            margin: 30px 0 18px;
        }

        .section-heading::before,
        .section-heading::after {
            content: "";
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(245, 241, 232, 0.18), transparent);
        }

        .section-heading span {
            color: var(--mist-100);
            background: rgba(245, 241, 232, 0.06);
            border: 1px solid rgba(245, 241, 232, 0.12);
            border-radius: 999px;
            padding: 10px 18px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.18em;
            text-transform: uppercase;
        }

        .stage-panel {
            background: linear-gradient(180deg, rgba(245, 241, 232, 0.96) 0%, rgba(236, 229, 216, 0.92) 100%);
            border: 1px solid rgba(221, 212, 196, 0.95);
            border-radius: 26px;
            padding: 24px 26px;
            box-shadow: var(--shadow-card);
            margin-bottom: 18px;
        }

        .stage-panel .stage-kicker {
            color: #647169;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }

        .stage-panel .stage-title {
            color: var(--text-dark) !important;
            font-family: Georgia, "Times New Roman", serif;
            font-size: 30px;
            line-height: 1.08;
            margin: 0;
        }

        .stage-panel .stage-copy {
            color: var(--text-mid);
            font-size: 14px;
            line-height: 1.7;
            margin: 12px 0 0;
            max-width: 720px;
        }

        .stage-panel .stage-meta {
            color: #6d776f;
            font-size: 12px;
            margin-top: 10px;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        [data-testid="stFileUploader"] {
            background: linear-gradient(180deg, rgba(245, 241, 232, 0.96) 0%, rgba(236, 229, 216, 0.92) 100%);
            border: 1.5px dashed #b8a57f;
            border-radius: 24px;
            padding: 18px;
            box-shadow: var(--shadow-card);
        }

        [data-testid="stFileUploader"] *,
        [data-testid="stFileUploaderDropzone"] *,
        [data-testid="stFileUploader"] section,
        [data-testid="stFileUploader"] small {
            color: var(--text-dark) !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: linear-gradient(180deg, rgba(245, 241, 232, 0.98) 0%, rgba(236, 229, 216, 0.94) 100%);
            border: 1px solid rgba(221, 212, 196, 0.98) !important;
            border-radius: 26px !important;
            box-shadow: var(--shadow-card);
            position: relative;
            overflow: hidden;
        }

        [data-testid="stVerticalBlockBorderWrapper"]::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--sand-500), var(--sage-600), var(--steel-500));
        }

        [data-testid="stVerticalBlockBorderWrapper"] p,
        [data-testid="stVerticalBlockBorderWrapper"] label,
        [data-testid="stVerticalBlockBorderWrapper"] .stCaption,
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"] {
            color: var(--text-mid) !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] h1,
        [data-testid="stVerticalBlockBorderWrapper"] h2,
        [data-testid="stVerticalBlockBorderWrapper"] h3,
        [data-testid="stVerticalBlockBorderWrapper"] h4 {
            color: var(--text-dark) !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stNumberInputContainer"],
        [data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="select"] > div,
        [data-testid="stVerticalBlockBorderWrapper"] .stTextInput input,
        [data-testid="stVerticalBlockBorderWrapper"] .stTextArea textarea {
            background: rgba(255, 255, 255, 0.86) !important;
            border: 1px solid #d8cfbe !important;
            border-radius: 16px !important;
            box-shadow: none !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stNumberInputContainer"] input,
        [data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="select"] input,
        [data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="select"] div,
        [data-testid="stVerticalBlockBorderWrapper"] .stTextArea textarea,
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stWidgetLabel"],
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stWidgetLabel"] p,
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"] *,
        [data-testid="stVerticalBlockBorderWrapper"] .st-emotion-cache-16txtl3,
        [data-testid="stVerticalBlockBorderWrapper"] .st-emotion-cache-1r4qj8v {
            color: var(--text-dark) !important;
            font-weight: 600;
        }

        .stButton > button,
        [data-testid="stDownloadButton"] > button {
            background: linear-gradient(180deg, #151816 0%, #202523 100%) !important;
            color: var(--mist-100) !important;
            border: 1px solid rgba(245, 241, 232, 0.14) !important;
            border-radius: 999px !important;
            font-weight: 600 !important;
            padding: 0.72rem 1.1rem !important;
            box-shadow: 0 14px 28px rgba(0, 0, 0, 0.18) !important;
            transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease !important;
        }

        .stButton > button:hover,
        [data-testid="stDownloadButton"] > button:hover {
            transform: translateY(-1px);
            border-color: rgba(143, 191, 167, 0.45) !important;
            box-shadow: 0 18px 30px rgba(0, 0, 0, 0.22) !important;
        }

        [data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(245, 241, 232, 0.98) 0%, rgba(236, 229, 216, 0.94) 100%);
            border: 1px solid rgba(221, 212, 196, 0.98);
            border-radius: 24px;
            padding: 18px 20px;
            box-shadow: var(--shadow-card);
            position: relative;
            overflow: hidden;
        }

        [data-testid="stMetric"]::before {
            content: "";
            position: absolute;
            left: 18px;
            right: 18px;
            top: 0;
            height: 4px;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--sand-500), var(--sage-600), var(--steel-500));
        }

        [data-testid="stMetricLabel"] {
            font-size: 11px !important;
            color: #647169 !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }

        [data-testid="stMetricValue"] {
            font-size: 28px !important;
            font-weight: 700 !important;
            color: var(--text-dark) !important;
        }

        [data-testid="stPlotlyChart"],
        [data-testid="stDataFrame"],
        [data-testid="stDataEditor"] {
            background: linear-gradient(180deg, rgba(245, 241, 232, 0.98) 0%, rgba(236, 229, 216, 0.94) 100%);
            border: 1px solid rgba(221, 212, 196, 0.98);
            border-radius: 26px;
            padding: 8px;
            box-shadow: var(--shadow-card);
            overflow: hidden;
            color: var(--text-dark) !important;
        }

        [data-testid="stDataFrame"] *,
        [data-testid="stDataEditor"] * {
            color: var(--text-dark) !important;
        }

        [data-testid="stExpander"] {
            background: linear-gradient(180deg, rgba(245, 241, 232, 0.98) 0%, rgba(236, 229, 216, 0.94) 100%);
            border: 1px solid rgba(221, 212, 196, 0.98) !important;
            border-radius: 24px !important;
            margin-bottom: 10px;
            overflow: hidden;
            box-shadow: var(--shadow-card);
        }

        [data-testid="stExpander"] *,
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary *,
        [data-testid="stExpanderDetails"] *,
        [data-testid="stExpanderToggleIcon"] {
            color: var(--text-dark) !important;
        }

        [data-testid="stAlert"] {
            border-radius: 18px !important;
            border: 1px solid rgba(221, 212, 196, 0.9) !important;
            color: var(--text-dark) !important;
        }

        [data-testid="stAlert"] * {
            color: var(--text-dark) !important;
        }

        [data-baseweb="checkbox"] *,
        [role="switch"] *,
        [data-baseweb="select"] *,
        [data-testid="stNumberInputContainer"] *,
        .stTextInput *,
        .stTextArea * {
            color: inherit;
        }

        code {
            color: #25463a;
            background: rgba(143, 191, 167, 0.14);
            padding: 0.12rem 0.32rem;
            border-radius: 6px;
        }

        @media (max-width: 1100px) {
            .hero-body {
                grid-template-columns: 1fr;
            }

            .hero-callout {
                justify-self: start;
            }
        }
    </style>
    """, unsafe_allow_html=True)


    def render_section_title(title):
        st.markdown(
            f'<div class="section-heading"><span>{title}</span></div>',
            unsafe_allow_html=True,
        )
 
    # ===== HEADER =====
    hero_col1, hero_col2 = st.columns([4.8, 1.6], vertical_alignment="center")
    with hero_col1:
        st.markdown(
            """
            <div class="app-hero">
                <div class="hero-meta">
                    <div class="eyebrow">Workforce Planning Studio</div>
                    <div class="hero-chip">Demonstration Interface</div>
                </div>
                <h1 class="title">Manpower Optimization, Reframed as an Executive Control Room</h1>
                <div class="hero-body">
                    <p class="subtitle">Upload workforce data, standardize job-family mappings, and run cost-aware optimization through a cleaner, presentation-ready interface designed for stakeholder reviews and decision workshops.</p>
                    <div class="hero-callout">
                        <div class="label">Interface Mode</div>
                        <p class="value">Boardroom Demo Flow</p>
                        <div class="note">Upload once, configure settings, run optimization, review outcomes.</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hero_col2:
        if CLIENT_LOGO_PATH.exists():
            logo_base64 = base64.b64encode(CLIENT_LOGO_PATH.read_bytes()).decode("utf-8")
            st.markdown(
                f"""
                <div class="logo-panel">
                    <img
                        src="data:image/png;base64,{logo_base64}"
                        alt="Client Logo"
                        style="max-width: 100%; max-height: 88px; object-fit: contain; display: block;"
                    />
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="logo-panel">
                    <p style='text-align:center;color:#ffffff;margin:0;font-weight:600;'>Client Logo</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("---")

    # ===== DETERMINE WORKFLOW STAGE =====
    stage = st.session_state.get('stage', 'upload_raw')

    # ===== STAGE 1: UPLOAD & PROCESS RAW DATA =====
    if stage == 'upload_raw':
        st.markdown("### 📋 Stage 1: Data Processing")
        st.markdown("Upload your Manpower.xlsx file (with Inhouse, Subcontractor, and Profession Mapping sheets)")
        st.caption(f"Configured job family universe: {TOTAL_CONFIGURED_JOB_FAMILIES}")
    
        uploaded_file = st.file_uploader("Choose Manpower.xlsx file", type=['xlsx'])
        if uploaded_file is not None:
            try:
                # Load all required sheets and normalize column names.
                inhouse_df, subcontractor_df = read_manpower_workbook(uploaded_file)

                # Drop fully empty rows from Excel exports.
                inhouse_df = inhouse_df[
                    ~(
                        inhouse_df['No'].apply(is_blank)
                        & inhouse_df['Location'].apply(is_blank)
                        & inhouse_df['Profession'].apply(is_blank)
                        & inhouse_df['Nationality'].apply(is_blank)
                    )
                ].copy()
                subcontractor_df = subcontractor_df[
                    ~(
                        subcontractor_df['No'].apply(is_blank)
                        & subcontractor_df['Working in'].apply(is_blank)
                        & subcontractor_df['Profession'].apply(is_blank)
                        & subcontractor_df['Nationality'].apply(is_blank)
                    )
                ].copy()
            
                st.success("✅ File loaded successfully.")
                st.info("🧭 Using embedded 3-step hierarchical mapping: Activity -> Profession -> Job Family")
            
                # ===== PROCESS INHOUSE DATA =====
                st.markdown("---")
                st.markdown("#### Processing In-House Staff...")
            
                # Step 1: Standardize Activity (Location -> Standardized Activity)
                inhouse_df['Activity_Standardized'] = inhouse_df['Location'].apply(
                    lambda x: NORMALIZED_ACTIVITY_MAPPING.get(
                        normalize_lookup_text(x),
                        clean_lookup_text(x),
                    )
                )
            
                # Step 2: Standardize Profession
                inhouse_df['Profession_Standardized'] = inhouse_df['Profession'].apply(
                    lambda x: NORMALIZED_PROFESSION_MAPPING.get(
                        normalize_lookup_text(x),
                        clean_lookup_text(x),
                    )
                )
            
                # Step 3: Merge Activity + Profession and map to Job Family
                inhouse_df['Activity_Profession'] = inhouse_df['Activity_Standardized'] + ' - ' + inhouse_df['Profession_Standardized']
                inhouse_df['Job_Family'] = inhouse_df['Activity_Profession'].apply(lambda x: get_job_family_with_fallback(x, JOB_FAMILY_MAPPING))
                inhouse_valid_for_mapping = (
                    inhouse_df['Activity_Standardized'].astype(str).str.strip().ne('')
                    & inhouse_df['Profession_Standardized'].astype(str).str.strip().ne('')
                )
                inhouse_unmapped = inhouse_df[inhouse_df['Job_Family'].isna() & inhouse_valid_for_mapping].copy()
                if not inhouse_unmapped.empty:
                    st.error(f"Unmapped in-house employees found: {len(inhouse_unmapped)}")
                    st.dataframe(
                        inhouse_unmapped[['No', 'Location', 'Profession', 'Activity_Profession']].head(50),
                        use_container_width=True
                    )
                    st.stop()
            
                inhouse_df['Is_Saudi'] = (inhouse_df['Nationality'] == 'SAUDI').astype(int)
                inhouse_df['Cost_Per_Employee'] = inhouse_df['Total Paid'] + inhouse_df['Total Unpaid']
                inhouse_df['Fully_Loaded_Inhouse_Cost_Per_Employee'] = inhouse_df.apply(
                    calculate_inhouse_fully_loaded_employee_cost,
                    axis=1,
                )
                inhouse_df['Saudi_Cost_Per_Employee'] = inhouse_df['Cost_Per_Employee'] * inhouse_df['Is_Saudi']
                inhouse_df['Non_Saudi_Cost_Per_Employee'] = inhouse_df['Cost_Per_Employee'] * (1 - inhouse_df['Is_Saudi'])
            
                # Add overtime cost (O.T Hrs) - assume 50 SAR/hr
                if 'O.T Hrs' in inhouse_df.columns:
                    overtime_cost = inhouse_df['O.T Hrs'].fillna(0) * 50
                    inhouse_df['Cost_Per_Employee'] += overtime_cost
                    inhouse_df['Saudi_Cost_Per_Employee'] += overtime_cost * inhouse_df['Is_Saudi']
                    inhouse_df['Non_Saudi_Cost_Per_Employee'] += overtime_cost * (1 - inhouse_df['Is_Saudi'])

                tenure_source_column, tenure_source_mode = detect_tenure_column(inhouse_df.columns)
                inhouse_df['Tenure Years'] = derive_tenure_years(
                    inhouse_df[tenure_source_column],
                    tenure_source_mode,
                ) if tenure_source_column else pd.Series(pd.NA, index=inhouse_df.index, dtype='float64')
                inhouse_df['Tenure Source Column'] = tenure_source_column if tenure_source_column else ''
                inhouse_df['Tenure Source Mode'] = tenure_source_mode if tenure_source_mode else ''
            
                inhouse_summary = inhouse_df.groupby('Job_Family').agg({
                    'No': 'count',
                    'Is_Saudi': 'sum',
                    'Cost_Per_Employee': 'sum',
                    'Fully_Loaded_Inhouse_Cost_Per_Employee': 'sum',
                    'Saudi_Cost_Per_Employee': 'sum',
                    'Non_Saudi_Cost_Per_Employee': 'sum'
                }).rename(columns={'No': 'Total_Inhouse', 'Is_Saudi': 'Saudi_Inhouse'})
            
                inhouse_summary['Non_Saudi_Inhouse'] = inhouse_summary['Total_Inhouse'] - inhouse_summary['Saudi_Inhouse']
                inhouse_summary['Avg_Cost_Saudi_Inhouse'] = inhouse_summary.apply(
                    lambda row: row['Saudi_Cost_Per_Employee'] / row['Saudi_Inhouse'] if row['Saudi_Inhouse'] > 0 else 0,
                    axis=1
                )
                inhouse_summary['Avg_Cost_NonSaudi_Inhouse'] = inhouse_summary.apply(
                    lambda row: row['Non_Saudi_Cost_Per_Employee'] / row['Non_Saudi_Inhouse'] if row['Non_Saudi_Inhouse'] > 0 else 0,
                    axis=1
                )
                inhouse_summary['Fully_Loaded_Cost_Per_Inhouse_Employee'] = inhouse_summary.apply(
                    lambda row: row['Fully_Loaded_Inhouse_Cost_Per_Employee'] / row['Total_Inhouse'] if row['Total_Inhouse'] > 0 else 0,
                    axis=1
                )
            
                st.write(
                    f"✅ Processed {len(inhouse_df)} in-house employees across "
                    f"{len(inhouse_summary)} of {TOTAL_CONFIGURED_JOB_FAMILIES} configured job families"
                )
            
                # ===== PROCESS SUBCONTRACTOR DATA =====
                st.markdown("#### Processing Subcontracted Staff...")
            
                # Step 1: Standardize Activity (Working in -> Standardized Activity)
                subcontractor_df['Activity_Standardized'] = subcontractor_df['Working in'].apply(
                    lambda x: NORMALIZED_ACTIVITY_MAPPING.get(
                        normalize_lookup_text(x),
                        clean_lookup_text(x),
                    )
                )
            
                # Step 2: Standardize Profession
                subcontractor_df['Profession_Standardized'] = subcontractor_df['Profession'].apply(
                    lambda x: NORMALIZED_PROFESSION_MAPPING.get(
                        normalize_lookup_text(x),
                        clean_lookup_text(x),
                    )
                )
            
                # Step 3: Merge Activity + Profession and map to Job Family
                subcontractor_df['Activity_Profession'] = subcontractor_df['Activity_Standardized'] + ' - ' + subcontractor_df['Profession_Standardized']
                subcontractor_df['Job_Family'] = subcontractor_df['Activity_Profession'].apply(lambda x: get_job_family_with_fallback(x, JOB_FAMILY_MAPPING))
                subcontractor_valid_for_mapping = (
                    subcontractor_df['Activity_Standardized'].astype(str).str.strip().ne('')
                    & subcontractor_df['Profession_Standardized'].astype(str).str.strip().ne('')
                )
                subcontractor_unmapped = subcontractor_df[
                    subcontractor_df['Job_Family'].isna() & subcontractor_valid_for_mapping
                ].copy()
                if not subcontractor_unmapped.empty:
                    st.error(f"Unmapped subcontracted employees found: {len(subcontractor_unmapped)}")
                    st.dataframe(
                        subcontractor_unmapped[['No', 'Working in', 'Profession', 'Activity_Profession']].head(50),
                        use_container_width=True
                    )
                    st.stop()
            
                subcontractor_df['Is_Saudi'] = (subcontractor_df['Nationality'] == 'SAUDI').astype(int)
            
                service_fee_column = detect_service_fee_column(subcontractor_df.columns)
                subcontractor_df['Service_Fee_Original'] = subcontractor_df[service_fee_column].apply(safe_numeric) if service_fee_column else 0.0
                subcontractor_df['Service_Fee_Negotiated'] = subcontractor_df['Service_Fee_Original'].apply(lambda value: min(value, 500.0))
                subcontractor_df['Negotiated_Service_Fee_Savings'] = (
                    subcontractor_df['Service_Fee_Original'] - subcontractor_df['Service_Fee_Negotiated']
                )
                subcontractor_df['Outsource_Base_Cost_Excluding_Insurance_Service'] = subcontractor_df.apply(
                    calculate_outsource_base_employee_cost,
                    axis=1,
                )
                subcontractor_df['Cost_Per_Employee'] = subcontractor_df.apply(
                    lambda row: calculate_outsource_employee_cost(row, service_fee_column=service_fee_column, negotiated_service_margin=False),
                    axis=1,
                )
                subcontractor_df['Negotiated_Cost_Per_Employee'] = subcontractor_df.apply(
                    lambda row: calculate_outsource_employee_cost(row, service_fee_column=service_fee_column, negotiated_service_margin=True),
                    axis=1,
                )
            
                subcontractor_summary = subcontractor_df.groupby('Job_Family').agg({
                    'No': 'count',
                    'Is_Saudi': 'sum',
                    'Outsource_Base_Cost_Excluding_Insurance_Service': 'sum',
                    'Cost_Per_Employee': 'sum',
                    'Negotiated_Cost_Per_Employee': 'sum',
                }).rename(columns={'No': 'Total_Outsourced', 'Is_Saudi': 'Saudi_Outsourced'})
            
                subcontractor_summary['Cost_Outsourced'] = subcontractor_summary['Cost_Per_Employee']
                subcontractor_summary['Avg_Cost_Per_Employee'] = subcontractor_summary.apply(
                    lambda row: row['Cost_Per_Employee'] / row['Total_Outsourced'] if row['Total_Outsourced'] > 0 else 0,
                    axis=1
                )
                subcontractor_summary['Avg_Base_Cost_Excluding_Insurance_Service'] = subcontractor_summary.apply(
                    lambda row: row['Outsource_Base_Cost_Excluding_Insurance_Service'] / row['Total_Outsourced'] if row['Total_Outsourced'] > 0 else 0,
                    axis=1
                )
                subcontractor_summary['Avg_Negotiated_Cost_Per_Employee'] = subcontractor_summary.apply(
                    lambda row: row['Negotiated_Cost_Per_Employee'] / row['Total_Outsourced'] if row['Total_Outsourced'] > 0 else 0,
                    axis=1
                )

                mapped_workforce_df = pd.concat(
                    [
                        inhouse_df[["Activity_Standardized", "Profession_Standardized", "Job_Family"]],
                        subcontractor_df[["Activity_Standardized", "Profession_Standardized", "Job_Family"]],
                    ],
                    ignore_index=True,
                )
                current_driver_values = calculate_driver_values(mapped_workforce_df)
            
                st.write(
                    f"✅ Processed {len(subcontractor_df)} subcontracted employees across "
                    f"{len(subcontractor_summary)} of {TOTAL_CONFIGURED_JOB_FAMILIES} configured job families"
                )
                if service_fee_column:
                    st.caption(f"Service margin detected using `{service_fee_column}`.")
                else:
                    st.caption("No service margin column was detected in the subcontractor sheet.")
            
                # ===== MERGE & CREATE OPTIMIZATION INPUT =====
                st.markdown("#### Generating Optimization Input...")
                ratio_rules_df = load_ratio_rules()
                ratio_rules = ratio_rules_df.set_index('Job Family Key').to_dict('index') if not ratio_rules_df.empty else {}
            
                # Get all job families from both inhouse and subcontractor data
                all_job_families = set(inhouse_summary.index) | set(subcontractor_summary.index)
                optimization_data = []
            
                for job_family in sorted(all_job_families):
                    inhouse_row = inhouse_summary.loc[job_family] if job_family in inhouse_summary.index else None
                    outsource_row = subcontractor_summary.loc[job_family] if job_family in subcontractor_summary.index else None
                
                    # Calculate totals
                    total_inhouse = inhouse_row['Total_Inhouse'] if inhouse_row is not None else 0
                    total_outsourced = outsource_row['Total_Outsourced'] if outsource_row is not None else 0
                    total_employees = total_inhouse + total_outsourced
                
                    total_inhouse_saudi = int(inhouse_row['Saudi_Inhouse']) if inhouse_row is not None else 0
                    total_inhouse_non_saudi = int(total_inhouse - total_inhouse_saudi)
                
                    # Calculate average costs per employee
                    avg_cost_inhouse_saudi = inhouse_row['Avg_Cost_Saudi_Inhouse'] if inhouse_row is not None else 0
                    avg_cost_inhouse_non_saudi = inhouse_row['Avg_Cost_NonSaudi_Inhouse'] if inhouse_row is not None else 0
                    fully_loaded_cost_inhouse = inhouse_row['Fully_Loaded_Cost_Per_Inhouse_Employee'] if inhouse_row is not None else 0
                    avg_cost_outsourced = outsource_row['Avg_Cost_Per_Employee'] if outsource_row is not None else 0
                    avg_outsource_base_cost = outsource_row['Avg_Base_Cost_Excluding_Insurance_Service'] if outsource_row is not None else pd.NA
                    avg_cost_outsourced_negotiated = outsource_row['Avg_Negotiated_Cost_Per_Employee'] if outsource_row is not None else 0
                
                    ratio_rule, _, _ = lookup_ratio_rule(job_family, ratio_rules)
                    outsourceability_type = OUTSOURCEABILITY_RULES.get(job_family, 'Partially Outsourceable')
                    driver_value = ratio_rule.get('Driver Value')

                    if job_family in current_driver_values:
                        driver_value = current_driver_values[job_family]
                    else:
                        driver_value = pd.NA
                    current_outsourced_ratio = safe_divide(total_outsourced, total_employees)
                    maximum_ratio = MAXIMUM_RATIO_RULES.get(job_family, 'N/A')
                    minimum_headcount_needed = calculate_minimum_headcount_needed(
                        total_employees,
                        outsourceability_type,
                        driver_value,
                        maximum_ratio,
                        total_inhouse,
                    )

                    if outsourceability_type == "Fully Outsourceable":
                        max_outsource_ratio = "100%"
                        max_outsource_ratio_value = 1.0
                    elif outsourceability_type == "Not Outsourceable":
                        max_outsource_ratio = "0%"
                        max_outsource_ratio_value = 0.0
                    else:
                        max_outsource_ratio = "TBD"
                        if job_family in {"Administration", "Engineer"}:
                            max_outsource_ratio_value = current_outsourced_ratio
                        else:
                            max_outsource_ratio_value = 0.5  # Temporary internal default until final partial rules are provided.
                
                    if total_employees > 0:
                        optimization_data.append({
                            'Job Family': job_family,
                            'Outsourceability Type': outsourceability_type,
                            'Driver Value': driver_value,
                            'Current Ratio': build_current_ratio_display(total_employees, driver_value),
                            'Maximum Ratio': maximum_ratio,
                            'Minimum Headcount Needed': minimum_headcount_needed,
                            'Current Outsourced Ratio': safe_numeric(current_outsourced_ratio),
                            'Avg Cost Non-Saudi Inhouse': avg_cost_inhouse_non_saudi,
                            'Avg Cost Saudi Inhouse': avg_cost_inhouse_saudi,
                            'Avg Cost Outsourced': avg_cost_outsourced,
                            'Avg Cost Outsourced Original': avg_cost_outsourced,
                            'Avg Cost Outsourced Negotiated': avg_cost_outsourced_negotiated,
                            'Avg Outsourced Base Cost Excluding Insurance Service': avg_outsource_base_cost,
                            'Fully Loaded Cost per In-house Employee': fully_loaded_cost_inhouse,
                            'Current Headcount': int(total_employees),
                            'Current In-House Count': int(total_inhouse),
                            'Current Outsourced Count': int(total_outsourced),
                            'Total Inhouse Saudi': total_inhouse_saudi,
                            'Current In-House Non-Saudi Count': int(total_inhouse_non_saudi),
                            'Max Outsource Ratio': max_outsource_ratio,
                            'Max Outsource Ratio Value': max_outsource_ratio_value,
                        })
            
                optimization_df = pd.DataFrame(optimization_data)
                resolved_avg_costs = optimization_df.apply(
                    lambda row: resolve_average_costs(
                        row['Avg Cost Saudi Inhouse'],
                        row['Avg Cost Non-Saudi Inhouse'],
                        row['Avg Cost Outsourced'],
                    ),
                    axis=1,
                )
                optimization_df[['Avg Cost Saudi Inhouse', 'Avg Cost Non-Saudi Inhouse', 'Avg Cost Outsourced']] = resolved_avg_costs

                if 'Avg Cost Outsourced Negotiated' in optimization_df.columns:
                    resolved_negotiated_outsourced = optimization_df.apply(
                        lambda row: resolve_average_costs(
                            row['Avg Cost Saudi Inhouse'],
                            row['Avg Cost Non-Saudi Inhouse'],
                            row['Avg Cost Outsourced Negotiated'],
                        )['Avg Cost Outsourced'],
                        axis=1,
                    )
                    optimization_df['Avg Cost Outsourced Negotiated'] = resolved_negotiated_outsourced

                if 'Avg Cost Outsourced Original' in optimization_df.columns:
                    optimization_df['Avg Cost Outsourced Original'] = optimization_df['Avg Cost Outsourced']

                optimization_df['Fully Loaded Cost per In-house Employee'] = optimization_df.apply(
                    lambda row: 1.2 * safe_numeric(row['Avg Cost Outsourced'])
                    if safe_numeric(row.get('Current In-House Count')) == 0
                    else safe_numeric(row.get('Fully Loaded Cost per In-house Employee')),
                    axis=1,
                )
                optimization_df[
                    [
                        'Fully Loaded Cost per In-house Non-Saudi Employee',
                        'Fully Loaded Cost per In-house Saudi Employee',
                    ]
                ] = optimization_df.apply(
                    lambda row: calculate_inhouse_cost_split(
                        row['Fully Loaded Cost per In-house Employee'],
                        row['Total Inhouse Saudi'],
                        row['Current In-House Non-Saudi Count'],
                    ),
                    axis=1,
                )

                st.write(
                    f"🧩 Created optimization input with {len(optimization_df)} of "
                    f"{TOTAL_CONFIGURED_JOB_FAMILIES} configured job families"
                )
            
                # Store the processed model inputs and move directly into the optimization settings.
                st.session_state.optimization_df = optimization_df
                st.session_state.inhouse_cleaned = inhouse_df
                st.session_state.subcontractor_cleaned = subcontractor_df
                st.session_state.optimization_has_run = False
                st.session_state.stage = 'optimize'
                st.rerun()
        
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
                import traceback
                st.write(traceback.format_exc())

    # ===== STAGE 2: OPTIMIZATION =====
    elif stage == 'optimize':
    
        # Back button at top
        if st.button("← Back to Data Processing"):
            st.session_state.stage = 'upload_raw'
            st.session_state.pop('optimization_df', None)
            st.session_state.pop('optimization_has_run', None)
            st.rerun()
    
        st.markdown("---")
        render_section_title("Optimization Settings")

        inhouse_cleaned = st.session_state.get('inhouse_cleaned', pd.DataFrame())
        tenure_data_available = (
            not inhouse_cleaned.empty
            and 'Tenure Years' in inhouse_cleaned.columns
            and inhouse_cleaned['Tenure Years'].notna().any()
        )
        tenure_source_label = ""
        if tenure_data_available and 'Tenure Source Column' in inhouse_cleaned.columns:
            tenure_source_label = next(
                (
                    str(value) for value in inhouse_cleaned['Tenure Source Column']
                    if pd.notna(value) and str(value).strip() != ""
                ),
                "",
            )

        settings_col1, settings_col2, settings_col3, settings_col4, settings_col5 = st.columns([1.15, 1.0, 1.0, 1.15, 0.9])

        with settings_col1:
            with st.container(border=True):
                st.markdown("#### Saudization")
                enforce_saudization = st.toggle("Enforce overall Saudization Rate?", value=True)
                SAUDIZATION_RATE = None
                if enforce_saudization:
                    SAUDIZATION_RATE = st.number_input(
                        "Saudization Rate (decimal)",
                        min_value=0.0, max_value=1.0, value=0.3, step=0.01, format="%.2f"
                    )
                    st.markdown(f"<p style='color:#24312c;font-weight:600;margin:0.35rem 0 0;'>Target set to {SAUDIZATION_RATE*100:.1f}%.</p>", unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color:#40514a;font-weight:600;margin:0.35rem 0 0;'>No Saudization Rate constraint.</p>", unsafe_allow_html=True)

                st.markdown("#### Saudization by profession")
                engineer_saudization_rate = st.number_input(
                    "Engineers",
                    min_value=0.0, max_value=1.0, value=0.25, step=0.01, format="%.2f",
                    key="engineer_saudization_rate",
                )
                sales_saudization_rate = st.number_input(
                    "Sales Professions",
                    min_value=0.0, max_value=1.0, value=0.60, step=0.01, format="%.2f",
                    key="sales_saudization_rate",
                )
                management_saudization_rate = st.number_input(
                    "Management roles",
                    min_value=0.0, max_value=1.0, value=0.35, step=0.01, format="%.2f",
                    key="management_saudization_rate",
                )

        with settings_col2:
            with st.container(border=True):
                st.markdown("#### Saudi Labor Policy")
                can_fire_saudi = st.toggle("Allow reducing current Saudi headcount?", value=False)
                if can_fire_saudi:
                    st.caption("Current Saudi labor may be reduced below present levels.")
                else:
                    st.caption("Current Saudi labor is protected as a minimum.")

        with settings_col3:
            with st.container(border=True):
                st.markdown("#### Outsourcing Controls")
                risk_factor = st.number_input(
                    "Risk factor",
                    min_value=0.0, max_value=1.0, value=0.25, step=0.01, format="%.2f"
                )
                negotiated_rates = st.toggle("Negotiated Rates", value=False)
                negotiated_insurance_cost_input = st.text_input(
                    "Negotiated Insurance Cost",
                    value="",
                    disabled=not negotiated_rates,
                )
                negotiated_service_margin_input = st.text_input(
                    "Negotiated Service Margin",
                    value="",
                    disabled=not negotiated_rates,
                )
                st.markdown("<p style='color:#24312c;font-weight:600;margin:0.35rem 0 0;'>Outsourced v1 uses the risk factor after minimum headcount is calculated.</p>", unsafe_allow_html=True)
                st.markdown("<p style='color:#40514a;font-weight:600;margin:0.35rem 0 0;'>Negotiated rates calculate a separate outsourced FTE cost column.</p>", unsafe_allow_html=True)

        with settings_col4:
            with st.container(border=True):
                st.markdown("#### Tenure Protection")
                protect_tenured_inhouse = st.toggle("Protect tenured in-house employees?", value=False)
                tenure_threshold_years = st.number_input(
                    "Minimum tenure (years)",
                    min_value=0.0, max_value=60.0, value=5.0, step=0.5, format="%.1f",
                    disabled=not protect_tenured_inhouse,
                )
                if tenure_data_available:
                    tenure_caption = f"Tenure will be evaluated using `{tenure_source_label}`." if tenure_source_label else "Tenure data is available for in-house employees."
                    st.markdown(f"<p style='color:#24312c;font-weight:600;margin:0.35rem 0 0;'>{tenure_caption}</p>", unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color:#8a5a3b;font-weight:600;margin:0.35rem 0 0;'>No tenure data detected in the uploaded in-house sheet.</p>", unsafe_allow_html=True)

        with settings_col5:
            with st.container(border=True):
                st.markdown("#### Actions")
                calculate_target_split = st.button("Calculate Target Split", use_container_width=True)
                run = st.button("Run Optimization", type="primary", use_container_width=True)
                st.caption("Review targets first, then run the optimization.")

        if 'optimization_has_run' not in st.session_state:
            st.session_state.optimization_has_run = False
        if run:
            st.session_state.optimization_has_run = True

        tenure_constraint_active = bool(protect_tenured_inhouse and tenure_data_available)
        if protect_tenured_inhouse and not tenure_data_available:
            st.warning("Tenure protection was turned on, but no tenure column was detected. The model will continue without the tenure constraint until tenure data is available in the in-house sheet.")

        # ===== PREPARE DATA =====
        optimization_df = st.session_state.optimization_df
    
        # Convert to the format expected by optimization
        data = optimization_df.copy()
        data['Current Ratio'] = data.apply(
            lambda row: build_current_ratio_display(row['Current Headcount'], row['Driver Value']),
            axis=1,
        )
        data['Maximum Ratio'] = data['Job Family'].map(MAXIMUM_RATIO_RULES).fillna('N/A')
        data['Risk Factor'] = risk_factor
        data = data.drop(columns=['Target Outsourced'], errors='ignore')
        data['Minimum Headcount Needed'] = data.apply(
            lambda row: calculate_minimum_headcount_needed(
                row['Current Headcount'],
                row['Outsourceability Type'],
                row['Driver Value'],
                row['Maximum Ratio'],
                row.get('Current In-House Count', 0),
            ),
            axis=1,
        )
        data['Outsourced v1'] = data.apply(lambda row: calculate_outsourced_v1(row, risk_factor), axis=1)
        data['In-house v1'] = data.apply(
            lambda row: max(0, int(safe_numeric(row['Current Headcount'])) - int(safe_numeric(row['Outsourced v1']))),
            axis=1,
        )

        tenure_summary_columns = [
            'Tenured In-House Count',
            'Tenured Saudi In-House',
            'Tenured Non-Saudi In-House',
            'Tenured Saudi Cost Total',
            'Tenured Non-Saudi Cost Total',
            'Avg Cost Saudi Tenured Inhouse',
            'Avg Cost Non-Saudi Tenured Inhouse',
        ]
        data = data.drop(
            columns=[column for column in tenure_summary_columns if column in data.columns],
            errors='ignore',
        )

        tenured_summary = summarize_tenured_inhouse(inhouse_cleaned, tenure_threshold_years) if tenure_constraint_active else pd.DataFrame()
        if not tenured_summary.empty:
            data = data.merge(tenured_summary, left_on='Job Family', right_index=True, how='left')

        for column in tenure_summary_columns:
            if column not in data.columns:
                data[column] = 0.0
            data[column] = pd.to_numeric(data[column], errors='coerce').fillna(0.0)

        data = data.drop(columns=['Base Minimum In-House'], errors='ignore')
        data['Tenure Constraint Active'] = 'Yes' if tenure_constraint_active else 'No'
        data['Tenure Threshold (Years)'] = tenure_threshold_years if tenure_constraint_active else pd.NA
        # Match prepare_model_data (manpower_app.service): LP reads Minimum Headcount Needed;
        # tenure floor must be merged into this column, not kept only on a side column.
        base_minimum_headcount_needed = data['Minimum Headcount Needed'].apply(
            lambda value: int(safe_numeric(value)),
        )
        data['Minimum Headcount Needed'] = data.apply(
            lambda row: max(
                int(safe_numeric(row['Minimum Headcount Needed'])),
                int(safe_numeric(row['Tenured In-House Count'])) if tenure_constraint_active else 0,
            ),
            axis=1,
        )
        data['Tenure Driven Minimum'] = data.apply(
            lambda row: 'Yes'
            if tenure_constraint_active
            and safe_numeric(row['Tenured In-House Count']) > safe_numeric(base_minimum_headcount_needed.loc[row.name])
            else 'No',
            axis=1,
        )
        data['Effective Avg Cost Saudi Inhouse'] = data.apply(
            lambda row: row['Avg Cost Saudi Tenured Inhouse']
            if row['Tenure Driven Minimum'] == 'Yes' and safe_numeric(row['Avg Cost Saudi Tenured Inhouse']) > 0
            else row['Avg Cost Saudi Inhouse'],
            axis=1,
        )
        data['Effective Avg Cost Non-Saudi Inhouse'] = data.apply(
            lambda row: row['Avg Cost Non-Saudi Tenured Inhouse']
            if row['Tenure Driven Minimum'] == 'Yes' and safe_numeric(row['Avg Cost Non-Saudi Tenured Inhouse']) > 0
            else row['Avg Cost Non-Saudi Inhouse'],
            axis=1,
        )
        data['In-House Cost Basis'] = data.apply(
            lambda row: 'Tenured in-house average cost'
            if row['Tenure Driven Minimum'] == 'Yes'
            else 'Overall in-house average cost',
            axis=1,
        )

        outsource_type = "Current"
        if 'Avg Cost Outsourced Original' in data.columns:
            data['Avg Cost Outsourced'] = data['Avg Cost Outsourced Original']

        negotiated_insurance_cost = safe_numeric(negotiated_insurance_cost_input)
        negotiated_service_margin = safe_numeric(negotiated_service_margin_input)
        data['Negotiated cost per outsourced FTE'] = data.apply(
            lambda row: (
                safe_numeric(row.get('Avg Outsourced Base Cost Excluding Insurance Service'))
                + negotiated_insurance_cost
                + negotiated_service_margin
            )
            if negotiated_rates and pd.notna(row.get('Avg Outsourced Base Cost Excluding Insurance Service'))
            else (safe_numeric(row['Avg Cost Outsourced']) if negotiated_rates else pd.NA),
            axis=1,
        )
        data['Payroll v3 Outsourced Cost Basis'] = data.apply(
            lambda row: safe_numeric(row['Negotiated cost per outsourced FTE'])
            if negotiated_rates and pd.notna(row.get('Negotiated cost per outsourced FTE'))
            else safe_numeric(row['Avg Cost Outsourced']),
            axis=1,
        )

        data, payroll_v2, payroll_v2_status = calculate_payroll_v2_plan(
            data,
            enforce_saudization,
            SAUDIZATION_RATE if enforce_saudization else 0.0,
        )
        data, payroll_v3, payroll_v3_status = calculate_payroll_v3_plan(
            data,
            enforce_saudization,
            SAUDIZATION_RATE if enforce_saudization else 0.0,
            can_fire_saudi,
        )
        data, payroll_v4, payroll_v4_status = calculate_payroll_v4_plan(
            data,
            enforce_saudization,
            SAUDIZATION_RATE if enforce_saudization else 0.0,
            can_fire_saudi,
            tenure_constraint_active,
        )
        profession_saudization_rates = {
            normalize_lookup_text('Engineer'): engineer_saudization_rate,
            normalize_lookup_text('Representative'): sales_saudization_rate,
            normalize_lookup_text('Executive Management'): management_saudization_rate,
        }
        data, payroll_v5, payroll_v5_status = calculate_payroll_v5_plan(
            data,
            enforce_saudization,
            SAUDIZATION_RATE if enforce_saudization else 0.0,
            can_fire_saudi,
            tenure_constraint_active,
            profession_saudization_rates,
        )
        payroll_v5_results = build_payroll_v5_results(data, payroll_v5_status)
        current_payroll_cost = (
            data['Current Outsourced Count'] * data['Avg Cost Outsourced']
            + data['Current In-House Count'] * data['Fully Loaded Cost per In-house Employee']
        ).sum()
        payroll_v5_savings = safe_divide(current_payroll_cost - payroll_v5, current_payroll_cost)

        if st.session_state.optimization_has_run:
            st.markdown(
                """
                <div class="stage-panel" style="margin-top: 10px; margin-bottom: 10px;">
                    <div class="stage-kicker">Model Input</div>
                    <h2 class="stage-title" style="font-size:24px;">Optimization inputs are prepared behind the scenes.</h2>
                    <p class="stage-copy">The debug input editor stays hidden in this demonstration flow, but the job-family processing table below exposes the calculations used by the model, including tenure protection when it is active.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            payroll_col1, payroll_col2, payroll_col3 = st.columns(3)
            with payroll_col1:
                st.metric("Current Payroll Cost", f"SAR {current_payroll_cost:,.0f}")
            with payroll_col2:
                st.metric("Optimized payroll", f"SAR {payroll_v5:,.0f}")
            with payroll_col3:
                st.metric("Savings", f"{payroll_v5_savings:.1%}")
            if payroll_v2_status not in {"Optimal", "Current"}:
                st.warning(f"Payroll v2 optimization status: {payroll_v2_status}. Current workforce counts are shown as the fallback.")
            if payroll_v3_status not in {"Optimal", "Matches v2"}:
                st.warning(f"Payroll v3 optimization status: {payroll_v3_status}. Payroll v2 counts are shown as the fallback.")
            if payroll_v4_status not in {"Optimal", "Matches v3"}:
                st.warning(f"Payroll v4 optimization status: {payroll_v4_status}. Payroll v3 counts are shown as the fallback.")
            if payroll_v5_status not in {"Optimal", "Matches v4"}:
                st.warning(
                    "Final scenario optimization status: %s. Prior-step counts are shown as the fallback."
                    % (payroll_v5_status,)
                )
            st.session_state.current_payroll_cost = current_payroll_cost
            st.session_state.payroll_v2 = payroll_v2
            st.session_state.payroll_v2_status = payroll_v2_status
            st.session_state.payroll_v3 = payroll_v3
            st.session_state.payroll_v3_status = payroll_v3_status
            st.session_state.payroll_v4 = payroll_v4
            st.session_state.payroll_v4_status = payroll_v4_status
            st.session_state.payroll_v5 = payroll_v5
            st.session_state.payroll_v5_savings = payroll_v5_savings
            st.session_state.payroll_v5_status = payroll_v5_status
            st.session_state.results_df = payroll_v5_results['results_df']
            st.session_state.total_cost = payroll_v5_results['total_cost']
            st.session_state.total_saudi_final = payroll_v5_results['total_saudi_final']
            st.session_state.total_non_saudi_final = payroll_v5_results['total_non_saudi_final']
            st.session_state.total_outsourced_final = payroll_v5_results['total_outsourced_final']
            st.session_state.total_employees_final = payroll_v5_results['total_employees_final']
            st.session_state.saudization_achieved = payroll_v5_results['saudization_achieved']
            st.session_state.optimization_status = payroll_v5_results['optimization_status']
            st.session_state.total_cost_saudi = payroll_v5_results['total_cost_saudi']
            st.session_state.total_cost_non_saudi = payroll_v5_results['total_cost_non_saudi']
            st.session_state.total_cost_outsourced = payroll_v5_results['total_cost_outsourced']
            st.session_state.outsource_type = "Final optimized scenario"
            st.session_state.optimization_df = data.copy()
            st.session_state.processing_debug_df = data.copy()
        else:
            for key in [
                'current_payroll_cost',
                'payroll_v2',
                'payroll_v2_status',
                'payroll_v3',
                'payroll_v3_status',
                'payroll_v4',
                'payroll_v4_status',
                'payroll_v5',
                'payroll_v5_savings',
                'payroll_v5_status',
                'results_df',
                'total_cost',
                'total_saudi_final',
                'total_non_saudi_final',
                'total_outsourced_final',
                'total_employees_final',
                'saudization_achieved',
                'optimization_status',
                'total_cost_saudi',
                'total_cost_non_saudi',
                'total_cost_outsourced',
                'outsource_type',
                'processing_debug_df',
            ]:
                st.session_state.pop(key, None)
            st.session_state.optimization_df = data.copy()
            st.info("Review the settings, then click Run Optimization to generate the final scenario results.")
    
        if calculate_target_split:
            st.session_state.target_split_df = calculate_target_split_from_data(data)
            st.success("Target split calculated successfully.")

        # ===== RUN OPTIMIZATION =====
        if run:
            st.success("Optimization completed. Final scenario results are shown below.")

        if False and run:
            with st.spinner("Optimizing workforce allocation..."):
                try:
                    prob = pulp.LpProblem("Manpower_Optimization", pulp.LpMinimize)
                    S, N, O = [], [], []
    
                    for i in range(len(data)):
                        current_saudi = int(safe_numeric(data.iloc[i]['Total Inhouse Saudi']))
                        total_employees = int(safe_numeric(data.iloc[i]['Current Headcount']))
                        outsourceability_type = data.iloc[i]['Outsourceability Type']
                        effective_min_inhouse = int(safe_numeric(data.iloc[i]['Minimum Headcount Needed']))
                        tenured_saudi = int(safe_numeric(data.iloc[i]['Tenured Saudi In-House'])) if tenure_constraint_active else 0
                        tenured_non_saudi = int(safe_numeric(data.iloc[i]['Tenured Non-Saudi In-House'])) if tenure_constraint_active else 0

                        base_saudi_lower_bound = 0 if can_fire_saudi or outsourceability_type == "Fully Outsourceable" else current_saudi
                        saudi_lower_bound = max(base_saudi_lower_bound, tenured_saudi)
                        non_saudi_lower_bound = tenured_non_saudi
                        max_outsourced_headcount = max(0, total_employees - effective_min_inhouse)

                        s = pulp.LpVariable(f'S_{i}', lowBound=saudi_lower_bound, cat='Integer')
                        n = pulp.LpVariable(f'N_{i}', lowBound=non_saudi_lower_bound, cat='Integer')
                        o = pulp.LpVariable(f'O_{i}', lowBound=0, upBound=max_outsourced_headcount, cat='Integer')
                        S.append(s); N.append(n); O.append(o)
    
                        prob += s + n + o == total_employees, f"Total_Employees_{i}"
                        prob += s + n >= effective_min_inhouse, f"Effective_Min_Inhouse_{i}"
                        if outsourceability_type == "Not Outsourceable":
                            prob += o == 0, f"Not_Outsourceable_{i}"
    
                    # Objective: minimize total cost using average costs per employee
                    prob += pulp.lpSum(
                        data.iloc[i]['Effective Avg Cost Saudi Inhouse'] * S[i] +
                        data.iloc[i]['Effective Avg Cost Non-Saudi Inhouse'] * N[i] +
                        data.iloc[i]['Avg Cost Outsourced'] * O[i]
                        for i in range(len(data))
                    )
    
                    if enforce_saudization:
                        prob += pulp.lpSum(S) >= SAUDIZATION_RATE * pulp.lpSum(S[i] + N[i] for i in range(len(data))), "Saudization_Rate"
    
                    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    
                    if pulp.LpStatus[prob.status] == 'Optimal':
                        results_data = []
                        for i in range(len(data)):
                            saudi = int(S[i].varValue)
                            non_saudi = int(N[i].varValue)
                            outsourced = int(O[i].varValue)
                        
                            # Calculate costs using the active in-house cost basis for the job family
                            cost_saudi = data.iloc[i]['Effective Avg Cost Saudi Inhouse'] * saudi
                            cost_non_saudi = data.iloc[i]['Effective Avg Cost Non-Saudi Inhouse'] * non_saudi
                            cost_outsourced = data.iloc[i]['Avg Cost Outsourced'] * outsourced
                        
                            results_data.append({
                                'Job Family': data.iloc[i]['Job Family'],
                                'Saudi Labor': saudi,
                                'In-House Non-Saudi Labor': non_saudi,
                                'Outsourced Labor': outsourced,
                                'Total Employees Headcount': saudi + non_saudi + outsourced,
                                'Cost - Saudi Labor (SAR)': cost_saudi,
                                'Cost - In-House Non-Saudi Labor (SAR)': cost_non_saudi,
                                'Cost - Outsourced Labor (SAR)': cost_outsourced,
                                'Total Cost (SAR)': cost_saudi + cost_non_saudi + cost_outsourced
                            })
    
                        results_df = pd.DataFrame(results_data)
                        total_saudi_final = sum(int(S[i].varValue) for i in range(len(data)))
                        total_non_saudi_final = sum(int(N[i].varValue) for i in range(len(data)))
                        total_outsourced_final = sum(int(O[i].varValue) for i in range(len(data)))
                        total_employees_final = total_saudi_final + total_non_saudi_final + total_outsourced_final
                        total_inhouse_final = total_saudi_final + total_non_saudi_final
                        saudization_achieved = (total_saudi_final / total_inhouse_final * 100) if total_inhouse_final > 0 else 0
    
                        st.session_state.results_df = results_df
                        st.session_state.total_cost = pulp.value(prob.objective)
                        st.session_state.total_saudi_final = total_saudi_final
                        st.session_state.total_non_saudi_final = total_non_saudi_final
                        st.session_state.total_outsourced_final = total_outsourced_final
                        st.session_state.total_employees_final = total_employees_final
                        st.session_state.saudization_achieved = saudization_achieved
                        st.session_state.optimization_status = "Optimal"
                        st.session_state.total_cost_saudi = results_df['Cost - Saudi Labor (SAR)'].sum()
                        st.session_state.total_cost_non_saudi = results_df['Cost - In-House Non-Saudi Labor (SAR)'].sum()
                        st.session_state.total_cost_outsourced = results_df['Cost - Outsourced Labor (SAR)'].sum()
                        st.session_state.outsource_type = outsource_type
                        st.success("✅ Optimization completed successfully.")
                    else:
                        st.error(f"Optimization failed: {pulp.LpStatus[prob.status]}")
    
                except Exception as e:
                    st.error(f"Error during optimization: {str(e)}")
                    import traceback
                    st.write(traceback.format_exc())
    
        if 'target_split_df' in st.session_state:
            st.markdown("---")
            render_section_title("Target Split by Job Family")
            target_display_df = st.session_state.target_split_df.copy()
            if 'Minimum Headcount Needed' not in target_display_df.columns and 'Target In-House Headcount' in target_display_df.columns:
                target_display_df = target_display_df.rename(columns={'Target In-House Headcount': 'Minimum Headcount Needed'})
            target_display_df = target_display_df.drop(
                columns=[
                    'Target Outsourced',
                    'Target Outsourced Headcount',
                    'Outsourcing Ratio',
                    'Effective Outsourced Workforce',
                ],
                errors='ignore',
            )
            target_display_df['Driver Value'] = target_display_df['Driver Value'].apply(
                lambda x: f"{safe_numeric(x):,.0f}" if pd.notna(x) else "N/A"
            )
            target_display_df['Current Headcount'] = target_display_df['Current Headcount'].apply(lambda x: f"{int(x):,}")
            target_display_df['Current Ratio'] = target_display_df['Current Ratio'].apply(
                lambda x: f"1:{int(math.floor(safe_numeric(x) + 0.5))}" if safe_numeric(x) > 0 else "N/A"
            )
            target_display_df['Minimum Required In-House Headcount'] = target_display_df['Minimum Required In-House Headcount'].apply(lambda x: f"{int(x):,}")
            target_display_df['Minimum Headcount Needed'] = target_display_df['Minimum Headcount Needed'].apply(lambda x: f"{int(x):,}")
            st.dataframe(target_display_df, use_container_width=True)

        if 'processing_debug_df' in st.session_state:
            st.markdown("---")
            render_section_title("Model Processing by Job Family")
            debug_display_df = st.session_state.processing_debug_df.copy()
            debug_columns = [
                'Job Family',
                'Current Headcount',
                'Current In-House Count',
                'Current Outsourced Count',
                'Total Inhouse Saudi',
                'Current In-House Non-Saudi Count',
                'Current Outsourced Ratio',
                'Driver Value',
                'Current Ratio',
                'Maximum Ratio',
                'Minimum Headcount Needed',
                'Outsourced v1',
                'In-house v1',
                'Avg Cost Outsourced',
                'Fully Loaded Cost per In-house Employee',
                'Fully Loaded Cost per In-house Non-Saudi Employee',
                'Fully Loaded Cost per In-house Saudi Employee',
                'Outsourced v2',
                'In-house Non Saudi v2',
                'In-house Saudi v2',
                'Outsourced v3',
                'In-house Non Saudi v3',
                'In-house Saudi v3',
                'Negotiated cost per outsourced FTE',
                'Tenure Constraint Active',
                'Tenure Threshold (Years)',
                'Tenured In-House Count',
                'Tenured Saudi In-House',
                'Tenured Non-Saudi In-House',
                'Outsourced v4',
                'In-house Non Saudi v4',
                'In-house Saudi v4',
                'Outsourced v5',
                'In-house Non Saudi v5',
                'In-house Saudi v5',
                'Effective Minimum In-House',
                'Tenure Driven Minimum',
                'In-House Cost Basis',
                'Avg Cost Saudi Inhouse',
                'Avg Cost Non-Saudi Inhouse',
                'Avg Cost Saudi Tenured Inhouse',
                'Avg Cost Non-Saudi Tenured Inhouse',
                'Effective Avg Cost Saudi Inhouse',
                'Effective Avg Cost Non-Saudi Inhouse',
                'Max Outsource Ratio',
                'Outsourceability Type',
            ]
            debug_display_df = debug_display_df[[column for column in debug_columns if column in debug_display_df.columns]].copy()
            for column in [
                'Current Headcount',
                'Current In-House Count',
                'Current Outsourced Count',
                'Total Inhouse Saudi',
                'Current In-House Non-Saudi Count',
                'Driver Value',
                'Minimum Headcount Needed',
                'Outsourced v1',
                'In-house v1',
                'Tenured In-House Count',
                'Tenured Saudi In-House',
                'Tenured Non-Saudi In-House',
                'Outsourced v4',
                'In-house Non Saudi v4',
                'In-house Saudi v4',
                'Outsourced v5',
                'In-house Non Saudi v5',
                'In-house Saudi v5',
                'Effective Minimum In-House',
                'Outsourced v2',
                'In-house Non Saudi v2',
                'In-house Saudi v2',
                'Outsourced v3',
                'In-house Non Saudi v3',
                'In-house Saudi v3',
            ]:
                if column in debug_display_df.columns:
                    debug_display_df[column] = debug_display_df[column].apply(
                        lambda x: f"{int(safe_numeric(x)):,}" if pd.notna(x) and safe_numeric(x) != 0 else ("0" if pd.notna(x) else "N/A")
                    )
            for column in [
                'Current Outsourced Ratio',
                'Tenure Threshold (Years)',
                'Avg Cost Saudi Inhouse',
                'Avg Cost Non-Saudi Inhouse',
                'Avg Cost Saudi Tenured Inhouse',
                'Avg Cost Non-Saudi Tenured Inhouse',
                'Effective Avg Cost Saudi Inhouse',
                'Effective Avg Cost Non-Saudi Inhouse',
                'Avg Cost Outsourced',
                'Fully Loaded Cost per In-house Employee',
                'Fully Loaded Cost per In-house Non-Saudi Employee',
                'Fully Loaded Cost per In-house Saudi Employee',
                'Negotiated cost per outsourced FTE',
            ]:
                if column in debug_display_df.columns:
                    if 'Ratio' in column and column != 'Current Ratio':
                        debug_display_df[column] = debug_display_df[column].apply(lambda x: f"{safe_numeric(x):.1%}" if pd.notna(x) else "N/A")
                    elif column == 'Tenure Threshold (Years)':
                        debug_display_df[column] = debug_display_df[column].apply(lambda x: f"{safe_numeric(x):.1f}" if pd.notna(x) else "N/A")
                    else:
                        debug_display_df[column] = debug_display_df[column].apply(lambda x: f"{safe_numeric(x):,.0f}" if pd.notna(x) else "N/A")
            debug_display_df = debug_display_df.rename(
                columns={
                    'Avg Cost Outsourced': 'Fully loaded cost per outsourced FTE',
                    'Fully Loaded Cost per In-house Employee': 'Fully loaded cost per in-house employees',
                    'Fully Loaded Cost per In-house Non-Saudi Employee': 'Fully loaded cost per in-house non-saudi employee',
                    'Fully Loaded Cost per In-house Saudi Employee': 'Fully loaded cost per in-house Saudi employees',
                }
            )
            st.dataframe(debug_display_df, use_container_width=True)

        # ===== DISPLAY RESULTS =====
        if hasattr(st.session_state, 'optimization_status'):
            st.markdown("---")
            render_section_title("Optimization Results")
        
            # ----- KPI METRICS -----
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("💰 Total Cost (SAR / Month)", f"SAR {st.session_state.total_cost:,.0f}")
            with col2:
                st.metric("👥 Total Employees Headcount", f"{st.session_state.total_employees_final:,}")
            with col3:
                st.metric("🤝 Total Outsourced Labor", f"{st.session_state.total_outsourced_final:,}")
        
            col4, col5, col6 = st.columns(3)
            with col4:
                st.metric("🇸🇦 Saudi Labor", f"{st.session_state.total_saudi_final:,}")
            with col5:
                st.metric("🌍 In-House Non-Saudi Labor", f"{st.session_state.total_non_saudi_final:,}")
            with col6:
                st.metric("📊 Saudization Rate", f"{st.session_state.saudization_achieved:.1f}%")
    
            st.markdown("---")
    
            # ----- COST ANALYSIS -----
            render_section_title("Cost Analysis")
    
            viz_col1, viz_col2 = st.columns(2)
    
            COLORS_METHOD = ['#7BCFA4', '#7E9EBC', '#D7EDE1']
            COLORS_FAMILY = [
                '#7BCFA4', '#9CDEBA', '#CFEFDE', '#7E9EBC', '#A7BDD3',
                '#D7EDE1', '#DCE5EE', '#BFD7C9', '#C8CED4', '#B6E5CB', '#E5EAEE'
            ]
    
            # Pie 1: Cost by sourcing method
            with viz_col1:
                total_all = (st.session_state.total_cost_saudi +
                             st.session_state.total_cost_non_saudi +
                             st.session_state.total_cost_outsourced)
    
                labels_m = ['Saudi Labor', 'In-House Non-Saudi Labor', 'Outsourced Labor']
                values_m = [
                    st.session_state.total_cost_saudi,
                    st.session_state.total_cost_non_saudi,
                    st.session_state.total_cost_outsourced
                ]
    
                fig_method = go.Figure(data=[go.Pie(
                    labels=labels_m,
                    values=values_m,
                    marker=dict(colors=COLORS_METHOD, line=dict(color='#ffffff', width=2)),
                    hovertemplate='<b>%{label}</b><br>SAR %{value:,.0f}<br>%{percent}<extra></extra>',
                    textinfo='percent',
                    textposition='auto',
                    hole=0.45
                )])
                fig_method.update_layout(
                    title=dict(text='Cost by sourcing method', font=dict(size=14, color='#1a1f1d'), x=0.5, xanchor='center'),
                    height=300,
                    margin=dict(t=40, b=20, l=20, r=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    legend=dict(
                        orientation='v',
                        x=1.02, y=0.5,
                        xanchor='left', yanchor='middle',
                        font=dict(size=12, color='#44504a'),
                        bgcolor='rgba(0,0,0,0)'
                    ),
                    annotations=[dict(
                        text=f"SAR<br>{total_all/1e6:.1f}M" if total_all >= 1e6 else f"SAR<br>{total_all:,.0f}",
                        x=0.5, y=0.5, font_size=13, showarrow=False,
                        font=dict(color='#1a1f1d', family='Georgia')
                    )]
                )
                st.plotly_chart(fig_method, use_container_width=True)
    
            # Pie 2: Cost by Job Family - top 10 + Other
            with viz_col2:
                results_sorted = st.session_state.results_df.copy()
                results_sorted = results_sorted.sort_values('Total Cost (SAR)', ascending=False).reset_index(drop=True)
    
                top10 = results_sorted.head(10)
                other_rows = results_sorted.iloc[10:]
                other_cost = other_rows['Total Cost (SAR)'].sum()
                other_count = len(other_rows)
    
                job_families = list(top10['Job Family'])
                costs = list(top10['Total Cost (SAR)'])
    
                if other_cost > 0:
                    job_families.append(f"Other ({other_count} families)")
                    costs.append(other_cost)

                total_family_cost = sum(costs)
    
                fig_family = go.Figure(data=[go.Pie(
                    labels=job_families,
                    values=costs,
                    marker=dict(colors=COLORS_FAMILY[:len(job_families)], line=dict(color='#ffffff', width=2)),
                    hovertemplate='<b>%{label}</b><br>SAR %{value:,.0f}<br>%{percent}<extra></extra>',
                    textinfo='percent', 
                    textposition='auto',
                    hole=0.45
                )])
                fig_family.update_layout(
                    title=dict(text='Cost by job family (top 10)', font=dict(size=14, color='#1a1f1d'), x=0.5, xanchor='center'),
                    height=300,
                    margin=dict(t=40, b=20, l=20, r=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    legend=dict(
                        orientation='v',
                        x=1.02, y=0.5,
                        xanchor='left', yanchor='middle',
                        font=dict(size=11, color='#44504a'),
                        bgcolor='rgba(0,0,0,0)'
                    ),
                    annotations=[dict(
                        text=f"SAR<br>{total_family_cost/1e6:.1f}M" if total_family_cost >= 1e6 else f"SAR<br>{total_family_cost:,.0f}",
                        x=0.5, y=0.5, font_size=13, showarrow=False,
                        font=dict(color='#1a1f1d', family='Georgia')
                    )]
                )
                st.plotly_chart(fig_family, use_container_width=True)
    
            st.markdown("---")
    
            # ----- DETAILED TABLE -----
            render_section_title("Detailed Allocation by Job Family")
            st.markdown("<p style='color:#888;font-size:13px;margin-top:-10px;margin-bottom:12px;'>Click each row to expand the cost breakdown</p>", unsafe_allow_html=True)
    
            for idx, row in st.session_state.results_df.iterrows():
                with st.expander(f"**{row['Job Family']}** - SAR {row['Total Cost (SAR)']:,.0f}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Saudi Labor", f"{int(row['Saudi Labor']):,}")
                    c2.metric("In-House Non-Saudi Labor", f"{int(row['In-House Non-Saudi Labor']):,}")
                    c3.metric("Outsourced Labor", f"{int(row['Outsourced Labor']):,}")
                    c4.metric("Total Headcount", f"{int(row['Total Employees Headcount']):,}")
    
                    fig_bk = go.Figure(data=[go.Bar(
                        x=['Saudi Labor', 'In-House Non-Saudi Labor', 'Outsourced Labor'],
                        y=[float(row['Cost - Saudi Labor (SAR)']),
                           float(row['Cost - In-House Non-Saudi Labor (SAR)']),
                           float(row['Cost - Outsourced Labor (SAR)'])],
                        marker_color=['#7BCFA4', '#7E9EBC', '#D7EDE1'],
                        hovertemplate='%{x}<br>SAR %{y:,.0f}<extra></extra>'
                    )])
                    fig_bk.update_layout(
                        height=220,
                        margin=dict(t=10, b=10, l=10, r=10),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        yaxis=dict(title=dict(text='Cost (SAR)', font=dict(color='#f4f7f5')), gridcolor='rgba(123, 207, 164, 0.16)', tickfont=dict(size=11, color='#44504a')),
                        xaxis=dict(gridcolor='rgba(0,0,0,0)', tickfont=dict(color='#44504a')),
                        showlegend=False
                    )
                    st.plotly_chart(fig_bk, use_container_width=True, key=f"breakdown_chart_{idx}")
    
            st.markdown("---")
    
            # ----- DOWNLOAD -----
            render_section_title("Download Results")
    
            output_buffer = io.BytesIO()
            with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                st.session_state.results_df.to_excel(writer, sheet_name='Optimization Results', index=False)
                if 'processing_debug_df' in st.session_state:
                    st.session_state.processing_debug_df.to_excel(writer, sheet_name='Model Processing', index=False)
    
                summary_data = {
                    'Metric': ['Total Cost (SAR / Month)', 'Total Employees Headcount', 'Saudi Labor',
                               'In-House Non-Saudi Labor', 'Outsourced Labor', 'Saudization Rate Achieved (%)',
                               'Optimization Status', 'Outsourced Cost Type',
                               'Can Reduce Saudi', 'Saudization Enforced',
                               'Risk Factor', 'Tenure Constraint Active', 'Tenure Threshold (Years)'],
                    'Value': [f'{st.session_state.total_cost:,.0f}',
                              st.session_state.total_employees_final,
                              st.session_state.total_saudi_final,
                              st.session_state.total_non_saudi_final,
                              st.session_state.total_outsourced_final,
                              f'{st.session_state.saudization_achieved:.2f}',
                              st.session_state.optimization_status,
                              st.session_state.outsource_type,
                              'Yes' if can_fire_saudi else 'No',
                              'Yes' if enforce_saudization else 'No',
                              f'{risk_factor:.2f}',
                              'Yes' if tenure_constraint_active else 'No',
                              f'{tenure_threshold_years:.1f}' if protect_tenured_inhouse else 'N/A']
                }
                if enforce_saudization:
                    summary_data['Metric'].insert(6, 'Saudization Rate Required (%)')
                    summary_data['Value'].insert(6, f'{SAUDIZATION_RATE*100:.2f}')
    
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
    
            output_buffer.seek(0)
            st.download_button(
                label="📊 Download Results as Excel",
                data=output_buffer.getvalue(),
                file_name="Manpower_Optimization_Results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

