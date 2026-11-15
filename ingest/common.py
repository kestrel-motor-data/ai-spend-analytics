"""Shared load logic for every source.

A load replaces whole days in a raw table: it deletes the day, then appends
the landed file's rows under a new load id. Re-running a day therefore never
duplicates it. Columns the file adds are added to the raw table rather than
dropped, so a vendor renaming a column shows up as a new column, and the
cleaned models decide what to do with it.
"""

import csv
import datetime as dt
import io
import os
import uuid

import time

from google.api_core.exceptions import Forbidden, NotFound, TooManyRequests
from google.cloud import bigquery, storage

PROJECT = os.environ["GCP_PROJECT"]
BUCKET = os.environ["LANDING_BUCKET"]

TYPES = {"INTEGER": int, "INT64": int, "FLOAT": float, "FLOAT64": float}


def days(start: dt.date, end: dt.date):
    while start <= end:
        yield start
        start += dt.timedelta(days=1)


def read_landed_csv(path: str) -> list[dict]:
    blob = storage.Client(project=PROJECT).bucket(BUCKET).blob(path)
    if not blob.exists():
        raise FileNotFoundError(f"gs://{BUCKET}/{path} has not landed")
    return list(csv.DictReader(io.StringIO(blob.download_as_text())))


def _date(value: str) -> dt.date:
    if len(value) != 10:
        raise ValueError(value)
    return dt.date.fromisoformat(value)


def _infer(rows: list[dict], column: str) -> str:
    values = [r[column] for r in rows if r[column] != ""]
    for kind, cast in (("INT64", int), ("NUMERIC", float), ("DATE", _date)):
        try:
            for v in values:
                cast(v)
            return kind
        except ValueError:
            continue
    return "STRING"


def _typed(rows: list[dict], schema: list[bigquery.SchemaField]):
    types = {f.name: f.field_type for f in schema}
    out_schema = list(schema)
    for column in rows[0] if rows else []:
        if column not in types:
            types[column] = _infer(rows, column)
            out_schema.append(bigquery.SchemaField(column, types[column]))
    typed = [
        {k: (None if v == "" else TYPES.get(types[k], str)(v)) for k, v in row.items()}
        for row in rows
    ]
    return typed, out_schema


def _retrying(job_fn, attempts: int = 5, base_delay: float = 2.0):
    """Run a BigQuery job, retrying with backoff on rate-limit errors.

    BigQuery enforces a limit on table update operations per table (DELETE
    and load jobs both count). A day's replace_day does one of each, so a
    busy run can be rate limited partway through -- after the DELETE has
    already removed the day's rows. Retrying the same call is safe here
    because both the DELETE and the load are idempotent for a given day.
    """
    for attempt in range(attempts):
        try:
            return job_fn()
        except (TooManyRequests, Forbidden) as exc:
            if attempt == attempts - 1:
                raise
            if isinstance(exc, Forbidden) and "rateLimitExceeded" not in str(exc):
                raise
            delay = base_delay * (2**attempt)
            print(f"rate limited ({exc.__class__.__name__}), retrying in {delay:.0f}s")
            time.sleep(delay)


def ensure_columns(table: str, columns: list) -> None:
    """Add columns to a raw table if they are not already there.

    Lets a PR add a vendor's upcoming export columns to a raw table ahead of
    time, as nullable, so the schema change ships through review like any
    other code change instead of a manual ALTER TABLE. If the table does not
    exist yet, this is a no-op: replace_day's first load creates it with
    whatever columns that day's rows have.
    """
    client = bigquery.Client(project=PROJECT)
    table_id = f"{PROJECT}.raw.{table}"
    try:
        table_ref = client.get_table(table_id)
    except NotFound:
        return
    existing = {f.name for f in table_ref.schema}
    missing = [c for c in columns if c.name not in existing]
    if not missing:
        return
    table_ref.schema = list(table_ref.schema) + missing
    client.update_table(table_ref, ["schema"])
    print(f"{table}: added columns {[c.name for c in missing]}")


def replace_day(table: str, date_column: str, day: dt.date, rows: list[dict]) -> str:
    client = bigquery.Client(project=PROJECT)
    table_id = f"{PROJECT}.raw.{table}"
    load_id = uuid.uuid4().hex
    loaded_at = dt.datetime.now(dt.timezone.utc).isoformat()

    # A new source's table is created by its first load.
    try:
        existing = client.get_table(table_id).schema
        _retrying(
            lambda: client.query(
                f"DELETE FROM `{table_id}` WHERE {date_column} = @day",
                job_config=bigquery.QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("day", "DATE", day)]
                ),
            ).result()
        )
    except NotFound:
        existing = [
            bigquery.SchemaField("_load_id", "STRING"),
            bigquery.SchemaField("_loaded_at", "TIMESTAMP"),
        ]

    if rows:
        typed, schema = _typed(rows, existing)
        for row in typed:
            row["_load_id"] = load_id
            row["_loaded_at"] = loaded_at
        _retrying(
            lambda: client.load_table_from_json(
                typed,
                table_id,
                job_config=bigquery.LoadJobConfig(
                    schema=schema,
                    write_disposition="WRITE_APPEND",
                    schema_update_options=["ALLOW_FIELD_ADDITION"],
                ),
            ).result()
        )
    print(f"{table} {day}: {len(rows)} rows, load {load_id}")
    return load_id
