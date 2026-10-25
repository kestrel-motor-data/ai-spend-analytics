"""Anthropic API usage, from Kestrel's Anthropic usage API.

Kestrel's Anthropic proxy only serves a usage report (token counts per day,
per workspace, per model) - there is no cost endpoint (the vendor's own
Cost Report API 404s on this host; confirmed against
https://kestrel-anthropic-api.paddoxtechnologies.com/docs, which Kestrel pays
list price and expects cost worked out from token counts). So this ingest
only pulls usage_report/messages and lands raw token counts; cost is computed
downstream from the published per-model price table (staging model, part B),
not in the ingest step.

Queried a single UTC day at a time (bucket_width=1d, starting_at/ending_at one
day apart), grouped by workspace_id and model (the only two group_by values
this API accepts). Responses paginate via next_page/has_more.

Requires an Admin API key (org:admin scope) in ANTHROPIC_API_TOKEN - a normal
API key cannot call this endpoint.
"""

import datetime as dt
import os
import time

import requests

from ingest.common import replace_day

BASE_URL = "https://kestrel-anthropic-api.paddoxtechnologies.com"
ANTHROPIC_VERSION = "2023-06-01"


def _headers() -> dict:
    return {
        "x-api-key": os.environ["ANTHROPIC_API_TOKEN"],
        "anthropic-version": ANTHROPIC_VERSION,
    }


def _get_all(path: str, params: dict) -> list[dict]:
    """Fetch every row across every time bucket and page for one path."""
    out: list[dict] = []
    page = None
    while True:
        query = dict(params)
        if page:
            query["page"] = page
        resp = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=query)
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("retry-after", "60")))
            continue
        resp.raise_for_status()
        body = resp.json()
        for bucket in body["data"]:
            for row in bucket["results"]:
                row["bucket_start"] = bucket["starting_at"][:10]
                out.append(row)
        if not body.get("has_more"):
            return out
        page = body["next_page"]


def _flatten_usage(row: dict, day: dt.date) -> dict:
    cache_creation = row.get("cache_creation") or {}
    return {
        "day": day.isoformat(),
        "workspace_id": row.get("workspace_id"),
        "model": row.get("model"),
        "uncached_input_tokens": row.get("uncached_input_tokens", 0),
        "cache_read_input_tokens": row.get("cache_read_input_tokens", 0),
        # Kestrel's docs: all cache writes are 5-minute writes (1h is unused).
        "cache_creation_1h_input_tokens": cache_creation.get("ephemeral_1h_input_tokens", 0),
        "cache_creation_5m_input_tokens": cache_creation.get("ephemeral_5m_input_tokens", 0),
        "output_tokens": row.get("output_tokens", 0),
    }


def load(day: dt.date) -> None:
    starting_at = f"{day.isoformat()}T00:00:00Z"
    ending_at = f"{(day + dt.timedelta(days=1)).isoformat()}T00:00:00Z"

    usage_rows = _get_all(
        "/v1/organizations/usage_report/messages",
        {
            "starting_at": starting_at,
            "ending_at": ending_at,
            "bucket_width": "1d",
            "limit": 1,
            "group_by[]": ["workspace_id", "model"],
        },
    )
    replace_day("anthropic_usage", "day", day, [_flatten_usage(r, day) for r in usage_rows])
