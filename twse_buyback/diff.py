"""Compare snapshots and report additions, changes, and removals."""
from __future__ import annotations

from . import config
from .errors import BuybackError

__all__ = ["diff", "index_by_key", "case_key"]


def case_key(rec) -> tuple:
    """Identity of a buyback case.

    Deliberately built only from fields that are fixed when the case is filed:
    market, stock code, board-meeting date, purpose, and the start of the
    buyback window. Progress fields (shares bought, completion flag) and the
    window's *end* date are all mutable, so including any of them would make a
    routine update look like a brand-new case.
    """
    return (rec["market"], rec["code"], rec["board_date"],
            rec["purpose_code"], rec["period_start"])


def index_by_key(records) -> dict:
    """Index individual cases by key, skipping per-company cumulative rows.

    Raises:
        BuybackError: Two rows share a key. That should be impossible, so it
            means the parser mis-read something; overwriting silently would
            hide it.
    """
    out = {}
    for rec in records:
        if rec.get("is_cumulative"):
            continue
        key = case_key(rec)
        if key in out:
            raise BuybackError(f"duplicate buyback case key {key}; parser is misreading rows")
        out[key] = rec
    return out


def diff(previous, current):
    """Diff two record lists.

    Args:
        previous: Records from the last snapshot, or ``None`` on a first run.
        current: Records just fetched.

    Returns:
        ``(new, changed, removed)``. ``changed`` items are
        ``(record, [(field, old, new), ...])``. On a first run everything is
        empty: an initial snapshot is a baseline, not an announcement.
    """
    current_index = index_by_key(current)
    if previous is None:
        return [], [], []

    previous_index = index_by_key(previous)

    new, changed = [], []
    for key, rec in current_index.items():
        old = previous_index.get(key)
        if old is None:
            new.append(rec)
            continue
        deltas = [
            (f, old.get(f, ""), rec.get(f, ""))
            for f in config.CHANGE_FIELDS
            if old.get(f, "") != rec.get(f, "")
        ]
        if deltas:
            changed.append((rec, deltas))

    removed = [rec for key, rec in previous_index.items() if key not in current_index]
    return new, changed, removed
