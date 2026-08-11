import unittest
from pathlib import Path

from twse_buyback import fetch, parse
from twse_buyback.config import Settings
from twse_buyback.errors import FetchError, TruncatedResponse

from .helpers import FakeResponse, FakeSession, codes_html, no_sleep

FULL = [str(1000 + i) for i in range(100)]
SHORT = FULL[:40]


def settings(**kwargs):
    # These tests never touch disk; data_dir just has to be a valid Path.
    kwargs.setdefault("data_dir", Path("unused"))
    return Settings(**kwargs)


class TestFetchHtml(unittest.TestCase):
    def test_non_200_raises(self):
        class Failing:
            def post(self, *a, **k):
                return FakeResponse("", status_code=503)

        with self.assertRaises(FetchError) as ctx:
            fetch.fetch_html("sii", settings(), session=Failing())
        self.assertIn("503", str(ctx.exception))

    def test_non_utf8_raises(self):
        class Latin1:
            def post(self, *a, **k):
                response = FakeResponse("")
                response.content = b"\xff\xfe not utf-8"
                return response

        with self.assertRaises(FetchError) as ctx:
            fetch.fetch_html("sii", settings(), session=Latin1())
        self.assertIn("UTF-8", str(ctx.exception))


class TestTruncationGuard(unittest.TestCase):
    """Regression tests for the mass false-positive bug.

    A truncated response used to be accepted and written over the snapshot;
    the next complete response then looked like hundreds of new filings.
    """

    def test_complete_response_accepted_first_try(self):
        session = FakeSession([codes_html(FULL)])
        records, warnings = fetch.fetch_market("sii", settings(), None, session, no_sleep)
        self.assertEqual(parse.count_cases(records), 100)
        self.assertEqual(warnings, [])
        self.assertEqual(session.calls, 1)

    def test_body_missing_closing_tag_is_retried_then_accepted(self):
        session = FakeSession([codes_html(FULL, complete=False), codes_html(FULL)])
        records, warnings = fetch.fetch_market("sii", settings(), None, session, no_sleep)
        self.assertEqual(parse.count_cases(records), 100)
        self.assertEqual(session.calls, 2)
        self.assertIn("truncated mid-stream", warnings[0])

    def test_persistently_truncated_body_raises(self):
        session = FakeSession([codes_html(FULL, complete=False)])
        with self.assertRaises(TruncatedResponse):
            fetch.fetch_market("sii", settings(), None, session, no_sleep)
        self.assertEqual(session.calls, 3)

    def test_short_row_count_is_retried_then_accepted(self):
        # Truncation that lands on a tag boundary still yields a well-formed
        # body, so the row count is the only thing that catches it.
        session = FakeSession([codes_html(SHORT), codes_html(FULL)])
        records, warnings = fetch.fetch_market("sii", settings(), 100, session, no_sleep)
        self.assertEqual(parse.count_cases(records), 100)
        self.assertEqual(session.calls, 2)
        self.assertIn("only 40 cases", warnings[0])

    def test_persistently_short_row_count_raises(self):
        session = FakeSession([codes_html(SHORT)])
        with self.assertRaises(TruncatedResponse) as ctx:
            fetch.fetch_market("sii", settings(), 100, session, no_sleep)
        self.assertIn("snapshot left unchanged", str(ctx.exception))

    def test_small_natural_shrinkage_is_tolerated(self):
        # The table does not shrink in normal operation, but the guard should
        # not fire on noise either.
        session = FakeSession([codes_html(FULL[:97])])
        records, warnings = fetch.fetch_market("sii", settings(), 100, session, no_sleep)
        self.assertEqual(parse.count_cases(records), 97)
        self.assertEqual(warnings, [])

    def test_no_baseline_means_no_count_check(self):
        # A first run has nothing to compare against; only the structural
        # check applies.
        session = FakeSession([codes_html(SHORT)])
        records, warnings = fetch.fetch_market("sii", settings(), None, session, no_sleep)
        self.assertEqual(parse.count_cases(records), 40)
        self.assertEqual(warnings, [])

    def test_growth_is_never_blocked(self):
        session = FakeSession([codes_html(FULL)])
        records, _ = fetch.fetch_market("sii", settings(), 50, session, no_sleep)
        self.assertEqual(parse.count_cases(records), 100)


if __name__ == "__main__":
    unittest.main()
