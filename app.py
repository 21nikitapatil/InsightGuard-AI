from __future__ import annotations

import io
import os
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from insightguard.analytics import (
    analyze_question,
    build_data_quality_report,
    build_kpi_summary,
    execute_analysis_plan,
    validate_analysis_plan,
)
from insightguard.data import load_uploaded_data, make_demo_data
from insightguard.llm import create_analysis_plan, gemini_is_configured

st.set_page_config(page_title="InsightGuard AI", page_icon="🛡️", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.8rem; padding-bottom: 2.5rem;}
    .hero {padding: 1.3rem 1.5rem; border: 1px solid rgba(120,120,120,.25);
           border-radius: 16px; margin-bottom: 1rem;}
    .muted {opacity: .75;}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("🛡️ InsightGuard AI")
    st.caption("Data-backed answers. Verifiable calculations.")
    st.divider()
    st.subheader("Load data")
    upload = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx", "xls"])
    use_demo = st.button("Load sample sales data", use_container_width=True)
    st.caption("Demo data is synthetic and contains no personal information.")
    st.divider()
    st.subheader("AI configuration")
    st.write("Gemini:", "Configured" if gemini_is_configured() else "Not configured")
    st.caption("Add GEMINI_API_KEY to your environment or Streamlit secrets to enable AI question interpretation.")
    st.caption("Without an API key, a limited rule-based question parser remains available.")

if "data" not in st.session_state:
    st.session_state.data = make_demo_data()
    st.session_state.data_name = "Sample sales dataset"
if use_demo:
    st.session_state.data = make_demo_data()
    st.session_state.data_name = "Sample sales dataset"
if upload is not None:
    try:
        st.session_state.data = load_uploaded_data(upload, upload.name)
        st.session_state.data_name = upload.name
        st.sidebar.success(f"Loaded {len(st.session_state.data):,} rows")
    except Exception as exc:
        st.sidebar.error(f"Could not read file: {exc}")

df: pd.DataFrame = st.session_state.data.copy()

st.markdown(
    """
    <div class="hero">
      <h1>InsightGuard AI</h1>
      <p>Ask business questions about your data, explore trends, and verify every reported metric against deterministic calculations.</p>
      <p class="muted">AI interprets your question; Python performs the calculation. AI output is never treated as a trusted numerical source.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(f"Current dataset: **{st.session_state.data_name}** · {len(df):,} rows · {len(df.columns)} columns")

kpis = build_kpi_summary(df)
cols = st.columns(4)
for col, (label, value) in zip(cols, kpis.items()):
    col.metric(label, value)

tab_ask, tab_explore, tab_quality, tab_data = st.tabs(
    ["💬 Ask your data", "📊 Explore", "🧹 Data quality", "🗂️ Data preview"]
)

with tab_ask:
    st.subheader("Ask a business question")
    examples = [
        "Which product generated the highest profit?",
        "Show monthly revenue trends",
        "Which region has the highest sales?",
        "What is the total revenue?",
        "Which category has the highest profit?",
    ]
    selected_example = st.selectbox("Try an example", ["Write my own question"] + examples)
    question = st.text_input(
        "Your question",
        value="" if selected_example == "Write my own question" else selected_example,
        placeholder="e.g. Which region has the highest revenue?",
    )
    if st.button("Analyze question", type="primary", disabled=not question.strip()):
        with st.spinner("Interpreting question and checking the data..."):
            plan = create_analysis_plan(question, df)
            plan, plan_error = validate_analysis_plan(plan, df)
            if plan_error:
                st.error(plan_error)
            else:
                result = execute_analysis_plan(df, plan)
                st.session_state.last_result = {
                    "question": question,
                    "plan": plan,
                    "result": result,
                }

    last = st.session_state.get("last_result")
    if last:
        st.divider()
        st.markdown(f"**Question:** {last['question']}")
        result = last["result"]
        st.markdown(f"**Answer:** {result['answer']}")
        st.info("Verification: the displayed answer and metrics were calculated from the loaded dataset by the application, not copied from an AI-generated number.")
        with st.expander("How the answer was calculated"):
            st.json(last["plan"])
            st.write(result["verification"])
        if result.get("table") is not None and not result["table"].empty:
            st.dataframe(result["table"], use_container_width=True, hide_index=True)
            if result["table"].shape[1] >= 2:
                numeric_cols = result["table"].select_dtypes(include="number").columns.tolist()
                non_numeric_cols = [c for c in result["table"].columns if c not in numeric_cols]
                if numeric_cols and non_numeric_cols:
                    chart_col = st.selectbox("Chart metric", numeric_cols, key="chart_metric")
                    group_col = st.selectbox("Chart category", non_numeric_cols, key="chart_category")
                    chart = px.bar(result["table"], x=group_col, y=chart_col, title=f"{chart_col} by {group_col}")
                    st.plotly_chart(chart, use_container_width=True)
        st.download_button(
            "Download analysis result as CSV",
            data=result["table"].to_csv(index=False).encode("utf-8") if result.get("table") is not None else b"",
            file_name="insightguard_analysis.csv",
            mime="text/csv",
        )

with tab_explore:
    st.subheader("Explore your dataset")
    all_columns = df.columns.tolist()
    default_cols = all_columns[: min(8, len(all_columns))]
    chosen_cols = st.multiselect("Columns to summarize", all_columns, default=default_cols)
    if chosen_cols:
        st.dataframe(df[chosen_cols].describe(include="all").transpose().reset_index(names="column"), use_container_width=True)
    date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        metric = st.selectbox("Numeric column to visualize", numeric_cols, key="explore_metric")
        category_options = [c for c in df.columns if c != metric and df[c].nunique(dropna=True) <= 30]
        if category_options:
            category = st.selectbox("Group by", category_options, key="explore_category")
            agg = df.groupby(category, dropna=False)[metric].sum(min_count=1).reset_index().sort_values(metric, ascending=False)
            st.plotly_chart(px.bar(agg, x=category, y=metric, title=f"{metric} by {category}"), use_container_width=True)
        else:
            st.line_chart(df[metric].reset_index(drop=True))

with tab_quality:
    st.subheader("Data quality report")
    report = build_data_quality_report(df)
    quality_cols = st.columns(3)
    quality_cols[0].metric("Duplicate rows", f"{report['duplicate_rows']:,}")
    quality_cols[1].metric("Missing cells", f"{report['missing_cells']:,}")
    quality_cols[2].metric("Columns with missing data", f"{report['columns_with_missing']:,}")
    st.dataframe(report["by_column"], use_container_width=True, hide_index=True)
    st.caption("InsightGuard reports quality issues without silently changing your source data.")
    st.download_button(
        "Download data quality report",
        data=report["by_column"].to_csv(index=False).encode("utf-8"),
        file_name="data_quality_report.csv",
        mime="text/csv",
    )

with tab_data:
    st.subheader("Data preview")
    st.dataframe(df.head(500), use_container_width=True, hide_index=True)
    st.caption("For performance, the preview is limited to the first 500 rows.")
