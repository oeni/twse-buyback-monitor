import unittest
from datetime import date

from twse_buyback import guard


def case(code, board):
    return {"market": "sii", "code": code, "name": f"公司{code}", "board_date": board}


class TestMinguoDate(unittest.TestCase):
    def test_converts_republic_year_to_gregorian(self):
        self.assertEqual(guard.parse_minguo_date("115/08/11"), date(2026, 8, 11))
        self.assertEqual(guard.parse_minguo_date("96/11/22"), date(2007, 11, 22))

    def test_placeholder_and_garbage_return_none(self):
        for value in ("----", "", None, "115/08", "abc/de/fg", "115/13/01", "115/02/30"):
            self.assertIsNone(guard.parse_minguo_date(value), value)


class TestSplitBackfill(unittest.TestCase):
    """Old-dated cases appearing today are recovered rows, not news."""

    def setUp(self):
        self.today = date(2026, 8, 11)

    def test_recent_cases_are_announcements(self):
        cases = [case("1101", "115/08/10"), case("2603", "115/07/01")]
        announcements, backfill = guard.split_backfill(cases, self.today, 6)
        self.assertEqual(len(announcements), 2)
        self.assertEqual(backfill, [])

    def test_decade_old_cases_are_backfill(self):
        # Exactly the rows the 2026-08-11 incident reported as new.
        cases = [case("3060", "96/11/22"), case("3059", "114/04/08")]
        announcements, backfill = guard.split_backfill(cases, self.today, 6)
        self.assertEqual(announcements, [])
        self.assertEqual([r["code"] for r in backfill], ["3060", "3059"])

    def test_mixed_batch_is_separated(self):
        cases = [case("1101", "115/08/11"), case("3060", "96/11/22")]
        announcements, backfill = guard.split_backfill(cases, self.today, 6)
        self.assertEqual([r["code"] for r in announcements], ["1101"])
        self.assertEqual([r["code"] for r in backfill], ["3060"])

    def test_unparseable_date_is_kept_as_announcement(self):
        # Never silently drop a case we cannot judge.
        announcements, backfill = guard.split_backfill([case("1101", "----")], self.today, 6)
        self.assertEqual(len(announcements), 1)
        self.assertEqual(backfill, [])

    def test_zero_months_disables_the_filter(self):
        cases = [case("3060", "96/11/22")]
        announcements, backfill = guard.split_backfill(cases, self.today, 0)
        self.assertEqual(len(announcements), 1)
        self.assertEqual(backfill, [])


class TestSurge(unittest.TestCase):
    def test_plausible_count_passes(self):
        self.assertIsNone(guard.check_surge([case("1101", "115/08/11")] * 8, 50))

    def test_implausible_count_flagged(self):
        message = guard.check_surge([case("1101", "115/08/11")] * 998, 50)
        self.assertIsNotNone(message)
        self.assertIn("998", message)

    def test_threshold_zero_disables(self):
        self.assertIsNone(guard.check_surge([case("1101", "115/08/11")] * 998, 0))


class TestRemovals(unittest.TestCase):
    def test_no_removals_is_silent(self):
        self.assertIsNone(guard.check_removals([], 50))

    def test_any_removal_is_flagged(self):
        message = guard.check_removals([case("1101", "115/08/11")], 50)
        self.assertIsNotNone(message)
        self.assertIn("sii/1101", message)

    def test_large_batch_named_differently(self):
        message = guard.check_removals([case(str(i), "115/08/11") for i in range(100)], 50)
        self.assertIn("large batch", message)
        self.assertIn("...", message)


if __name__ == "__main__":
    unittest.main()
