"""Read and write reports, snapshots, and change history."""
from __future__ import annotations

import csv

from . import config

__all__ = ["write_snapshot", "read_snapshot", "write_report", "append_changes_log",
           "count_cases_by_market", "SNAPSHOT_FIELDS", "LOG_FIELDS"]

SNAPSHOT_FIELDS = ["market", "is_cumulative"] + config.COLUMNS + ["purpose_text"]
LOG_FIELDS = ["detect_date", "type", "market", "code", "name", "board_date",
              "purpose_text", "detail"]


def write_snapshot(records, path) -> None:
    """Overwrite the snapshot. Only call this with a verified-complete fetch."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SNAPSHOT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            row = dict(rec)
            row["is_cumulative"] = "True" if rec.get("is_cumulative") else "False"
            writer.writerow(row)


def read_snapshot(path):
    """Load the previous snapshot, or ``None`` when there is not one yet."""
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row["is_cumulative"] = row.get("is_cumulative") == "True"
    return rows


def write_report(markdown: str, path) -> None:
    """Write the report for one date, replacing an earlier run from that date."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown.rstrip() + "\n", encoding="utf-8")


def count_cases_by_market(records) -> dict:
    """Cases per market, excluding cumulative rows.

    This is what the completeness guard compares against, so it must count the
    same thing the fetch layer counts.
    """
    counts = {}
    for rec in records or []:
        if rec.get("is_cumulative"):
            continue
        counts[rec["market"]] = counts.get(rec["market"], 0) + 1
    return counts


def _new_detail(rec) -> str:
    return f"預定{rec['planned_shares']}股 {rec['period_start']}~{rec['period_end']}"


def append_changes_log(result, path) -> None:
    """Append one run's classified changes.

    Backfill and removals get their own row types rather than being folded into
    ``new``, so the log distinguishes market events from data-quality events.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow(LOG_FIELDS)
        for rec in result.announcements:
            writer.writerow([result.date, "new", rec["market"], rec["code"], rec["name"],
                             rec["board_date"], rec["purpose_text"], _new_detail(rec)])
        for rec, deltas in result.changed:
            detail = "; ".join(f"{f}:{old or '-'}->{new or '-'}" for f, old, new in deltas)
            writer.writerow([result.date, "changed", rec["market"], rec["code"], rec["name"],
                             rec["board_date"], rec["purpose_text"], detail])
        for rec in result.backfill:
            writer.writerow([result.date, "backfill", rec["market"], rec["code"], rec["name"],
                             rec["board_date"], rec["purpose_text"], _new_detail(rec)])
        for rec in result.removed:
            writer.writerow([result.date, "removed", rec["market"], rec["code"], rec["name"],
                             rec["board_date"], rec["purpose_text"],
                             "本案從 MOPS 表中消失"])
