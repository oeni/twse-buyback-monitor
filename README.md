# twse-buyback-monitor

Track share buyback filings by Taiwan-listed companies, and tell the difference
between real news and a bad day at the data source.

Taiwanese listed and OTC companies must file buyback announcements with MOPS
(公開資訊觀測站). This tool fetches that table daily, diffs it against the last
run, and reports two things: **newly filed buybacks** and **execution progress**
on the ones already running.

[繁體中文說明](README.zh-TW.md)

```console
$ python -m twse_buyback --data-dir ./data
new=3 changed=2
```

- No API key, no account, no scraping framework.
- One third-party dependency: `requests`.
- Deterministic. No LLM anywhere in the pipeline.

## Install

```bash
git clone https://github.com/oeni/twse-buyback-monitor
cd twse-buyback-monitor
pip install -e .
```

Python 3.9+.

## Use

```bash
# first run establishes a baseline and announces nothing
python -m twse_buyback --data-dir ./data

# print the Markdown report as well
python -m twse_buyback --data-dir ./data --print-digest

# make a scheduled job fail when the data looks wrong, not just when the fetch does
python -m twse_buyback --data-dir ./data --strict
```

Three files appear in `--data-dir`:

| File | What it is |
|---|---|
| `snapshot_latest.csv` | The full table as last fetched. Overwritten each run; the baseline every diff is measured against. |
| `changes_log.csv` | Append-only history. Row types: `new`, `changed`, `backfill`, `removed`. |
| `run.log` | One line per run, plus any retries and anomalies. |

As a library:

```python
from pathlib import Path
from twse_buyback import Settings, run, render

result = run(Settings(data_dir=Path("data")))

for case in result.announcements:
    print(case["code"], case["name"], case["planned_shares"])

if result.anomalies:
    print("do not trust this run:", result.anomalies)

print(render(result))   # Markdown report
```

`run()` writes the CSVs and returns what changed. It does not decide what to do
about it — post it to Slack, write it into a note, trigger an alert, whatever
you need.

## The interesting part

The naive version of this tool is thirty lines: fetch, parse, diff against
yesterday, report the difference. That version is wrong, and it is wrong in a
way that looks like it is working.

MOPS intermittently returns a response that is **cut off partway through the
table**. There is no `Content-Length` header, the HTTP status is 200, and the
partial body parses perfectly — it just contains fewer rows, always missing the
tail. Nothing in the request or the response says anything is wrong.

So the naive tool writes that partial table over its snapshot. The next day the
full response comes back, and every row that had gone missing is now absent
from the baseline and present in the fetch — which is the exact definition of
"new". The tool then reports hundreds of brand-new buyback announcements,
including ones whose board meetings happened in 2007.

This is not hypothetical. It is what the predecessor of this tool did:

```
2026-08-05T18:00:01 OK new=524 changed=0
2026-08-11T18:00:01 OK new=998 changed=0
```

```
2026-08-11,new,sii,3060,銘異,96/11/22,轉讓股份予員工,"planned 3,000,000 shares 96/11/23~96/12/31"
```

Note the `OK`. Every run passed. The day rows *disappeared* was completely
silent, because the tool only tracked additions and changes — a diff that
cannot see deletions cannot see data loss.

### What this tool does about it

Four independent layers, ordered so the cheapest catches the most:

**1. Structural check.** A complete response ends with `</html>`; one cut off
mid-stream cannot. This catches truncation without needing any history, so it
works on the very first run.

**2. Completeness check.** The row count must not collapse relative to the last
good snapshot (default: at least 95% of it). This catches truncation that
happens to land on a tag boundary.

Failing either triggers a refetch (default: 3 attempts). Truncation is
transient, so this usually resolves it. If every attempt fails, the run raises
and **the snapshot is left untouched** — a bad response can never become the
baseline, so tomorrow's run recovers on its own.

**3. Plausibility check.** Taiwan sees single-digit buyback filings on a normal
day. Dozens at once is flagged as an anomaly rather than reported as news.

**4. Recency check.** A board meeting from 2007 cannot be today's news. Cases
older than the cutoff (default: 6 months) are recorded as `backfill`, not
announced.

And deletions are tracked. Buyback cases are historical record; they should
never leave the table. If one does, you hear about it.

The design principle throughout: **never write a partial result, and never let
a data-quality problem present itself as a market event.** Every failure raises
explicitly, and every anomaly is stated in the report rather than smoothed over.

## Data source notes

Things learned the hard way, all verified against the live endpoint:

- The endpoint is `POST https://mopsov.twse.com.tw/mops/web/ajax_t35sc09`. It is
  the site's own internal AJAX call, not a documented API. It can change without
  warning, and when it does this tool raises rather than guessing.
- **The `year` and `month` form parameters have no effect.** Every combination
  probed (115/08, 115/07, 114/03, 110/01) returns the identical full-history
  table, back to 2000. There is a live test asserting this, so if MOPS ever
  implements the filter, you find out from a test failure.
- A data row is exactly 20 `<td>` cells. 100% of live data rows match, so a row
  with any other cell count is markup, not data.
- Rows marked `累計` are per-company totals. They are kept in the snapshot and
  excluded from diffing.
- Dates use the Republic of China calendar: year 115 is 2026.

## Development

```bash
python -m unittest discover -s tests -t .              # offline, ~0.5s
RUN_NETWORK_TESTS=1 python -m unittest tests.test_smoke_network   # live
```

The network tests assert the assumptions the parser is built on, so when MOPS
changes something they tell you which assumption broke.

## License

MIT
