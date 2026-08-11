import unittest

from twse_buyback import digest
from twse_buyback.pipeline import RunResult


def rec(code, name, market="sii"):
    return {
        "code": code, "name": name, "market": market, "board_date": "115/06/30",
        "purpose_text": "轉讓股份予員工", "planned_shares": "10,000,000",
        "price_low": "17.85", "price_high": "41.50",
        "period_start": "115/07/01", "period_end": "115/08/01",
    }


class TestRender(unittest.TestCase):
    def test_headings_and_counts(self):
        result = RunResult(date="2026-08-11", announcements=[rec("1101", "台泥")])
        out = digest.render(result)
        self.assertIn("## 2026-08-11", out)
        self.assertIn("新公告買回（1）", out)
        self.assertIn("執行進度異動（0）", out)
        self.assertIn("1101 台泥", out)
        self.assertIn("上市", out)

    def test_change_block(self):
        changed = [(rec("2603", "長榮"),
                    [("bought_shares", "", "5,000,000"), ("bought_ratio_pct", "", "25.00")])]
        out = digest.render(RunResult(date="2026-08-11", changed=changed))
        self.assertIn("2603 長榮", out)
        self.assertIn("空→5,000,000", out)

    def test_empty_sections_say_so(self):
        self.assertIn("（無）", digest.render(RunResult(date="2026-08-11")))

    def test_baseline_run_is_labelled(self):
        result = RunResult(date="2026-08-11", baseline=True, counts={"sii": 100, "otc": 50})
        out = digest.render(result)
        self.assertIn("baseline", out)
        self.assertIn("150", out)

    def test_anomalies_lead_the_report(self):
        result = RunResult(date="2026-08-11",
                           announcements=[rec("1101", "台泥")],
                           anomalies=["998 announcements in one run"])
        out = digest.render(result)
        self.assertIn("資料異常", out)
        self.assertLess(out.index("資料異常"), out.index("新公告買回"))

    def test_backfill_and_removals_get_their_own_sections(self):
        result = RunResult(date="2026-08-11",
                           backfill=[rec("3060", "銘異")],
                           removed=[rec("8050", "廣積")])
        out = digest.render(result)
        self.assertIn("回補的舊案", out)
        self.assertIn("3060", out)
        self.assertIn("從 MOPS 表中消失的案", out)
        self.assertIn("8050", out)

    def test_long_lists_are_truncated_with_a_pointer(self):
        result = RunResult(date="2026-08-11",
                           backfill=[rec(str(3000 + i), "X") for i in range(50)])
        out = digest.render(result)
        self.assertIn("另有 30 筆", out)
        self.assertIn("changes_log.csv", out)


class TestRenderLine(unittest.TestCase):
    def test_one_line_summary(self):
        result = RunResult(date="2026-08-11",
                           announcements=[rec("1101", "台泥"), rec("2603", "長榮")])
        line = digest.render_line(result, "18:00")
        self.assertIn("18:00", line)
        self.assertIn("新公告 2 案", line)
        self.assertIn("1101、2603", line)

    def test_more_than_five_codes_elided(self):
        result = RunResult(date="2026-08-11",
                           announcements=[rec(str(1000 + i), "X") for i in range(8)])
        self.assertIn("…", digest.render_line(result, "18:00"))

    def test_anomaly_marked_in_the_line(self):
        result = RunResult(date="2026-08-11", anomalies=["something is wrong"])
        self.assertIn("資料異常", digest.render_line(result, "18:00"))


if __name__ == "__main__":
    unittest.main()
