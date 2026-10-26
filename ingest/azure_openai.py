"""Azure OpenAI usage export: one CSV per day, per API key and deployment."""

import datetime as dt

from google.cloud import bigquery

from ingest.common import ensure_columns, read_landed_csv, replace_day

# Columns the vendor's usage export v2 introduces, landing from 2027-04-09
# (DATA14D v2 cutover). Added as nullable ahead of the cutover so the first
# v2 file lands on a raw table that already has them, instead of a hard
# BigQuery schema error the first time a stg model references one. See
# ensure_columns in ingest/common.py and the ticket for the rest of the v2
# work (reading the new path, mapping the renamed columns in staging).
V2_COLUMNS = [
    bigquery.SchemaField("usage_date_utc", "DATE"),
    bigquery.SchemaField("key_id", "STRING"),
    bigquery.SchemaField("deployment_name", "STRING"),
    bigquery.SchemaField("model", "STRING"),
    bigquery.SchemaField("prompt_tokens", "INT64"),
    bigquery.SchemaField("cached_prompt_tokens", "INT64"),
    bigquery.SchemaField("completion_tokens", "INT64"),
    bigquery.SchemaField("billed_amount", "NUMERIC"),
    bigquery.SchemaField("billing_currency", "STRING"),
]


def load(day: dt.date) -> None:
    ensure_columns("azure_openai_usage", V2_COLUMNS)
    rows = read_landed_csv(f"azure_openai/usage_{day.isoformat()}.csv")
    replace_day("azure_openai_usage", "usage_date", day, rows)
