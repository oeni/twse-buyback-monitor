# 2026-08 incident: false announcements after truncated MOPS responses

- Date identified: 2026-08-11
- Impact: two false reports during ten weeks of operation
- Detection: manual review of an implausible announcement count

## Summary

The earlier monitor accepted incomplete MOPS responses as valid snapshots. On
the next complete fetch, every row missing from the snapshot appeared to be a
new filing. This produced false reports of 524 and 998 announcements.

```text
2026-08-05T18:00:01 OK new=524 changed=0
2026-08-11T18:00:01 OK new=998 changed=0
```

One reported record had a board date in Republic of China year 96 (2007), so
the records existed but were not current announcements.

```text
2026-08-11,new,sii,3060,銘異,96/11/22,轉讓股份予員工,"預定3,000,000股 96/11/23~96/12/31"
```

## Investigation

### Query parameters

The endpoint accepts `year` and `month`, but different periods returned the
same full-history table:

```text
115/08 -> 4270 rows    115/07 -> 4270 rows
114/03 -> 4270 rows    110/01 -> 4270 rows
```

The period fields therefore did not explain the spikes.

### Parser

The parser accepts data rows with exactly 20 `<td>` cells. A live response had
the following distribution:

```text
cells per row: {0: 478, 1: 10, 2: 1, 20: 4270}
```

All data rows matched the expected width, so the parser was not dropping valid
rows.

### Distribution of false announcements

| Date | Cases | Market distribution |
|---|---:|---|
| 2026-08-05 | 524 | 523 OTC, 1 listed |
| 2026-08-11 | 998 | 995 listed, 3 OTC |

The affected rows were concentrated at high stock codes near the end of a
code-sorted table. Some cases were reported more than once with identical
payloads. These observations were consistent with tail rows disappearing and
later returning.

## Root cause

MOPS intermittently returned a response cut off partway through the table:

- HTTP status remained 200;
- no `Content-Length` header was present;
- complete rows before the cutoff remained valid HTML fragments.

The monitor wrote the shorter result over its snapshot. Its diff tracked
additions and modifications but not removals, so the loss was silent. When a
complete table returned, the missing tail met the existing definition of a new
case.

```text
day N     incomplete response -> tail rows missing from snapshot
day N+1   complete response   -> returned rows classified as new
```

## Corrective actions

| Check | Purpose |
|---|---|
| Require the response to end with `</html>` | Detect mid-stream truncation without a baseline. |
| Require at least 95% of the previous row count | Detect a short response with valid closing tags. |
| Retry up to three times | Recover from transient truncation. |
| Keep the previous snapshot after any fetch failure | Prevent incomplete data from becoming the baseline. |
| Flag implausible announcement counts | Surface unexpected surge mechanisms. |
| Classify older cases as backfill | Keep recovered history out of current announcements. |
| Track removals | Make future data loss visible. |

Regression tests cover incomplete HTML, row-count collapse, snapshot
preservation, recovery on the next run, old-case backfill, and removals.
