"""Regression test for record_alert's NUMERIC rounding.

DATA14D-116: once the pipeline service account could finally write to
`reporting`, the first real alert (Supply Chain, 91.238693027333329%)
still failed. cost / budget is a float with far more precision than
BigQuery's NUMERIC type allows, and insert_rows_json rejected it outright
("Invalid NUMERIC value"). This checks that record_alert rounds pct to a
NUMERIC-safe string before inserting, for both a typical ratio and one
with many trailing digits.
"""

import datetime as dt
import unittest
from unittest import mock

from google.api_core.exceptions import NotFound

from alerts import budget_alerts


class RecordAlertRoundingTest(unittest.TestCase):
    def _insert_pct(self, pct):
        client = mock.Mock()
        client.get_table.side_effect = NotFound("no table")
        client.insert_rows_json.return_value = []
        budget_alerts.record_alert(client, dt.date(2027, 3, 1), "Supply Chain", pct)
        _, args, _ = client.insert_rows_json.mock_calls[0]
        return args[1][0]["pct"]

    def test_rounds_long_decimal_to_numeric_safe_string(self):
        row_pct = self._insert_pct(0.91238693027333329)
        self.assertEqual(row_pct, "0.912387")
        # Confirms it no longer has more precision than BigQuery NUMERIC
        # type's default scale (9 digits) can hold.
        self.assertLessEqual(len(row_pct.split(".")[1]), 9)

    def test_rounds_typical_ratio_cleanly(self):
        self.assertEqual(self._insert_pct(0.9), "0.900000")


if __name__ == "__main__":
    unittest.main()
