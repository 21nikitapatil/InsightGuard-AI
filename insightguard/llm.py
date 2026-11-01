from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd

from insightguard.analytics import rule_based_plan


def gemini_is_configured() -> bool:
    try:
        import streamlit as st
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        secret_key = ""
    return bool(os.getenv("GEMINI_API_KEY") or secret_key)


def _get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        import streamlit as st
        return str(st.secrets.get("GEMINI_API_KEY", ""))
    except Exception:
        return ""


def create_analysis_plan(question: str, df: pd.DataFrame) -> dict[str, Any]:
    """Ask Gemini for a constrained JSON plan; fall back to a local parser if unavailable."""
    key = _get_api_key()
    if not key:
        return rule_based_plan(question, df)

    columns = []
    for col in df.columns:
        columns.append({
            "name": str(col),
            "dtype": str(df[col].dtype),
            "sample_values": [str(v) for v in df[col].dropna().head(3).tolist()],
        })
    prompt = f"""
You convert a user question into a safe data-analysis plan.
Return only valid JSON with exactly these keys:
operation, metric, group_by, filters, top_n, date_column, date_period.
operation must be one of sum, mean, count, min, max.
metric and group_by must be exact column names from the schema.
group_by may be null. filters must always be [].
top_n must be an integer from 1 to 50.
date_period must be null or month. For monthly trend questions, set date_column to a date column and date_period to month.
Never output code, SQL, or instructions to execute. Do not invent columns.
Question: {question}
Schema: {json.dumps(columns)}
"""
    try:
        from google import genai
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": 0},
        )
        plan = json.loads(response.text)
        if isinstance(plan, dict):
            return plan
    except Exception:
        # The UI will still work if the API is unavailable; this fallback is visible in the generated plan.
        pass
    return rule_based_plan(question, df)
