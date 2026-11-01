from __future__ import annotations

import re
from typing import Any

import pandas as pd


NUMERIC_OPS = {"sum", "mean", "count", "min", "max"}
ALLOWED_KEYS = {"operation", "metric", "group_by", "filters", "top_n", "date_column", "date_period"}


def build_kpi_summary(df: pd.DataFrame) -> dict[str, str]:
    numeric = df.select_dtypes(include="number").columns.tolist()
    result: dict[str, str] = {
        "Rows": f"{len(df):,}",
        "Columns": f"{len(df.columns):,}",
        "Missing cells": f"{int(df.isna().sum().sum()):,}",
    }
    revenue_col = next((c for c in df.columns if c.lower() in {"revenue", "sales", "amount", "total_sales"}), None)
    if revenue_col and pd.api.types.is_numeric_dtype(df[revenue_col]):
        result["Total " + revenue_col.title()] = f"{df[revenue_col].sum(min_count=1):,.2f}"
    else:
        result["Numeric columns"] = f"{len(numeric):,}"
    return result


def build_data_quality_report(df: pd.DataFrame) -> dict[str, Any]:
    by_column = pd.DataFrame({
        "column": df.columns,
        "data_type": [str(df[c].dtype) for c in df.columns],
        "missing_values": [int(df[c].isna().sum()) for c in df.columns],
        "missing_percent": [round(float(df[c].isna().mean() * 100), 2) for c in df.columns],
        "unique_values": [int(df[c].nunique(dropna=True)) for c in df.columns],
    })
    return {
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_cells": int(df.isna().sum().sum()),
        "columns_with_missing": int((df.isna().sum() > 0).sum()),
        "by_column": by_column,
    }


def rule_based_plan(question: str, df: pd.DataFrame) -> dict[str, Any]:
    """Conservative fallback parser; supports simple aggregations and groupings."""
    q = question.lower()
    cols = list(df.columns)
    def match_column(words: list[str]) -> str | None:
        for word in words:
            for col in cols:
                if col.lower() == word or col.lower().replace("_", " ") == word:
                    return col
        return None

    date_col = next((c for c in cols if any(k in c.lower() for k in ("date", "time")) and
                     pd.api.types.is_datetime64_any_dtype(df[c])), None)
    metric = match_column(["revenue", "sales", "profit", "quantity", "cost", "amount"])
    group_by = None
    if "product" in q or "item" in q:
        group_by = match_column(["product", "item", "product name"])
    elif "region" in q or "area" in q:
        group_by = match_column(["region", "area", "territory"])
    elif "category" in q:
        group_by = match_column(["category", "product category"])
    elif "month" in q or "monthly" in q:
        group_by = date_col
    elif "status" in q or "cancel" in q:
        group_by = match_column(["status", "order status"])
    elif "customer" in q:
        group_by = match_column(["customer", "customer name", "customer_id"])

    if any(w in q for w in ("how many", "count", "number of orders", "number of records")):
        operation = "count"
        if metric is None:
            metric = cols[0]
    elif any(w in q for w in ("average", "avg", "mean")):
        operation = "mean"
    elif any(w in q for w in ("lowest", "least", "minimum", "min ")):
        operation = "min"
    elif any(w in q for w in ("highest", "most", "top", "maximum", "max ")):
        operation = "max" if "maximum" in q or "max " in q else "sum"
    else:
        operation = "sum"

    if metric is None:
        numeric = df.select_dtypes(include="number").columns.tolist()
        metric = numeric[0] if numeric else None
    if metric is None:
        return {"operation": "count", "metric": cols[0], "group_by": group_by, "filters": [], "top_n": 10}
    if group_by == date_col and date_col is not None:
        operation = "sum"
    return {
        "operation": operation,
        "metric": metric,
        "group_by": group_by,
        "filters": [],
        "top_n": 10,
        "date_column": date_col if ("month" in q or "monthly" in q) else None,
        "date_period": "month" if ("month" in q or "monthly" in q) else None,
    }


