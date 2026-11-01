from __future__ import annotations

from typing import BinaryIO

import numpy as np
import pandas as pd


def make_demo_data(rows: int = 240) -> pd.DataFrame:
    """Create reproducible synthetic sales data for demos and tests."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2025-01-01", periods=180, freq="D")
    products = ["Desk Lamp", "Office Chair", "Notebook", "Monitor Stand", "Keyboard"]
    regions = ["North", "South", "East", "West"]
    categories = {
        "Desk Lamp": "Lighting",
        "Office Chair": "Furniture",
        "Notebook": "Stationery",
        "Monitor Stand": "Furniture",
        "Keyboard": "Electronics",
    }
    unit_price = {"Desk Lamp": 35.0, "Office Chair": 180.0, "Notebook": 4.0,
                  "Monitor Stand": 42.0, "Keyboard": 55.0}
    product = rng.choice(products, size=rows)
    quantity = rng.integers(1, 9, size=rows)
    price = np.array([unit_price[p] for p in product])
    revenue = quantity * price
    cost = revenue * rng.uniform(0.42, 0.78, size=rows)
    frame = pd.DataFrame({
        "order_id": [f"ORD-{i:04d}" for i in range(1, rows + 1)],
        "order_date": rng.choice(dates, size=rows),
        "region": rng.choice(regions, size=rows),
        "product": product,
        "category": [categories[p] for p in product],
        "quantity": quantity,
        "revenue": np.round(revenue, 2),
        "cost": np.round(cost, 2),
        "profit": np.round(revenue - cost, 2),
        "status": rng.choice(["Completed", "Completed", "Completed", "Cancelled"], size=rows),
    })
    frame["order_date"] = pd.to_datetime(frame["order_date"])
    # Add realistic data-quality cases for the quality-report demonstration.
    if rows > 20:
        frame.loc[3, "region"] = np.nan
        frame.loc[7, "profit"] = np.nan
    return frame.sort_values("order_date").reset_index(drop=True)


def load_uploaded_data(file_obj: BinaryIO, filename: str) -> pd.DataFrame:
    """Load CSV/XLS/XLSX and apply conservative type inference."""
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix == "csv":
        df = pd.read_csv(file_obj)
    elif suffix in {"xlsx", "xls"}:
        df = pd.read_excel(file_obj)
    else:
        raise ValueError("Please upload a CSV or Excel file.")
    if df.empty:
        raise ValueError("The uploaded file contains no rows.")
    if len(df.columns) > 100:
        raise ValueError("The file has more than 100 columns; please simplify it first.")
    df.columns = [str(c).strip() for c in df.columns]
    if any(not c for c in df.columns):
        raise ValueError("Column names must not be blank.")
    if len(set(df.columns)) != len(df.columns):
        raise ValueError("Column names must be unique after trimming whitespace.")
    for col in df.columns:
        if df[col].dtype == object:
            # Parse only columns whose names suggest a date to avoid corrupting identifiers.
            if any(token in col.lower() for token in ("date", "time", "timestamp")):
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().mean() >= 0.7:
                    df[col] = parsed
    return df
