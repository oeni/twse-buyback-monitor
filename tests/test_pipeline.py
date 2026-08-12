import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from twse_buyback import pipeline, storage
from twse_buyback.config import Settings
from twse_buyback.errors import TruncatedResponse

from .helpers import FakeSession, build_html, codes_html, data_row, no_sleep

TODAY = date(2026, 8, 11)
FULL = [str(1000 + i) for i in range(100)]


class PipelineCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = Settings(data_dir=self.tmp, markets=("sii",), max_attempts=2)

    def run_with(self, *bodies):
        return pipeline.run(self.settings, today=TODAY,
                            session=FakeSession(bodies), sleep=no_sleep)

    def log_rows(self):
        with self.settings.changes_log_csv.open(encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))


class TestBaseline(PipelineCase):
    def test_first_run_establishes_baseline_without_announcing(self):
        result = self.run_with(codes_html(FULL))
        self.assertTrue(result.baseline)
        self.assertEqual(result.announcements, [])
        self.assertTrue(self.settings.snapshot_csv.exists())
        self.assertTrue(self.settings.report_md(result.date).exists())
        self.assertIn("首次執行已建立基準資料",
                      self.settings.report_md(result.date).read_text(encoding="utf-8"))
        self.assertIn("baseline established: 100 cases", result.summary())

    def test_second_identical_run_reports_nothing(self):
        self.run_with(codes_html(FULL))
        result = self.run_with(codes_html(FULL))
        self.assertFalse(result.baseline)
        self.assertEqual(result.summary(), "new=0 changed=0")
        report = self.settings.report_md(result.date).read_text(encoding="utf-8")
        self.assertIn("今日無新增公告或執行進度異動。", report)


class TestNormalOperation(PipelineCase):
    def test_new_filing_is_announced_and_logged(self):
        self.run_with(codes_html(FULL))
        result = self.run_with(codes_html(FULL + ["9999"]))
        self.assertEqual([r["code"] for r in result.announcements], ["9999"])
        self.assertEqual(self.log_rows()[0]["type"], "new")

    def test_execution_progress_is_reported(self):
        self.run_with(build_html([data_row("1101")]))
        result = self.run_with(build_html([data_row("1101", done="Y", bought="500,000")]))
        self.assertEqual(len(result.changed), 1)
        self.assertEqual({d[0] for d in result.changed[0][1]}, {"done", "bought_shares"})


class TestTruncationRegression(PipelineCase):
    """The 2026-08 incident, end to end.

    Timeline that produced it: a truncated response overwrote the snapshot,
    and the next complete response reported the missing tail as 998 new
    filings dating back to 2007.
    """

    def test_truncated_response_does_not_touch_the_snapshot(self):
        self.run_with(codes_html(FULL))
        before = self.settings.snapshot_csv.read_bytes()
        report_path = self.settings.report_md(TODAY.strftime("%Y-%m-%d"))
        report_before = report_path.read_bytes()

        with self.assertRaises(TruncatedResponse):
            self.run_with(codes_html(FULL[:40]))

        self.assertEqual(self.settings.snapshot_csv.read_bytes(), before,
                         "a short response must never become the new baseline")
        self.assertEqual(report_path.read_bytes(), report_before,
                         "a failed fetch must not overwrite the daily report")

    def test_recovery_run_after_truncation_reports_nothing(self):
        self.run_with(codes_html(FULL))
        with self.assertRaises(TruncatedResponse):
            self.run_with(codes_html(FULL[:40]))
        result = self.run_with(codes_html(FULL))
        self.assertEqual(result.announcements, [])
        self.assertEqual(result.removed, [])

    def test_transient_truncation_self_heals_within_one_run(self):
        self.run_with(codes_html(FULL))
        result = self.run_with(codes_html(FULL[:40]), codes_html(FULL))
        self.assertEqual(result.announcements, [])
        self.assertEqual(len(result.fetch_warnings), 1)

    def test_old_cases_reappearing_are_backfill_not_news(self):
        # Bypasses the fetch guards by keeping the row count high, so this
        # exercises the last line of defence on its own.
        recent = [data_row(c, board_date="115/08/10") for c in FULL]
        old = [data_row("3060", board_date="96/11/22", period_start="96/11/23")]
        self.run_with(build_html(recent))
        result = self.run_with(build_html(recent + old))

        self.assertEqual(result.announcements, [])
        self.assertEqual([r["code"] for r in result.backfill], ["3060"])
        self.assertTrue(any("回補" in a for a in result.anomalies))
        self.assertEqual(self.log_rows()[0]["type"], "backfill")

    def test_mass_new_filings_flagged_as_implausible(self):
        base = [data_row(c, board_date="115/08/10") for c in FULL]
        surge = [data_row(str(5000 + i), board_date="115/08/11") for i in range(200)]
        self.run_with(build_html(base))
        result = self.run_with(build_html(base + surge))

        self.assertEqual(len(result.announcements), 200)
        self.assertTrue(any("合理門檻" in a for a in result.anomalies))
        self.assertIn("ANOMALY", result.summary())

    def test_vanished_cases_are_reported_not_silent(self):
        # The original tool only tracked additions and changes, so the run in
        # which rows disappeared looked completely healthy.
        self.run_with(codes_html(FULL))
        shrunk = FULL[:96]  # within the completeness ratio, so the fetch passes
        result = self.run_with(codes_html(shrunk))
        self.assertEqual(len(result.removed), 4)
        self.assertTrue(any("消失" in a for a in result.anomalies))
        self.assertEqual({r["type"] for r in self.log_rows()}, {"removed"})


class TestCounts(PipelineCase):
    def test_counts_recorded_per_market(self):
        result = self.run_with(codes_html(FULL))
        self.assertEqual(result.counts, {"sii": 100})

    def test_previous_counts_feed_the_completeness_guard(self):
        self.run_with(codes_html(FULL))
        result = self.run_with(codes_html(FULL))
        self.assertEqual(result.previous_counts, {"sii": 100})


class TestStorageRoundTrip(unittest.TestCase):
    def test_snapshot_survives_a_write_read_cycle(self):
        tmp = Path(tempfile.mkdtemp()) / "snap.csv"
        records = [
            {"market": "sii", "is_cumulative": False, "code": "1101", "name": "台泥",
             "board_date": "115/06/30", "purpose_code": "1", "purpose_text": "轉讓股份予員工",
             "seq": "1", "amount_cap": "", "planned_shares": "10,000,000",
             "price_low": "17.85", "price_high": "41.50", "period_start": "115/07/01",
             "period_end": "115/08/01", "done": "Y", "standard_data": "",
             "bought_shares": "10,000,000", "cancelled_transferred_shares": "",
             "bought_ratio_pct": "100.00", "bought_amount": "418,000,000",
             "avg_price": "41.80", "bought_of_outstanding_pct": "0.11", "note": ""},
        ]
        storage.write_snapshot(records, tmp)
        loaded = storage.read_snapshot(tmp)
        self.assertEqual(loaded[0]["code"], "1101")
        self.assertEqual(loaded[0]["name"], "台泥")
        self.assertIs(loaded[0]["is_cumulative"], False)

    def test_missing_snapshot_reads_as_none(self):
        self.assertIsNone(storage.read_snapshot(Path(tempfile.mkdtemp()) / "nope.csv"))


if __name__ == "__main__":
    unittest.main()
