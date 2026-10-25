"""Anthropic API usage and cost, from the Usage and Cost Admin API.

Usage and cost are two separate endpoints. We load the cost endpoint's daily
totals by workspace as spend, and the usage endpoint's daily totals by
workspace as a token count. Both are queried for a single UTC day at a time
(bucket_width=1d, starting_at/ending_at one day apart), so each call returns
at most one time bucket; `limit=1` keeps that explicit. Responses paginate
within a bucket via `next_page`/`has_more`, same shape as the vendor's other
list endpoints.

Requires an Admin API key (org:admin scope) in ANTHROPIC_API_TOKEN - a normal
API key cannot call these endpoints.
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


def _flatten_cost(row: dict, day: dt.date) -> dict:
    return {
        "day": day.isoformat(),
        "workspace_id": row.get("workspace_id"),
        "description": row.get("description"),
        "cost_type": row.get("cost_type"),
        "model": row.get("model"),
        "service_tier": row.get("service_tier"),
        "amount_usd": row.get("amount"),
        "currency": row.get("currency"),
    }


def _flatten_usage(row: dict, day: dt.date) -> dict:
    cache_creation = row.get("cache_creation") or {}
    return {
        "day": day.isoformat(),
        "workspace_id": row.get("workspace_id"),
        "api_key_id": row.get("api_key_id"),
        "model": row.get("model"),
        "service_tier": row.get("service_tier"),
        "uncached_input_tokens": row.get("uncached_input_tokens", 0),
        "cache_read_input_tokens": row.get("cache_read_input_tokens", 0),
        "cache_creation_1h_input_tokens": cache_creation.get("ephemeral_1h_input_tokens", 0),
        "cache_creation_5m_input_tokens": cache_creation.get("ephemeral_5m_input_tokens", 0),
        "output_tokens": row.get("output_tokens", 0),
    }


def load(day: dt.date) -> None:
    starting_at = f"{day.isoformat()}T00:00:00Z"
    ending_at = f"{(day + dt.timedelta(days=1)).isoformat()}T00:00:00Z"

    cost_rows = _get_all(
        "/v1/organizations/cost_report",
        {
            "starting_at": starting_at,
            "ending_at": ending_at,
            "bucket_width": "1d",
            "limit": 1,
            "group_by[]": ["workspace_id", "description"],
        },
    )
    replace_day("anthropic_cost", "day", day, [_flatten_cost(r, day) for r in cost_rows])

    usage_rows = _get_all(
        "/v1/organizations/usage_report/messages",
        {
            "starting_at": starting_at,
            "ending_at": ending_at,
            "bucket_width": "1d",
            "limit": 1,
            "group_by[]": ["workspace_id", "api_key_id", "model", "service_tier"],
        },
    )
    replace_day("anthropic_usage", "day", day, [_flatten_usage(r, day) for r in usage_rows])
