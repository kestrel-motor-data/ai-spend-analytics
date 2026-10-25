"""Regression test for replace_day's rate-limit retry.

DATA14D incident: a backfill hit BigQuery's per-table rate limit mid-run.
The DELETE for a day succeeded but the following load job was rejected with
a 429, and nothing retried it, so the day was left with zero rows. This
checks that a rate-limit error is retried instead of being left half-done.
"""

import unittest
from unittest import mock

from google.api_core.exceptions import Forbidden, NotFound, TooManyRequests

from ingest import common


class RetryingTest(unittest.TestCase):
    def test_retries_too_many_requests_then_succeeds(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise TooManyRequests("rate limited")
            return "ok"

        with mock.patch.object(common.time, "sleep") as sleep:
            result = common._retrying(flaky, attempts=5, base_delay=0.01)

        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleep.call_count, 2)

    def test_retries_forbidden_rate_limit_message(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise Forbidden("rateLimitExceeded: too many table update operations")
            return "ok"

        with mock.patch.object(common.time, "sleep"):
            result = common._retrying(flaky, attempts=5, base_delay=0.01)

        self.assertEqual(result, "ok")

    def test_does_not_retry_unrelated_forbidden(self):
        def always_denied():
            raise Forbidden("Access Denied: no permission")

        with mock.patch.object(common.time, "sleep") as sleep:
            with self.assertRaises(Forbidden):
                common._retrying(always_denied, attempts=5, base_delay=0.01)

        sleep.assert_not_called()

    def test_raises_after_exhausting_attempts(self):
        def always_limited():
            raise TooManyRequests("rate limited")

        with mock.patch.object(common.time, "sleep"):
            with self.assertRaises(TooManyRequests):
                common._retrying(always_limited, attempts=3, base_delay=0.01)

    def test_other_errors_are_not_retried(self):
        def not_found():
            raise NotFound("no such table")

        with mock.patch.object(common.time, "sleep") as sleep:
            with self.assertRaises(NotFound):
                common._retrying(not_found, attempts=5, base_delay=0.01)

        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
