"""Track Taiwan-listed share buyback filings from MOPS.

    from twse_buyback import Settings, run

    result = run(Settings())
    for case in result.announcements:
        print(case["code"], case["name"], case["planned_shares"])

``run()`` writes a dated Markdown report, the current snapshot, and a change
log, then returns what changed.
"""
from .config import Settings
from .digest import render, render_line
from .errors import (BuybackError, FetchError, StructureChanged,
                     TruncatedResponse)
from .pipeline import RunResult, run

__version__ = "1.1.0"

__all__ = [
    "Settings", "RunResult", "run",
    "render", "render_line",
    "BuybackError", "FetchError", "StructureChanged", "TruncatedResponse",
    "__version__",
]
