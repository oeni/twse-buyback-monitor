"""Fetch MOPS tables and reject incomplete responses.

Completeness is checked by the HTML terminator and by comparison with the last
accepted row count. Rejected responses are retried before the run fails.
"""
from __future__ import annotations

import time
from datetime import datetime

import requests

from . import config, parse
from .errors import FetchError, TruncatedResponse

__all__ = ["fetch_html", "fetch_market"]


def _minguo_period(now=None):
    """Current year/month in the Republic of China calendar MOPS expects."""
    now = now or datetime.now()
    return str(now.year - 1911), f"{now.month:02d}"


def fetch_html(market: str, settings, session=None) -> str:
    """POST the query for one market and return the decoded body.

    Raises:
        FetchError: Non-200 status, transport failure, or a body that is not
            valid UTF-8 (which would mean MOPS changed its encoding).
    """
    year, month = _minguo_period()
    form = dict(config.FORM_BASE, TYPEK=market, year=year, month=month)
    poster = session.post if session is not None else requests.post
    try:
        resp = poster(config.MOPS_URL, data=form, headers=settings.headers(),
                      timeout=settings.timeout)
    except requests.RequestException as exc:
        raise FetchError(f"request to MOPS failed (market={market}): {exc}") from exc

    if resp.status_code != 200:
        raise FetchError(f"MOPS returned HTTP {resp.status_code} (market={market})")
    try:
        return resp.content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FetchError(
            f"MOPS response is not valid UTF-8 (market={market}); encoding may have changed: {exc}"
        ) from exc


def fetch_market(market: str, settings, previous_count=None, session=None, sleep=time.sleep):
    """Fetch and parse one market, retrying while the response looks incomplete.

    Args:
        market: MOPS market code.
        settings: Runtime :class:`~twse_buyback.config.Settings`.
        previous_count: Case count this market had in the last good snapshot,
            or ``None`` on a first run (which disables the comparative check --
            there is no baseline to compare against yet).
        session: Optional ``requests.Session``; injected by tests.
        sleep: Injected by tests to avoid real backoff delays.

    Returns:
        ``(records, reasons)`` where ``reasons`` lists the rejected attempts,
        so a run that only succeeded on retry still says so in the log.

    Raises:
        TruncatedResponse: Every attempt came back incomplete. The caller must
            leave the existing snapshot untouched.
        StructureChanged: Propagated from the parser.
        FetchError: Propagated from the transport layer.
    """
    floor = None
    if previous_count:
        floor = int(previous_count * settings.min_completeness_ratio)

    reasons = []
    for attempt in range(1, settings.max_attempts + 1):
        html = fetch_html(market, settings, session=session)

        if not parse.is_complete_html(html):
            reasons.append(f"attempt {attempt}: body does not end with </html> "
                           f"({len(html)} chars) -- truncated mid-stream")
            sleep(2 * attempt)
            continue

        records = parse.parse(html, market)
        count = parse.count_cases(records)

        if floor is not None and count < floor:
            reasons.append(f"attempt {attempt}: only {count} cases, expected at least "
                           f"{floor} (previous snapshot had {previous_count})")
            sleep(2 * attempt)
            continue

        return records, reasons

    raise TruncatedResponse(
        "MOPS returned an incomplete table on every attempt for market="
        f"{market}; snapshot left unchanged. " + " | ".join(reasons)
    )
