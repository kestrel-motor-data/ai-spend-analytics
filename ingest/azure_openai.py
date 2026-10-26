"""Azure OpenAI usage export: one CSV per day, per API key and deployment.

Version 2 of the export starts with usage for 2027-04-09 (the last version 1
day is 2027-04-08). Version 2 moves the file under a v2/ subfolder, changes
the usage day to UTC, and renames several columns; see docs/runbook.md
"Vendor source changes" and stg_azure_openai_usage.sql for the mapping.
replace_day's delete key must match the date column actually present in a
given day's file, so we pass usage_date for version 1 days and
usage_date_utc for version 2 days.
"""

import datetime as dt

from ingest.common import read_landed_csv, replace_day

V2_START = dt.date(2027, 4, 9)


def load(day: dt.date) -> None:
    if day >= V2_START:
        rows = read_landed_csv(f"azure_openai/v2/usage_{day.isoformat()}.csv")
        replace_day("azure_openai_usage", "usage_date_utc", day, rows)
    else:
        rows = read_landed_csv(f"azure_openai/usage_{day.isoformat()}.csv")
        replace_day("azure_openai_usage", "usage_date", day, rows)
