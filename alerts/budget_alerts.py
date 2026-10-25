"""Nightly budget-threshold alert.

Checks each department's spend for a month against its monthly AI budget
(raw.ai_budgets, surfaced in marts.rpt_ai_spend_monthly) and posts once to
the AI Spend Report Slack channel the first time a department passes 90%
of its budget for that month. State lives in reporting.budget_alerts_sent so a
full model rebuild every night never produces a duplicate post.
"""

import argparse
import datetime as dt
import os

import requests
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

PROJECT = os.environ["GCP_PROJECT"]
THRESHOLD = 0.9
STATE_TABLE = "reporting.budget_alerts_sent"


def over_threshold(client, month):
    query = f"""
        with by_department as (
            select department, sum(cost) as cost, any_value(budget) as budget
            from `{PROJECT}.marts.rpt_ai_spend_monthly`
            where month = @month and budget is not null
            group by department
        )
        select department, cost, budget
        from by_department
        where safe_divide(cost, budget) >= @threshold
    """
    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("month", "DATE", month),
                bigquery.ScalarQueryParameter("threshold", "FLOAT64", THRESHOLD),
            ]
        ),
    )
    return [(row.department, float(row.cost), float(row.budget)) for row in job.result()]


def already_alerted(client, month, department):
    table_id = f"{PROJECT}.{STATE_TABLE}"
    try:
        client.get_table(table_id)
    except NotFound:
        return False
    query = f"""
        select 1 from `{table_id}`
        where month = @month and department = @department
        limit 1
    """
    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("month", "DATE", month),
                bigquery.ScalarQueryParameter("department", "STRING", department),
            ]
        ),
    )
    return job.result().total_rows > 0


def record_alert(client, month, department, pct):
    table_id = f"{PROJECT}.{STATE_TABLE}"
    schema = [
        bigquery.SchemaField("month", "DATE"),
        bigquery.SchemaField("department", "STRING"),
        bigquery.SchemaField("pct", "NUMERIC"),
        bigquery.SchemaField("alerted_at", "TIMESTAMP"),
    ]
    try:
        client.get_table(table_id)
    except NotFound:
        client.create_table(bigquery.Table(table_id, schema=schema))
    errors = client.insert_rows_json(
        table_id,
        [
            {
                "month": month.isoformat(),
                "department": department,
                "pct": pct,
                "alerted_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
        ],
    )
    if errors:
        raise RuntimeError(f"failed to record alert for {department}: {errors}")


def post_slack(webhook_url, department, pct, month):
    text = f"{department} has passed {pct:.0%} of its AI budget for {month:%B %Y}."
    response = requests.post(webhook_url, json={"text": text}, timeout=10)
    response.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="First day of the month, YYYY-MM-DD")
    args = parser.parse_args()
    month = dt.date.fromisoformat(args.month)
    if month.day != 1:
        raise ValueError(f"--month must be the first of the month, got {args.month}")

    webhook_url = os.environ["SLACK_REPORT_WEBHOOK"]
    client = bigquery.Client(project=PROJECT)

    for department, cost, budget in over_threshold(client, month):
        if already_alerted(client, month, department):
            continue
        pct = cost / budget
        post_slack(webhook_url, department, pct, month)
        record_alert(client, month, department, pct)
        print(f"alerted {department}: {pct:.1%} of budget for {month:%B %Y}")


if __name__ == "__main__":
    main()
