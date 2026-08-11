"""Live checks against MOPS. Opt in with ``RUN_NETWORK_TESTS=1``.

These assert the assumptions the parser is built on, so when MOPS changes
something they are what tells you which assumption broke.
"""
import os
import unittest
from pathlib import Path

from twse_buyback import fetch, parse
from twse_buyback.config import Settings


@unittest.skipUnless(os.environ.get("RUN_NETWORK_TESTS") == "1",
                     "network test: set RUN_NETWORK_TESTS=1 to run")
class TestLiveEndpoint(unittest.TestCase):
    settings = Settings(data_dir=Path("unused"))

    def test_response_is_complete_and_parses(self):
        html = fetch.fetch_html("sii", self.settings)
        self.assertTrue(parse.is_complete_html(html), "response arrived truncated")
        records = parse.parse(html, "sii")
        self.assertGreater(parse.count_cases(records), 1000)

    def test_every_case_has_a_numeric_stock_code(self):
        html = fetch.fetch_html("sii", self.settings)
        records = parse.parse(html, "sii")
        self.assertTrue(all(r["code"].isdigit() for r in records))

    def test_year_and_month_parameters_are_ignored_by_mops(self):
        # The form takes a period, but the endpoint returns the full history
        # regardless. If this ever starts failing, MOPS has implemented the
        # filter and the completeness guard's thresholds need revisiting.
        import requests

        from twse_buyback import config

        counts = []
        for year, month in (("115", "08"), ("110", "01")):
            form = dict(config.FORM_BASE, TYPEK="sii", year=year, month=month)
            resp = requests.post(config.MOPS_URL, data=form,
                                 headers=self.settings.headers(), timeout=30)
            counts.append(parse.count_cases(parse.parse(resp.content.decode("utf-8"), "sii")))
        self.assertEqual(counts[0], counts[1])


if __name__ == "__main__":
    unittest.main()
