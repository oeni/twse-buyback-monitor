import unittest

from twse_buyback import parse
from twse_buyback.errors import StructureChanged

from .helpers import SAMPLE_HTML, build_html, codes_html, data_row


class TestParse(unittest.TestCase):
    def test_parses_individual_cases(self):
        records = parse.parse(SAMPLE_HTML, "sii")
        self.assertEqual(parse.count_cases(records), 2)

    def test_field_mapping(self):
        records = parse.parse(SAMPLE_HTML, "sii")
        rec = next(r for r in records if r["code"] == "1101" and not r["is_cumulative"])
        self.assertEqual(rec["board_date"], "114/06/30")
        self.assertEqual(rec["planned_shares"], "10,000,000")
        self.assertEqual(rec["done"], "Y")
        self.assertEqual(rec["bought_ratio_pct"], "100.00")
        self.assertEqual(rec["purpose_text"], "轉讓股份予員工")
        self.assertEqual(rec["market"], "sii")

    def test_cumulative_rows_flagged_not_dropped(self):
        records = parse.parse(SAMPLE_HTML, "sii")
        cumulative = [r for r in records if r["is_cumulative"]]
        self.assertEqual(len(cumulative), 1)
        self.assertEqual(cumulative[0]["code"], "1101")

    def test_unknown_purpose_code_falls_back_to_the_code(self):
        html = codes_html(["1101"], purpose="9")
        rec = parse.parse(html, "sii")[0]
        self.assertEqual(rec["purpose_text"], "9")

    def test_missing_title_raises(self):
        with self.assertRaises(StructureChanged):
            parse.parse("<html><body>nothing here</body></html>", "sii")

    def test_zero_data_rows_raises(self):
        html = "<html><body>買回自己公司股份<table><tr><td>x</td></tr></table></body></html>"
        with self.assertRaises(StructureChanged):
            parse.parse(html, "sii")


class TestCompletenessDetection(unittest.TestCase):
    """The structural half of the truncation guard."""

    def test_complete_body_recognised(self):
        self.assertTrue(parse.is_complete_html(SAMPLE_HTML))
        self.assertTrue(parse.is_complete_html(codes_html(["1101", "2603"])))

    def test_trailing_whitespace_tolerated(self):
        self.assertTrue(parse.is_complete_html(codes_html(["1101"]) + "\n\n  \n"))

    def test_truncated_body_rejected(self):
        truncated = codes_html(["1101", "2603"], complete=False)
        self.assertFalse(parse.is_complete_html(truncated))

    def test_truncated_body_still_parses_which_is_why_the_check_exists(self):
        # This is the crux of the original bug: a truncated response is not a
        # parse error. It yields valid rows, just not all of them.
        truncated = build_html([data_row("1101"), data_row("2603")], complete=False)
        records = parse.parse(truncated, "sii")
        self.assertEqual(parse.count_cases(records), 2)
        self.assertFalse(parse.is_complete_html(truncated))


if __name__ == "__main__":
    unittest.main()
