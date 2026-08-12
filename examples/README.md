# Sample output / 範例輸出

Five consecutive monitoring days, produced by the real pipeline from real MOPS
filings (fetched 2026-08-11, all columns verbatim). Regenerate with
`python examples/regenerate.py`; CI fails if these files drift from what the
code actually produces.

以下是連續五個監控日的完整產出，由真實管線處理真實 MOPS 申報資料
（2026-08-11 抓取，欄位原樣）生成。執行 `python examples/regenerate.py`
可重新產生；CI 會確保這些檔案與程式實際輸出一致。

| Day | File | What it shows |
|---|---|---|
| 1 | [`2026-08-10.md`](2026-08-10.md) | First run: a baseline is recorded, nothing is announced. 首次執行只建基準。 |
| 2 | [`2026-08-11.md`](2026-08-11.md) | A busy day: four new filings, two execution updates. 四筆新公告、兩筆執行進度。 |
| 3 | [`2026-08-12.md`](2026-08-12.md) | A quiet day. 無異動的一天。 |
| 4 | [`2026-08-13.md`](2026-08-13.md) | A 2007 case reappears → recorded as backfill and flagged, not announced as news. 舊案回補，標記異常。 |
| 5 | [`2026-08-14.md`](2026-08-14.md) | A case vanishes from the table → reported and flagged. 案件消失，回報並標記。 |

Plus the two files that accumulate across runs:

- [`changes_log.csv`](changes_log.csv) — the append-only history; all four row
  types (`new` / `changed` / `backfill` / `removed`) appear once.
- [`run.log`](run.log) — one line per run, plus anomaly lines.

Notes:

- Dates inside reports use the Republic of China calendar (民國): year 115 is
  2026, so `115/08/10` is 2026-08-10. The 3060 backfill case, `96/11/22`, is
  from November 2007 — which is why it must not be reported as today's news.
- A real MOPS table holds ~5,700 cases per run; the sample uses ten so the
  diffs stay readable.
- Day 5 relaxes `min_completeness_ratio` for demonstration: with only seven
  OTC rows, one vanishing row is a 14% drop, and the default settings would
  reject the fetch before the diff ever saw it. That rejection is the correct
  production behaviour; the relaxed run exists to show what the last line of
  defence looks like when the earlier guards are bypassed.
