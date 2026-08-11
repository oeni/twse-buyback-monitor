"""Sanity checks applied to a diff before it is reported as news.

The fetch layer stops incomplete data from reaching the snapshot. These are the
second line of defence: even given a clean fetch, they stop implausible diffs
from being announced as if they were real buyback news.
"""
from __future__ import annotations

from datetime import date

__all__ = ["parse_minguo_date", "split_backfill", "check_surge", "check_removals"]


def parse_minguo_date(value):
    """Parse a MOPS date such as ``115/08/11`` into a :class:`datetime.date`.

    MOPS uses the Republic of China calendar, where year 115 is 2026. Returns
    ``None`` for the placeholder ``----`` and for anything unparseable, so
    callers treat unknown dates as "cannot judge" rather than crashing.
    """
    if not value:
        return None
    parts = value.strip().split("/")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(p) for p in parts)
    except ValueError:
        return None
    try:
        return date(year + 1911, month, day)
    except ValueError:
        return None


def split_backfill(new_cases, today, months):
    """Separate genuinely new announcements from historical backfill.

    A company's board cannot have resolved on a buyback years ago and have it
    show up today as news. When old-dated cases appear it means rows that were
    missing from the previous snapshot have come back. Those are recorded, but
    they are not announcements.

    Args:
        new_cases: Records the diff classified as new.
        today: Reference date.
        months: Anything with a board date older than this is backfill.

    Returns:
        ``(announcements, backfill)``. Cases with an unparseable board date are
        treated as announcements so nothing is quietly dropped.
    """
    if months <= 0:
        return list(new_cases), []

    cutoff_ordinal = today.toordinal() - int(months * 30.44)
    announcements, backfill = [], []
    for rec in new_cases:
        board = parse_minguo_date(rec.get("board_date", ""))
        if board is not None and board.toordinal() < cutoff_ordinal:
            backfill.append(rec)
        else:
            announcements.append(rec)
    return announcements, backfill


def check_surge(announcements, threshold):
    """Flag an implausible number of same-day announcements.

    Taiwan sees single-digit buyback filings on a normal day. Dozens at once
    means the diff is measuring a data artefact, not the market.

    Returns:
        A description of the anomaly, or ``None`` when the count is plausible.
    """
    if threshold > 0 and len(announcements) > threshold:
        return (f"{len(announcements)} announcements in one run exceeds the "
                f"plausibility threshold of {threshold}; treating as a data "
                f"artefact rather than news")
    return None


def check_removals(removed, threshold):
    """Flag cases disappearing from the table.

    Buyback cases are historical record: they should never leave. Any removal
    is a data-quality signal, and a large batch means the response was short
    despite passing the fetch guards.

    Returns:
        A description of the anomaly, or ``None`` when nothing was removed.
    """
    if not removed:
        return None
    detail = ", ".join(f"{r['market']}/{r['code']}" for r in removed[:5])
    if len(removed) > 5:
        detail += ", ..."
    severity = "unexpected" if len(removed) <= threshold else "large batch of"
    return (f"{len(removed)} {severity} case(s) vanished from the MOPS table "
            f"({detail}); historical cases should never disappear")
