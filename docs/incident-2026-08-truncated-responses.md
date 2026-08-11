# Incident: 998 buyback announcements that never happened

**Date:** 2026-08-11 · **Impact:** two days of false reports over ten weeks of operation · **Detected by:** a human noticing the number looked wrong

This is the failure that this project exists to prevent. It is written up in
full because the interesting part is not the fix — it is that every automated
signal said the system was healthy.

## What was seen

The predecessor tool logged one line per daily run. Ten weeks of them looked
like this:

```
2026-07-30T18:00:00 OK new=5 changed=1
2026-07-31T18:00:00 OK new=2 changed=0
2026-08-03T18:00:01 OK new=2 changed=2
2026-08-04T18:00:01 OK new=0 changed=0
2026-08-05T18:00:01 OK new=524 changed=0     <-- 
2026-08-06T18:00:00 OK new=2 changed=1
2026-08-07T18:00:00 OK new=8 changed=2
2026-08-10T18:00:00 OK new=1 changed=1
2026-08-11T18:00:01 OK new=998 changed=0     <-- 
```

Taiwan does not see 998 buyback filings in a day. It sees between zero and ten.

Every one of those runs is marked `OK`. Nothing failed, nothing raised, no
guard fired, and the exit code was 0 every time — so the scheduled task showed
green throughout.

## Diagnosis

Four checks, in the order they were run.

**1. Are the reported cases real?** Pull the change log for the spike days:

```
2026-08-11,new,sii,3060,銘異,96/11/22,轉讓股份予員工,"預定3,000,000股 96/11/23~96/12/31"
2026-08-11,new,sii,3059,華晶科,114/04/08,轉讓股份予員工,...
```

Republic of China year 96 is 2007. A board meeting from 2007 was being reported
as today's news. So the cases are real records, but their arrival is not a real
event.

**2. Is the source unstable?** The endpoint takes `year` and `month`
parameters, so the first hypothesis was a month-boundary effect. Probing four
different periods killed it:

```
115/08 -> 4270 rows    115/07 -> 4270 rows
114/03 -> 4270 rows    110/01 -> 4270 rows
```

Identical every time. **The period parameters do nothing** — the endpoint always
returns the full history back to 2000. Three consecutive calls also returned
byte-identical row counts, so the response is not randomly varying either.

**3. Is the parser dropping rows?** The parser accepts only rows with exactly
20 `<td>` cells and silently skips the rest, which would be a plausible silent
data-loss path. Counting cells across a live response:

```
cells per row: {0: 478, 1: 10, 2: 1, 20: 4270}
```

Every data row has 20 cells. Nothing was being skipped. Parser cleared.

**4. Where do the spurious cases cluster?** This is what broke it open:

| Day | Cases | Market split |
|---|---|---|
| 2026-08-05 | 524 | 523 OTC, 1 listed |
| 2026-08-11 | 998 | 995 listed, 3 OTC |

Each spike is confined to a single market, spread across ~150–300 stock codes,
and concentrated in **high code numbers** (6xxx, 8xxx) — the tail of a
code-sorted table.

And cases were being re-reported. Stock 8466 was announced as new on 2026-06-10,
then announced again on 2026-08-11 with a byte-identical payload. Across the
whole log, 539 cases had been reported as new more than once.

Rows were not appearing. **They were coming back.**

## Root cause

MOPS intermittently returns a response that is cut off partway through the
table. Nothing at the HTTP layer reveals this:

- status is 200
- there is no `Content-Length` header to check the body against
- the truncated HTML parses fine and yields structurally valid rows

The tool accepted the short response and overwrote its snapshot with it. That
snapshot is the baseline for the next diff, so the missing tail was now missing
from the baseline. When the next complete response arrived, every one of those
rows satisfied the definition of "new": not in the baseline, present in the
fetch.

```
day N     truncated response  ->  tail rows vanish from snapshot   (SILENT)
day N+1   complete response   ->  tail rows are "new"              (998 false positives)
```

The second half of the bug is why day N was silent. The diff computed additions
and modifications, but not deletions — so a failure whose entire symptom is
*rows going missing* was invisible by construction. The one run that most needed
an alarm was the one guaranteed not to raise.

## Fixes

| # | Guard | Catches |
|---|---|---|
| 1 | Response must end with `</html>` | Truncation, with no history needed |
| 2 | Row count ≥ 95% of last good snapshot | Truncation landing on a tag boundary |
| 3 | Refetch up to 3× before failing | Makes transient truncation self-healing |
| 4 | Never write the snapshot on failure | Stops one bad day poisoning every later run |
| 5 | Flag implausible announcement counts | Any surge mechanism, known or not |
| 6 | Classify old-dated cases as backfill | Historical rows returning |
| 7 | Report deletions | Makes silent data loss audible |

Guards 1–4 make the corrupt state unreachable. Guards 5–7 assume 1–4 will
eventually be defeated by something nobody predicted, and make sure that when it
happens, the output says so instead of presenting it as market news.

Regression tests reproduce the incident end to end, including the specific
assertion that a short response must never become the new baseline.

## What generalises

- **A diff that cannot see deletions cannot see data loss.** If your baseline
  can shrink, track removals, even when your source is append-only in theory.
- **`OK` in a log means "the code did not raise", not "the output is right."**
  Plausibility belongs in the guard set alongside correctness.
- **Never let a partial read become a baseline.** Failing and retrying tomorrow
  is nearly free; a poisoned baseline corrupts every run after it.
- **When output is suspicious, ask where it clusters.** The market split and the
  stock-code distribution identified truncation in one query, after three
  reasonable hypotheses had already been eliminated.
