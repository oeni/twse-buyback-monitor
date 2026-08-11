"""Turn a MOPS t35sc09 HTML response into records.

The endpoint returns HTML, not JSON, and there is no documented schema, so
parsing is positional: a data row is any ``<tr>`` holding exactly 20 ``<td>``
cells whose second cell looks like a stock code. Everything structural about
that assumption is asserted rather than assumed.
"""
from __future__ import annotations

import re

from . import config
from .errors import StructureChanged

__all__ = ["parse", "is_complete_html", "count_cases"]

_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_CODE = re.compile(r"\d{4,6}")

# Rows summarising one company's whole history carry this instead of a sequence
# number. They are kept in the snapshot but never diffed.
CUMULATIVE_MARKER = "累計"


def _cell_text(html: str) -> str:
    return _TAG.sub("", html).replace("&nbsp;", " ").replace("　", " ").strip()


def is_complete_html(html: str) -> bool:
    """Whether the response looks like it arrived in full.

    MOPS sends no ``Content-Length``, so a response cut off mid-stream is
    indistinguishable from a short one at the HTTP layer -- it parses fine and
    yields valid rows, just fewer of them. The one thing a truncated body
    cannot have is the closing tag, so that is the check.
    """
    return html.rstrip().endswith(config.HTML_TERMINATOR)


def parse(html: str, market: str) -> list:
    """Parse one market's response.

    Args:
        html: Decoded response body.
        market: MOPS market code, stored on every record.

    Returns:
        A list of dicts, one per table row, including cumulative rows
        (flagged via ``is_cumulative``).

    Raises:
        StructureChanged: The title keyword is missing, or no row survived
            column-count filtering. Either means the markup changed.
    """
    if config.PAGE_TITLE_KEYWORD not in html:
        raise StructureChanged(
            f"response is missing the title keyword {config.PAGE_TITLE_KEYWORD!r} "
            f"(market={market}); MOPS markup probably changed"
        )

    records = []
    for tr in _TR.findall(html):
        cells = [_cell_text(c) for c in _TD.findall(tr)]
        if len(cells) != config.N_COLUMNS:
            continue
        seq = cells[0]
        is_cumulative = seq == CUMULATIVE_MARKER
        if not (is_cumulative or seq.isdigit()):
            continue
        if not _CODE.fullmatch(cells[1] or ""):
            continue
        rec = {name: cells[i] for i, name in enumerate(config.COLUMNS)}
        rec["market"] = market
        rec["is_cumulative"] = is_cumulative
        rec["purpose_text"] = config.PURPOSE_MAP.get(rec["purpose_code"], rec["purpose_code"])
        records.append(rec)

    if not records:
        raise StructureChanged(
            f"parsed 0 rows for market={market} (no <tr> had {config.N_COLUMNS} cells); "
            f"MOPS markup probably changed"
        )
    return records


def count_cases(records) -> int:
    """Number of individual buyback cases, excluding per-company totals."""
    return sum(1 for r in records if not r.get("is_cumulative"))
