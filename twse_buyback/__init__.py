"""Track Taiwan-listed share buyback filings from MOPS.

    from pathlib import Path
    from twse_buyback import Settings, run

    result = run(Settings(data_dir=Path("data")))
    for case in result.announcements:
        print(case["code"], case["name"], case["planned_shares"])

``run()`` writes two CSVs and returns what changed. It does not decide what to
do about it -- that is the caller's job.
"""
from .config import Settings
from .digest import render, render_line
from .errors import (BuybackError, FetchError, StructureChanged,
                     TruncatedResponse)
from .pipeline import RunResult, run

__version__ = "1.0.0"

__all__ = [
    "Settings", "RunResult", "run",
    "render", "render_line",
    "BuybackError", "FetchError", "StructureChanged", "TruncatedResponse",
    "__version__",
]
