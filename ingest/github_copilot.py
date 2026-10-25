"""GitHub Copilot usage and seats, from the Kestrel Copilot usage API.

Usage is per user per day; a day with no activity for a user has no row.
Seats have no history endpoint, so each night's load takes a snapshot of
who currently holds a seat and records it under that day - a login's
absence on a later day means the seat was no longer held then.
"""

import datetime as dt
import os
import time

import requests

from ingest.common import replace_day

BASE_URL = "https://kestrel-copilot-api.paddoxtechnologies.com"
PAGE_ROWS = {"usage": "usage", "seats": "seats"}


def _get_all(path: str, params: dict, rows_key: str) -> list[dict]:
    token = os.environ["COPILOT_API_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}
    out: list[dict] = []
    page = 1
    while True:
        resp = requests.get(
            f"{BASE_URL}{path}", headers=headers, params={**params, "page": page}
        )
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", "60")))
            continue
        resp.raise_for_status()
        out.extend(resp.json()[rows_key])
        if 'rel="next"' not in resp.headers.get("Link", ""):
            return out
        page += 1


def load(day: dt.date) -> None:
    usage = _get_all(
        "/orgs/kestrel/copilot/usage",
        {"since": day.isoformat(), "until": day.isoformat()},
        "usage",
    )
    replace_day("github_copilot_usage", "day", day, usage)

    seats = _get_all("/orgs/kestrel/copilot/seats", {}, "seats")
    for row in seats:
        row["day"] = day.isoformat()
    replace_day("github_copilot_seats", "day", day, seats)
