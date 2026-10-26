"""Azure OpenAI usage export: one CSV per day, per API key and deployment.

The vendor's export moves to a v2 format starting with usage for 2027-04-09
(DATA14D-114): a new path (`v2/` subfolder) and a renamed set of columns.
`ensure_columns` (below) already made sure the v2 columns exist on
`raw.azure_openai_usage` as nullable columns ahead of the cutover, so this
only needs to pick the right landing path and the right column to key the
per-day delete in `replace_day` on, since v2 rows don't carry `usage_date`
at all.
"""

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

# Last day of the v1 export. v2 starts the next day; there is no overlap.
V2_CUTOVER = dt.date(2027, 4, 9)


def load(day: dt.date) -> None:
    ensure_columns("azure_openai_usage", V2_COLUMNS)
    if day >= V2_CUTOVER:
        path = f"azure_openai/v2/usage_{day.isoformat()}.csv"
        date_column = "usage_date_utc"
    else:
        path = f"azure_openai/usage_{day.isoformat()}.csv"
        date_column = "usage_date"
    rows = read_landed_csv(path)
    replace_day("azure_openai_usage", date_column, day, rows)