def validate_analysis_plan(plan: dict[str, Any], df: pd.DataFrame) -> tuple[dict[str, Any], str | None]:
    if not isinstance(plan, dict):
        return {}, "The question could not be translated into a supported analysis."
    if set(plan.keys()) - ALLOWED_KEYS:
        return {}, "The analysis plan contains unsupported instructions."
    operation = plan.get("operation")
    metric = plan.get("metric")
    group_by = plan.get("group_by")
    if operation not in NUMERIC_OPS:
        return {}, f"Unsupported operation: {operation!r}."
    if metric not in df.columns:
        return {}, f"Metric column {metric!r} was not found in the uploaded data."
    if operation != "count" and not pd.api.types.is_numeric_dtype(df[metric]):
        return {}, f"The selected metric '{metric}' is not numeric, so {operation} cannot be calculated."
    if group_by is not None and group_by not in df.columns:
        return {}, f"Group-by column {group_by!r} was not found in the uploaded data."
    if group_by is not None and df[group_by].nunique(dropna=True) > 500:
        return {}, "This grouping has too many unique values. Choose a lower-cardinality column."
    top_n = plan.get("top_n", 10)
    if not isinstance(top_n, int) or top_n < 1 or top_n > 50:
        return {}, "top_n must be an integer between 1 and 50."
    if plan.get("filters") not in (None, []):
        return {}, "Filters are not enabled in this version; ask a question without filters."
    date_column = plan.get("date_column")
    if date_column is not None and date_column not in df.columns:
        return {}, "The requested date column does not exist."
    if plan.get("date_period") not in (None, "month"):
        return {}, "Only monthly date grouping is supported."
    return {
        "operation": operation,
        "metric": metric,
        "group_by": group_by,
        "filters": [],
        "top_n": top_n,
        "date_column": date_column,
        "date_period": plan.get("date_period"),
    }, None


def execute_analysis_plan(df: pd.DataFrame, plan: dict[str, Any]) -> dict[str, Any]:
    metric = plan["metric"]
    operation = plan["operation"]
    group_by = plan.get("group_by")
    work = df.copy()
    date_col = plan.get("date_column")
    if date_col and plan.get("date_period") == "month":
        work["_insightguard_month"] = pd.to_datetime(work[date_col], errors="coerce").dt.to_period("M").astype(str)
        group_by = "_insightguard_month"

    if operation == "count":
        if group_by:
            table = work.groupby(group_by, dropna=False).size().reset_index(name="record_count")
            value_col = "record_count"
        else:
            table = pd.DataFrame({"metric": ["Record count"], "value": [len(work)]})
            value_col = "value"
    elif group_by:
        grouped = work.groupby(group_by, dropna=False)[metric]
        if operation == "sum":
            table = grouped.sum(min_count=1).reset_index()
        elif operation == "mean":
            table = grouped.mean().reset_index()
        elif operation == "min":
            table = grouped.min().reset_index()
        elif operation == "max":
            table = grouped.max().reset_index()
        value_col = metric
    else:
        series = work[metric]
        if operation == "sum":
            value = series.sum(min_count=1)
        elif operation == "mean":
            value = series.mean()
        elif operation == "min":
            value = series.min()
        else:
            value = series.max()
        table = pd.DataFrame({"metric": [metric], "value": [value]})
        value_col = "value"

    table = table.sort_values(value_col, ascending=False, na_position="last").head(plan.get("top_n", 10)).reset_index(drop=True)
    if group_by and group_by in table.columns and len(table):
        winner = table.iloc[0]
        answer = f"Highest {operation} of {metric} is for {winner[group_by]}: {winner[value_col]:,.2f}." if pd.notna(winner[value_col]) else "The top group has no valid numeric values."
    elif len(table):
        value = table.iloc[0][value_col]
        answer = f"{operation.title()} of {metric}: {value:,.2f}." if pd.notna(value) else f"No valid values were available for {metric}."
    else:
        answer = "No result was produced for this question."
    verification = (
        f"Calculated locally with pandas from {len(df):,} source rows. "
        f"Operation={operation}; metric={metric}; grouping={group_by or 'none'}. "
        f"Missing values are handled using pandas aggregation defaults; source data was not modified."
    )
    if "_insightguard_month" in table.columns:
        table = table.rename(columns={"_insightguard_month": "month"})
    return {"answer": answer, "table": table, "verification": verification}


def analyze_question(question: str, df: pd.DataFrame) -> dict[str, Any]:
    plan, error = validate_analysis_plan(rule_based_plan(question, df), df)
    if error:
        return {"error": error}
    return execute_analysis_plan(df, plan)
