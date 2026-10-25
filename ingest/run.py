"""Load landed files into raw for a date range.

    python -m ingest.run --start 2027-03-21 --end 2027-03-21
    python -m ingest.run --start 2027-03-21 --end 2027-03-21 --source azure_openai
"""

import argparse
import datetime as dt

from ingest import azure_openai, github_copilot, m365_copilot
from ingest.common import days

SOURCES = {
    "azure_openai": azure_openai.load,
    "m365_copilot": m365_copilot.load,
    "github_copilot": github_copilot.load,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--end", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--source", default=",".join(SOURCES))
    args = parser.parse_args()

    for name in args.source.split(","):
        for day in days(args.start, args.end):
            SOURCES[name](day)
