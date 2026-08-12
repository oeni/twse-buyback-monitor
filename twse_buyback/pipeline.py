"""Fetch, validate, diff, and persist one monitoring run."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from . import digest
from . import diff as diff_mod
from . import fetch as fetch_mod
from . import guard, storage

__all__ = ["RunResult", "run"]


@dataclass
class RunResult:
    """What one run found.

    Attributes:
        date: Run date as ``YYYY-MM-DD``.
        baseline: True when this run only established the first snapshot. No
            diff is meaningful yet, so every list is empty.
        announcements: Newly filed buyback cases -- the actual news.
        backfill: Cases that appeared but are too old to be news; almost always
            rows returning after having gone missing.
        changed: ``(record, [(field, old, new), ...])`` for cases that moved.
        removed: Cases that vanished from the table. Should always be empty.
        counts: Cases per market in this fetch.
        previous_counts: Cases per market in the previous snapshot.
        anomalies: Human-readable descriptions of anything suspicious. A
            non-empty list means treat the other fields with suspicion.
        fetch_warnings: Attempts that were rejected before one succeeded.
    """

    date: str
    baseline: bool = False
    announcements: list = field(default_factory=list)
    backfill: list = field(default_factory=list)
    changed: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    previous_counts: dict = field(default_factory=dict)
    anomalies: list = field(default_factory=list)
    fetch_warnings: list = field(default_factory=list)

    @property
    def has_updates(self) -> bool:
        """Whether anything worth telling a human about happened."""
        return bool(self.announcements or self.changed)

    def summary(self) -> str:
        """One-line summary for a log."""
        if self.baseline:
            total = sum(self.counts.values())
            return f"baseline established: {total} cases"
        parts = [f"new={len(self.announcements)}", f"changed={len(self.changed)}"]
        if self.backfill:
            parts.append(f"backfill={len(self.backfill)}")
        if self.removed:
            parts.append(f"removed={len(self.removed)}")
        if self.fetch_warnings:
            parts.append(f"retries={len(self.fetch_warnings)}")
        if self.anomalies:
            parts.append(f"ANOMALY={len(self.anomalies)}")
        return " ".join(parts)


def run(settings, today=None, session=None, sleep=None) -> RunResult:
    """Fetch every market, diff against the last snapshot, and persist.

    The snapshot is written only after every market has been fetched and
    verified. A failure partway through leaves the previous baseline intact,
    which is what makes a bad day recoverable by simply running again.

    Args:
        settings: Runtime :class:`~twse_buyback.config.Settings`.
        today: Reference date, injected by tests.
        session: Optional ``requests.Session``, injected by tests.
        sleep: Retry backoff function, injected by tests.

    Returns:
        The :class:`RunResult`.

    Raises:
        TruncatedResponse: MOPS never returned a complete table.
        StructureChanged: MOPS changed its markup.
        FetchError: The request itself failed.
    """
    today = today or date.today()
    result = RunResult(date=today.strftime("%Y-%m-%d"))

    previous = storage.read_snapshot(settings.snapshot_csv)
    result.previous_counts = storage.count_cases_by_market(previous)

    records = []
    for market in settings.markets:
        extra = {"sleep": sleep} if sleep is not None else {}
        market_records, warnings = fetch_mod.fetch_market(
            market, settings,
            previous_count=result.previous_counts.get(market),
            session=session,
            **extra,
        )
        records.extend(market_records)
        result.fetch_warnings.extend(f"[{market}] {w}" for w in warnings)

    result.counts = storage.count_cases_by_market(records)

    if previous is None:
        result.baseline = True
        storage.write_snapshot(records, settings.snapshot_csv)
        storage.write_report(digest.render(result), settings.report_md(result.date))
        return result

    new, changed, removed = diff_mod.diff(previous, records)
    announcements, backfill = guard.split_backfill(new, today, settings.backfill_months)

    result.announcements = announcements
    result.backfill = backfill
    result.changed = changed
    result.removed = removed

    for check in (guard.check_surge(announcements, settings.surge_threshold),
                  guard.check_removals(removed, settings.surge_threshold)):
        if check:
            result.anomalies.append(check)
    if backfill:
        result.anomalies.append(
            f"有 {len(backfill)} 筆超過 {settings.backfill_months} 個月的舊案重新出現；"
            "已列為回補，不視為今日公告。"
        )

    # Written after the diff so a crash mid-diff cannot leave the baseline
    # advanced past changes that were never recorded.
    storage.write_snapshot(records, settings.snapshot_csv)
    storage.append_changes_log(result, settings.changes_log_csv)
    storage.write_report(digest.render(result), settings.report_md(result.date))
    return result


def log_line(text: str, path) -> None:
    """Append a timestamped line to the run log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now().isoformat(timespec='seconds')} {text}\n")
