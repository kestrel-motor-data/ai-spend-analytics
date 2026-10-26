"""Regression test for the Azure OpenAI v2 cutover (DATA14D).

load() now calls ensure_columns before reading the landed file, so the v2
export's new columns (usage_date_utc, key_id, deployment_name, model,
prompt/cached/completion tokens, billed_amount, billing_currency) exist on
raw.azure_openai_usage as nullable columns before the first v2 file ever
lands on 2027-04-09. Without this, the staging model that references them
would hit a hard BigQuery "Unrecognized name" error the first night a v2
file loads, instead of a plain missing/null value.
"""

import datetime as dt
import unittest
from unittest import mock

from ingest import azure_openai


class LoadTest(unittest.TestCase):
    def test_load_ensures_v2_columns_before_reading_file(self):
        calls = []
        with mock.patch.object(azure_openai, "ensure_columns") as ensure_columns, \
                mock.patch.object(azure_openai, "read_landed_csv", return_value=[]) as read_csv, \
                mock.patch.object(azure_openai, "replace_day") as replace_day:
            ensure_columns.side_effect = lambda *a: calls.append("ensure_columns")
            read_csv.side_effect = lambda *a: calls.append("read_landed_csv") or []

            azure_openai.load(dt.date(2027, 3, 24))

        self.assertEqual(calls, ["ensure_columns", "read_landed_csv"])
        ensure_columns.assert_called_once_with("azure_openai_usage", azure_openai.V2_COLUMNS)
        read_csv.assert_called_once_with("azure_openai/usage_2027-03-24.csv")
        replace_day.assert_called_once_with("azure_openai_usage", "usage_date", dt.date(2027, 3, 24), [])

    def test_v2_columns_cover_every_renamed_field(self):
        names = {c.name for c in azure_openai.V2_COLUMNS}
        self.assertEqual(
            names,
            {
                "usage_date_utc",
                "key_id",
                "deployment_name",
                "model",
                "prompt_tokens",
                "cached_prompt_tokens",
                "completion_tokens",
                "billed_amount",
                "billing_currency",
            },
        )


if __name__ == "__main__":
    unittest.main()
