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

from google.api_core.exceptions import NotFound
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


def replace_day(table: str, date_column: str, day: dt.date, rows: list[dict]) -> str:
    client = bigquery.Client(project=PROJECT)
    table_id = f"{PROJECT}.raw.{table}"
    load_id = uuid.uuid4().hex
    loaded_at = dt.datetime.now(dt.timezone.utc).isoformat()

    # A new source's table is created by its first load.
    try:
        existing = client.get_table(table_id).schema
        client.query(
            f"DELETE FROM `{table_id}` WHERE {date_column} = @day",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("day", "DATE", day)]
            ),
        ).result()
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
        client.load_table_from_json(
            typed,
            table_id,
            job_config=bigquery.LoadJobConfig(
                schema=schema,
                write_disposition="WRITE_APPEND",
                schema_update_options=["ALLOW_FIELD_ADDITION"],
            ),
        ).result()
    print(f"{table} {day}: {len(rows)} rows, load {load_id}")
    return load_id
