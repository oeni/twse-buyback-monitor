"""Endpoint constants and runtime settings."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "Settings", "default_output_dir", "MOPS_URL", "MARKET_NAME",
    "PURPOSE_MAP", "COLUMNS", "N_COLUMNS",
]

# --- MOPS endpoint -------------------------------------------------------

MOPS_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t35sc09"

# The form takes `year`/`month`, but they have no observable effect: every
# combination we probed (115/08, 115/07, 114/03, 110/01) returns the identical
# full-history table. We still send the current period so the request looks
# like the one the site's own UI makes.
FORM_BASE = {"encodeURIComponent": 1, "step": 1, "firstin": 1, "off": 1}

MARKET_NAME = {"sii": "上市", "otc": "上櫃"}
DEFAULT_MARKETS = ("sii", "otc")

PURPOSE_MAP = {
    "1": "轉讓股份予員工",
    "2": "股權轉換",
    "3": "維護公司信用及股東權益並辦理註銷",
}

# A data row is exactly 20 <td> cells. Verified against live sii/otc responses:
# 100% of data rows match, so a row with any other cell count is markup, not data.
COLUMNS = [
    "seq", "code", "name", "board_date", "purpose_code", "amount_cap",
    "planned_shares", "price_low", "price_high", "period_start", "period_end",
    "done", "standard_data", "bought_shares", "cancelled_transferred_shares",
    "bought_ratio_pct", "bought_amount", "avg_price", "bought_of_outstanding_pct",
    "note",
]
N_COLUMNS = len(COLUMNS)

# Present in both the sii and otc page titles; absence means we fetched the
# wrong thing or MOPS restructured the page.
PAGE_TITLE_KEYWORD = "買回自己公司股份"

# A complete response ends with this. A response cut off mid-stream does not,
# which is how truncation is caught without needing any historical baseline.
HTML_TERMINATOR = "</html>"

# Fields whose value changing means the buyback is progressing. `period_end`
# is included because buyback windows do get extended and that is worth
# reporting; it is deliberately NOT part of the identity key.
CHANGE_FIELDS = ("done", "bought_shares", "bought_ratio_pct", "bought_amount",
                 "period_end", "note")


def default_output_dir() -> Path:
    """Return ``output/`` in the source checkout, or under the current directory."""
    source_root = Path(__file__).resolve().parent.parent
    if (source_root / "pyproject.toml").is_file():
        return source_root / "output"
    return Path.cwd() / "output"


@dataclass(frozen=True)
class Settings:
    """Everything the pipeline needs to run.

    Args:
        data_dir: Where reports, the snapshot, and logs are written.
        markets: MOPS market codes to fetch. Defaults to listed + OTC.
        timeout: Per-request timeout in seconds.
        max_attempts: How many times to refetch a market before giving up.
            Truncation is transient, so a retry usually resolves it.
        min_completeness_ratio: A fetch is rejected if it returns fewer than
            this fraction of the rows the previous snapshot held for that
            market. Guards against truncation that still ends in ``</html>``.
        surge_threshold: More new cases than this in a single run is treated
            as an anomaly rather than as news.
        backfill_months: New cases whose board-meeting date is older than this
            are recorded as backfill, not reported as new announcements.
        user_agent: Sent with every request.
    """

    data_dir: Path = field(default_factory=default_output_dir)
    markets: tuple = DEFAULT_MARKETS
    timeout: int = 30
    max_attempts: int = 3
    min_completeness_ratio: float = 0.95
    surge_threshold: int = 50
    backfill_months: int = 6
    user_agent: str = "twse-buyback-monitor (+https://github.com/oeni/twse-buyback-monitor)"

    @property
    def snapshot_csv(self) -> Path:
        return self.data_dir / "snapshot_latest.csv"

    @property
    def changes_log_csv(self) -> Path:
        return self.data_dir / "changes_log.csv"

    @property
    def run_log(self) -> Path:
        return self.data_dir / "run.log"

    def report_md(self, run_date: str) -> Path:
        return self.data_dir / f"{run_date}.md"

    def headers(self) -> dict:
        return {"User-Agent": self.user_agent}
