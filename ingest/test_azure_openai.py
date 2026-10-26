"""Regression test for the Azure OpenAI usage export version 2 cutover.

Version 2 starts with usage for 2027-04-09, moves the file to a v2/
subfolder, and reports the day as usage_date_utc instead of usage_date.
replace_day's delete key has to match whichever date column a day's file
actually has, so load() must pick the file path and date column by day.
"""

import datetime as dt
import unittest
from unittest import mock

from ingest import azure_openai


class AzureOpenAILoadTest(unittest.TestCase):
    @mock.patch.object(azure_openai, "replace_day")
    @mock.patch.object(azure_openai, "read_landed_csv")
    def test_version_1_day_uses_old_path_and_date_column(self, read_csv, replace_day):
        read_csv.return_value = [{"usage_date": "2027-04-08"}]

        azure_openai.load(dt.date(2027, 4, 8))

        read_csv.assert_called_once_with("azure_openai/usage_2027-04-08.csv")
        replace_day.assert_called_once_with(
            "azure_openai_usage", "usage_date", dt.date(2027, 4, 8), read_csv.return_value
        )

    @mock.patch.object(azure_openai, "replace_day")
    @mock.patch.object(azure_openai, "read_landed_csv")
    def test_version_2_day_uses_new_path_and_date_column(self, read_csv, replace_day):
        read_csv.return_value = [{"usage_date_utc": "2027-04-09"}]

        azure_openai.load(dt.date(2027, 4, 9))

        read_csv.assert_called_once_with("azure_openai/v2/usage_2027-04-09.csv")
        replace_day.assert_called_once_with(
            "azure_openai_usage",
            "usage_date_utc",
            dt.date(2027, 4, 9),
            read_csv.return_value,
        )


if __name__ == "__main__":
    unittest.main()
