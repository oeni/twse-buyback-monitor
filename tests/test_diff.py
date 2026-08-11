import unittest

from twse_buyback import diff
from twse_buyback.errors import BuybackError


def case(code, board="115/06/30", purpose="1", period_start="115/07/01",
         period_end="115/09/01", bought="", ratio="", done="N",
         cumulative=False, market="sii", **extra):
    rec = {
        "market": market, "code": code, "name": f"公司{code}", "board_date": board,
        "purpose_code": purpose, "purpose_text": "轉讓股份予員工",
        "period_start": period_start, "period_end": period_end,
        "bought_shares": bought, "bought_ratio_pct": ratio, "done": done,
        "bought_amount": "", "note": "", "is_cumulative": cumulative,
    }
    rec.update(extra)
    return rec


class TestDiff(unittest.TestCase):
    def test_new_case_detected(self):
        new, changed, removed = diff.diff([case("1101")], [case("1101"), case("2603")])
        self.assertEqual([r["code"] for r in new], ["2603"])
        self.assertEqual((changed, removed), ([], []))

    def test_execution_progress_detected(self):
        prev = [case("1101", bought="", ratio="", done="N")]
        curr = [case("1101", bought="5,000,000", ratio="50.00", done="N")]
        new, changed, removed = diff.diff(prev, curr)
        self.assertEqual((new, removed), ([], []))
        rec, deltas = changed[0]
        self.assertEqual(rec["code"], "1101")
        self.assertEqual({d[0] for d in deltas}, {"bought_shares", "bought_ratio_pct"})

    def test_extended_buyback_window_is_a_change_not_a_new_case(self):
        # period_end moves when a buyback window is extended. It must be
        # reported, but it must not be part of the identity key, or the
        # extension would look like a brand-new filing.
        prev = [case("1101", period_end="115/09/01")]
        curr = [case("1101", period_end="115/09/30")]
        new, changed, removed = diff.diff(prev, curr)
        self.assertEqual((new, removed), ([], []))
        self.assertEqual([d[0] for d in changed[0][1]], ["period_end"])

    def test_removed_case_reported(self):
        new, changed, removed = diff.diff([case("1101"), case("2603")], [case("1101")])
        self.assertEqual((new, changed), ([], []))
        self.assertEqual([r["code"] for r in removed], ["2603"])

    def test_no_change(self):
        self.assertEqual(diff.diff([case("1101")], [case("1101")]), ([], [], []))

    def test_first_run_reports_nothing(self):
        self.assertEqual(diff.diff(None, [case("1101"), case("2603")]), ([], [], []))

    def test_cumulative_rows_ignored(self):
        prev = [case("1101")]
        curr = [case("1101"), case("1101", cumulative=True, board="----",
                                    purpose="----", period_start="----")]
        self.assertEqual(diff.diff(prev, curr), ([], [], []))

    def test_same_code_different_markets_are_distinct_cases(self):
        prev = [case("6666", market="sii")]
        curr = [case("6666", market="sii"), case("6666", market="otc")]
        new, _, removed = diff.diff(prev, curr)
        self.assertEqual([r["market"] for r in new], ["otc"])
        self.assertEqual(removed, [])

    def test_duplicate_key_raises_rather_than_overwriting(self):
        duplicated = [case("1101"), case("1101")]
        with self.assertRaises(BuybackError):
            diff.diff(duplicated, duplicated)


if __name__ == "__main__":
    unittest.main()
