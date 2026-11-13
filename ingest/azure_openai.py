"""Azure OpenAI usage export: one CSV per day, per API key and deployment."""

import datetime as dt

from ingest.common import read_landed_csv, replace_day


def load(day: dt.date) -> None:
    rows = read_landed_csv(f"azure_openai/usage_{day.isoformat()}.csv")
    replace_day("azure_openai_usage", "usage_date", day, rows)
