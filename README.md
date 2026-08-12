# twse-buyback-monitor

Daily Markdown reports for share buyback filings by Taiwan-listed and OTC
companies. Data comes from the Market Observation Post System (MOPS).

[繁體中文](README.zh-TW.md)

## Quick start

```bash
git clone https://github.com/oeni/twse-buyback-monitor.git
cd twse-buyback-monitor
python -m pip install -e .
python -m twse_buyback
```

No arguments are required. Each successful run writes a dated report under
`output/`:

```text
output/
├── 2026-08-12.md
├── snapshot_latest.csv
├── changes_log.csv
└── run.log
```

A day with no new filing or execution update still gets a Markdown report. A
failed fetch does not create or overwrite a report, so missing data is not
mistaken for a quiet day.

The first run creates the comparison baseline. Existing filings are not
reported as new.

## Options

```bash
# Also print the report in the terminal
python -m twse_buyback --print-digest

# Use another output directory
python -m twse_buyback --output-dir C:\buyback-output

# Return a non-zero exit code when the data passes fetching but looks abnormal
python -m twse_buyback --strict

# Show all settings
python -m twse_buyback --help
```

## Output files

| File | Contents |
|---|---|
| `YYYY-MM-DD.md` | New filings and execution updates for the date. |
| `snapshot_latest.csv` | Last complete MOPS table; used as the next baseline. |
| `changes_log.csv` | Append-only history of new, changed, backfilled, and removed cases. |
| `run.log` | Run results, retries, and data warnings. |

CSV files use UTF-8 with BOM for direct use in Excel.

## Data checks

MOPS sometimes returns an HTTP 200 response with an incomplete table. The
monitor rejects a response when:

- the HTML closing tag is missing;
- the row count drops sharply from the last complete snapshot;
- an implausible number of filings appears at once; or
- historical cases disappear from the table.

Rejected responses are retried. If all attempts fail, the previous snapshot is
kept. Older cases that reappear are recorded as backfill instead of current
announcements. See the [August 2026 incident report](docs/incident-2026-08-truncated-responses.md)
for the failure that led to these checks.

The MOPS endpoint used by this project is an internal web endpoint, not a
documented API. A site change can require a parser update.

## Library use

```python
from twse_buyback import Settings, run

result = run(Settings())

for case in result.announcements:
    print(case["code"], case["name"], case["planned_shares"])
```

Pass `Settings(data_dir=...)` to store output elsewhere.

## Development

```bash
python -m unittest discover -s tests -t .
```

Live MOPS checks are opt-in:

```bash
RUN_NETWORK_TESTS=1 python -m unittest tests.test_smoke_network
```

Python 3.9 or newer is required. Runtime dependency: `requests`.

## License

MIT
