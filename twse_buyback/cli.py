"""Command-line entry point."""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from .config import DEFAULT_MARKETS, Settings, default_output_dir
from .digest import render
from .pipeline import log_line, run

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="twse-buyback-monitor",
        description="Track Taiwan-listed share buyback filings from MOPS and "
                    "report new cases and execution progress.",
    )
    parser.add_argument("--output-dir", "--data-dir", dest="data_dir", type=Path,
                        default=default_output_dir(),
                        help="directory for daily Markdown, snapshot, and logs "
                             "(default: repository output/)")
    parser.add_argument("--markets", nargs="+", default=list(DEFAULT_MARKETS),
                        metavar="CODE", help="MOPS market codes (default: sii otc)")
    parser.add_argument("--timeout", type=int, default=30, help="per-request timeout, seconds")
    parser.add_argument("--max-attempts", type=int, default=3,
                        help="refetch attempts before declaring the response truncated")
    parser.add_argument("--min-completeness", type=float, default=0.95, metavar="RATIO",
                        help="reject a fetch returning less than this fraction of the "
                             "previous snapshot's row count")
    parser.add_argument("--surge-threshold", type=int, default=50,
                        help="more new cases than this in one run is flagged as an anomaly")
    parser.add_argument("--backfill-months", type=int, default=6,
                        help="new cases with a board date older than this are recorded as "
                             "backfill rather than announced")
    parser.add_argument("--print-digest", action="store_true",
                        help="print the Markdown digest to stdout")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero when the run completes but finds anomalies")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings(
        data_dir=args.data_dir,
        markets=tuple(args.markets),
        timeout=args.timeout,
        max_attempts=args.max_attempts,
        min_completeness_ratio=args.min_completeness,
        surge_threshold=args.surge_threshold,
        backfill_months=args.backfill_months,
    )

    try:
        result = run(settings)
    except Exception as exc:
        log_line(f"ERROR {exc.__class__.__name__}: {exc}", settings.run_log)
        log_line(traceback.format_exc(), settings.run_log)
        print(f"ERROR {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1

    log_line(f"OK {result.summary()}", settings.run_log)
    for warning in result.fetch_warnings:
        log_line(f"   retry {warning}", settings.run_log)
    for anomaly in result.anomalies:
        log_line(f"   anomaly {anomaly}", settings.run_log)

    print(result.summary())
    print(f"report={settings.report_md(result.date)}")
    for anomaly in result.anomalies:
        print(f"  anomaly: {anomaly}", file=sys.stderr)
    if args.print_digest:
        print()
        print(render(result))

    return 1 if (args.strict and result.anomalies) else 0
