"""Regression tests for the Azure OpenAI v2 cutover (DATA14D-114).

load() ensures the v2 columns exist on raw.azure_openai_usage ahead of the
cutover, then picks the v1 or v2 landing path and date column by day: before
2027-04-09 it reads the old path and keys replace_day on usage_date; from
2027-04-09 it reads the new `v2/` path and keys on usage_date_utc, since v2
rows don't carry usage_date at all.
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

    def test_load_reads_v1_path_before_cutover(self):
        with mock.patch.object(azure_openai, "ensure_columns"), \
                mock.patch.object(azure_openai, "read_landed_csv", return_value=[]) as read_csv, \
                mock.patch.object(azure_openai, "replace_day") as replace_day:
            azure_openai.load(dt.date(2027, 4, 8))

        read_csv.assert_called_once_with("azure_openai/usage_2027-04-08.csv")
        replace_day.assert_called_once_with(
            "azure_openai_usage", "usage_date", dt.date(2027, 4, 8), []
        )

    def test_load_reads_v2_path_from_cutover(self):
        with mock.patch.object(azure_openai, "ensure_columns"), \
                mock.patch.object(azure_openai, "read_landed_csv", return_value=[]) as read_csv, \
                mock.patch.object(azure_openai, "replace_day") as replace_day:
            azure_openai.load(dt.date(2027, 4, 9))

        read_csv.assert_called_once_with("azure_openai/v2/usage_2027-04-09.csv")
        replace_day.assert_called_once_with(
            "azure_openai_usage", "usage_date_utc", dt.date(2027, 4, 9), []
        )


if __name__ == "__main__":
    unittest.main()
