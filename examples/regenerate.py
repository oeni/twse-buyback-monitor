"""Rebuild every file in ``examples/``.

    python examples/regenerate.py

The sample reports are not written by hand. This script replays five
consecutive monitoring days through the real pipeline -- the same fetch
validation, diffing, classification, and rendering that a production run
uses -- against canned MOPS responses, then copies the results here. CI
re-runs it and fails if the committed examples ever drift from what the
code actually produces.

The buyback cases inside are real filings, taken from the live MOPS table
on 2026-08-11, with all twenty columns intact. The five-day storyline is
compressed for demonstration:

======================  =====================================================
2026-08-10              First run. A baseline is recorded; nothing announced.
2026-08-11              Four new filings, two execution updates.
2026-08-12              A quiet day.
2026-08-13              A 2007 case reappears -> backfill, flagged.
2026-08-14              A case vanishes -> removed, flagged.
======================  =====================================================

A real table holds ~5,700 cases per run; the sample uses ten so the diffs
stay readable. Day five relaxes ``min_completeness_ratio`` because with only
seven OTC rows, one disappearing row would otherwise be rejected at the fetch
layer before the diff could report it -- which is exactly what the default
settings are for.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXAMPLES_DIR.parent))

from twse_buyback import pipeline  # noqa: E402
from twse_buyback.config import COLUMNS, Settings  # noqa: E402

# --- Real MOPS filings (fetched 2026-08-11, all columns verbatim) ---------

def case(market, seq, code, name, board, purpose, cap, planned, low, high,
         start, end, done="N", bought="", cancelled="", ratio="", amount="",
         avg="", outstanding="", note=""):
    return {
        "market": market, "seq": seq, "code": code, "name": name,
        "board_date": board, "purpose_code": purpose, "amount_cap": cap,
        "planned_shares": planned, "price_low": low, "price_high": high,
        "period_start": start, "period_end": end, "done": done,
        "standard_data": "", "bought_shares": bought,
        "cancelled_transferred_shares": cancelled, "bought_ratio_pct": ratio,
        "bought_amount": amount, "avg_price": avg,
        "bought_of_outstanding_pct": outstanding, "note": note,
    }


NOTE_8466 = "為維護股東權益及兼顧市場機制，視股價變化及成交量狀況採行分批買回策略，故未執行完畢。"
NOTE_8927 = "為維護整體股東權益及兼顧市場機制，視股價變化及成交狀況執行 買回，故未全數執行完畢。"

# In progress when the story begins; completed on day two.
GIANT_BEFORE = case("sii", "668", "9921", "巨大", "115/05/08", "1",
                    "28,914,080,517", "4,000,000", "60.00", "100.00",
                    "115/05/08", "115/07/07")
GIANT_AFTER = dict(GIANT_BEFORE, done="Y", bought_shares="4,000,000",
                   bought_ratio_pct="100.00", bought_amount="287,003,263",
                   avg_price="71.75", bought_of_outstanding_pct="1.02")

MAGI_BEFORE = case("sii", "652", "8466", "美吉吉-KY", "115/06/10", "1",
                   "2,245,146,348", "1,000,000", "10.89", "24.23",
                   "115/06/10", "115/08/09")
MAGI_AFTER = dict(MAGI_BEFORE, done="Y", bought_shares="510,000",
                  bought_ratio_pct="51.00", bought_amount="8,683,148",
                  avg_price="17.03", bought_of_outstanding_pct="0.64",
                  note=NOTE_8466)

# Stable throughout: earlier filings already in their final state.
STEADY_SII = [
    case("sii", "560", "6239", "力成", "115/08/07", "1", "47,961,609,111",
         "10,000,000", "250.00", "350.00", "115/08/10", "115/09/30"),
    case("sii", "624", "7823", "奧義賽博-KY創", "115/08/04", "1", "199,518,938",
         "400,000", "57.00", "122.00", "115/08/05", "115/10/02"),
    case("sii", "684", "9946", "三發地產", "115/05/12", "1", "2,925,727,749",
         "3,000,000", "14.00", "25.00", "115/05/12", "115/07/11", done="Y",
         bought="3,000,000", ratio="100.00", amount="53,718,851", avg="17.91",
         outstanding="0.92"),
]
STEADY_OTC = [
    case("otc", "445", "7820", "立盈", "115/08/06", "1", "864,737,742",
         "300,000", "95.00", "150.00", "115/08/07", "115/10/06"),
    case("otc", "446", "7842", "天能綠電", "115/08/06", "1", "266,817,726",
         "825,000", "80.00", "135.00", "115/08/06", "115/10/05"),
    case("otc", "516", "8937", "合騏*", "115/02/06", "1", "1,575,175,527",
         "1,000,000", "110.00", "180.00", "115/02/06", "115/04/05", done="Y",
         bought="1,000,000", ratio="100.00", amount="148,693,724",
         avg="148.69", outstanding="0.93"),
    case("otc", "521", "9951", "皇田", "115/05/07", "3", "2,939,466,223",
         "1,000,000", "45.00", "65.00", "115/05/08", "115/07/06", done="Y",
         bought="1,000,000", ratio="100.00", amount="53,255,867", avg="53.26",
         outstanding="1.36"),
]

# Vanishes on day five.
PEIKEE = case("otc", "510", "8927", "北基", "115/03/06", "3", "432,089,887",
              "7,000,000", "17.15", "37.40", "115/03/06", "115/05/05", done="Y",
              bought="4,474,000", cancelled="4,474,000", ratio="63.91",
              amount="102,803,459", avg="22.98", outstanding="1.05",
              note=NOTE_8927)

# Filed on 2026-08-10/11; first seen on day two.
NEW_SII = [
    case("sii", "510", "5292", "華懋", "115/08/10", "1", "1,441,332,757",
         "3,000,000", "121.00", "275.00", "115/08/11", "115/10/08"),
    case("sii", "599", "6771", "平和環保-創", "115/08/11", "1", "497,324,658",
         "1,000,000", "26.60", "58.01", "115/08/11", "115/10/08"),
]
NEW_OTC = [
    case("otc", "435", "6945", "圓祥生技", "115/08/11", "1", "1,143,569,155",
         "2,000,000", "76.00", "150.00", "115/08/12", "115/10/11"),
    case("otc", "499", "8436", "大江", "115/08/10", "1", "4,684,475,472",
         "500,000", "88.00", "173.00", "115/08/11", "115/10/09"),
]

# A completed filing from November 2007. When it reappears after having gone
# missing, the recency guard must file it as backfill, not as today's news.
OLD_3060 = case("sii", "401", "3060", "銘異", "96/11/22", "1", "1,007,292,209",
                "3,000,000", "35.00", "55.00", "96/11/23", "96/12/31", done="Y",
                bought="3,000,000", cancelled="3,000,000", ratio="100.00",
                amount="124,266,510", avg="41.42", outstanding="2.50")


# --- Canned MOPS responses ------------------------------------------------

def mops_html(records):
    """A response body shaped like the real t35sc09 page."""
    rows = "".join(
        "<tr>" + "".join(f"<td>{r[col]}</td>" for col in COLUMNS) + "</tr>\n"
        for r in records
    )
    return (
        "<html><head><title>公開資訊觀測站</title></head><body>\n"
        "<table><tr><td>上市櫃公司買回自己公司股份彙總統計表</td></tr></table>\n"
        f"<table>\n{rows}</table>\n</body></html>\n"
    )


class CannedSession:
    """Returns one prepared body per request, in order."""

    def __init__(self, bodies):
        self.bodies = list(bodies)

    def post(self, url, data=None, headers=None, timeout=None):
        body = self.bodies.pop(0)
        return type("Response", (), {"status_code": 200,
                                     "content": body.encode("utf-8")})()


# --- The five-day storyline -----------------------------------------------

def day(settings, when, sii, otc):
    session = CannedSession([mops_html(sii), mops_html(otc)])
    result = pipeline.run(settings, today=when, session=session)
    line = f"{when}T18:00:02 OK {result.summary()}"
    return [line] + [f"{when}T18:00:02    anomaly {a}" for a in result.anomalies]


def main():
    tmp = Path(tempfile.mkdtemp())
    settings = Settings(data_dir=tmp)

    sii_day1 = STEADY_SII + [MAGI_BEFORE, GIANT_BEFORE]
    otc_day1 = STEADY_OTC + [PEIKEE]
    sii_day2 = STEADY_SII + [MAGI_AFTER, GIANT_AFTER] + NEW_SII
    otc_day2 = STEADY_OTC + [PEIKEE] + NEW_OTC
    sii_day4 = sii_day2 + [OLD_3060]
    otc_day5 = STEADY_OTC + NEW_OTC          # 北基 is gone

    log = []
    log += day(settings, date(2026, 8, 10), sii_day1, otc_day1)
    log += day(settings, date(2026, 8, 11), sii_day2, otc_day2)
    log += day(settings, date(2026, 8, 12), sii_day2, otc_day2)
    log += day(settings, date(2026, 8, 13), sii_day4, otc_day2)
    # Demo-only: with seven OTC rows, one vanishing row is a 14% drop and the
    # completeness guard would reject the fetch outright. Relaxing it lets the
    # removal reach the diff so the report can show how removals are flagged.
    relaxed = Settings(data_dir=tmp, min_completeness_ratio=0.5)
    log += day(relaxed, date(2026, 8, 14), sii_day4, otc_day5)

    for name in ("2026-08-10.md", "2026-08-11.md", "2026-08-12.md",
                 "2026-08-13.md", "2026-08-14.md", "changes_log.csv"):
        shutil.copy(tmp / name, EXAMPLES_DIR / name)
    (EXAMPLES_DIR / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")

    shutil.rmtree(tmp)
    print(f"examples rebuilt in {EXAMPLES_DIR}")


if __name__ == "__main__":
    main()
