# InsightGuard AI — Data Analysis Copilot

InsightGuard AI is a small business-analytics app that lets a user upload CSV or Excel data, inspect data quality, ask simple questions in natural language, and view data-backed results and charts.

**Core principle:** the language model may interpret the question, but pandas performs the calculation. The app validates the plan against the actual dataset and does not execute model-generated code or SQL.

## Features

- Upload CSV, XLSX, and XLS files
- Synthetic sales dataset for a quick demo
- KPI summary, data preview, and basic visual exploration
- Data quality report for missing values, duplicate rows, and per-column completeness
- Question-to-analysis plan using Gemini when configured, with a local rule-based fallback
- Whitelisted aggregation operations (`sum`, `mean`, `count`, `min`, `max`)
- Group-by analysis and monthly grouping for supported date columns
- Result tables, charts, CSV exports, and an explanation of how results were calculated
- Automated tests for core data and validation behavior

## Technology

Python, Streamlit, pandas, NumPy, Plotly, Gemini API (optional), pytest.

## Run locally

Python 3.10+ is recommended.

```bash
python -m venv .venv
```

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

macOS/Linux:
```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit. The app works with sample data without an API key.

## Enable Gemini (optional)

1. Create an API key using Google's official AI developer platform, subject to its current access and usage limits.
2. Set an environment variable named `GEMINI_API_KEY` before launching Streamlit.

Windows PowerShell:
```powershell
$env:GEMINI_API_KEY="YOUR_KEY"
streamlit run app.py
```

macOS/Linux:
```bash
export GEMINI_API_KEY="YOUR_KEY"
streamlit run app.py
```

For Streamlit Community Cloud, add `GEMINI_API_KEY` under **App settings → Secrets**. Do not put a real API key in source code or commit it to GitHub.

If Gemini is unavailable or not configured, the app falls back to a limited local rule-based parser. Not every free-form question is supported in fallback mode.

## Run tests

```bash
pytest -q
```

## Try these questions

Using the included sample sales data:
- Which product generated the highest profit?
- Which region has the highest sales?
- What is the total revenue?
- Which category has the highest profit?
- Show monthly revenue trends

Question interpretation is deliberately constrained. Unsupported filters or unknown columns should be rejected instead of silently guessed.

## Deployment to Streamlit Community Cloud

1. Push this project to a GitHub repository.
2. Sign in to Streamlit Community Cloud and create an app from that repository.
3. Select `app.py` as the main file.
4. Deploy. Add `GEMINI_API_KEY` in the app's Secrets only if you want the Gemini integration.
5. Test the deployed app with the sample data and a small CSV before sharing the link.

## GitHub upload

```bash
git init
git add .
git commit -m "Build InsightGuard AI data analysis copilot"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

If you already created a repository and cloned it, run the add/commit/push commands from that repository instead of running `git init` again.

## Limitations and safety

- This is a portfolio project, not a production-grade data governance platform.
- Uploaded files are processed in the running app; do not upload confidential or sensitive data to a public demo.
- Numeric results are calculated locally, but interpretation still depends on the chosen plan. Review the plan and source columns.
- The rule-based fallback only understands a small range of common question patterns.
- Current analysis supports simple aggregations and groupings; arbitrary SQL, arbitrary Python execution, complex filters, causal explanations, and unrestricted multi-step reasoning are intentionally not supported.
- Missing values are not silently imputed. Aggregation behavior follows pandas defaults and is described in the verification note.
- The demo data is synthetic and must not be described as real business data.

## Suggested next improvements

- Add a larger test suite for ambiguous questions and mixed data types
- Add explicit filters with validation and a preview of matched rows
- Add configurable date ranges and clearer treatment of missing metrics
- Add authentication and privacy controls before handling sensitive datasets
- Add a user-facing record of the question, validated plan, and calculation result
