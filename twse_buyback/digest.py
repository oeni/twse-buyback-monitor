"""Render a :class:`~twse_buyback.pipeline.RunResult` as Markdown.

Output is in Traditional Chinese because the data is: company names, buyback
purposes and the notes field all arrive that way from MOPS, so translating the
surrounding labels would only produce a half-English report.
"""
from __future__ import annotations

from . import config

__all__ = ["render", "render_line"]


def _market(rec) -> str:
    return config.MARKET_NAME.get(rec["market"], rec["market"])


def _format_new(rec) -> str:
    return (f"- **{rec['code']} {rec['name']}**（{_market(rec)}）"
            f" 決議 {rec['board_date']}｜目的：{rec['purpose_text']}"
            f"｜預定 {rec['planned_shares']} 股 @ {rec['price_low']}–{rec['price_high']}"
            f"｜期間 {rec['period_start']}~{rec['period_end']}")


def _format_changed(rec, deltas) -> str:
    body = "；".join(f"{f} {old or '空'}→{new or '空'}" for f, old, new in deltas)
    return f"- **{rec['code']} {rec['name']}** 決議 {rec['board_date']}｜{body}"


def render(result) -> str:
    """Full Markdown block for one run.

    Anomalies are rendered first and never hidden: a report that silently drops
    the fact that 900 rows went missing is worse than no report.
    """
    lines = [f"## {result.date}", ""]

    if result.anomalies:
        lines.append("> ⚠️ **資料異常** — 本次結果請勿當成市場訊息：")
        lines += [f"> - {a}" for a in result.anomalies]
        lines.append("")

    if result.baseline:
        total = sum(result.counts.values())
        lines.append(f"（baseline 建立：既有 {total} 筆買回案，不視為新公告）")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"### 新公告買回（{len(result.announcements)}）")
    lines += [_format_new(r) for r in result.announcements] or ["（無）"]
    lines.append("")

    lines.append(f"### 執行進度異動（{len(result.changed)}）")
    lines += [_format_changed(r, d) for r, d in result.changed] or ["（無）"]
    lines.append("")

    if result.backfill:
        lines.append(f"### 回補的舊案（{len(result.backfill)}，非新聞）")
        lines += [_format_new(r) for r in result.backfill[:20]]
        if len(result.backfill) > 20:
            lines.append(f"- …另有 {len(result.backfill) - 20} 筆，詳見 changes_log.csv")
        lines.append("")

    if result.removed:
        lines.append(f"### 從 MOPS 表中消失的案（{len(result.removed)}）")
        lines += [f"- {r['market']}/{r['code']} {r['name']} 決議 {r['board_date']}"
                  for r in result.removed[:20]]
        if len(result.removed) > 20:
            lines.append(f"- …另有 {len(result.removed) - 20} 筆")
        lines.append("")

    return "\n".join(lines)


def render_line(result, time_str: str, label: str = "庫藏股監控") -> str:
    """Single-line summary, for a changelog or a chat message."""
    codes = "、".join(r["code"] for r in result.announcements[:5])
    if len(result.announcements) > 5:
        codes += "…"
    suffix = f"（{codes}）" if codes else ""
    warn = " ⚠️資料異常" if result.anomalies else ""
    return (f"- **{time_str} {label}（自動）** — "
            f"新公告 {len(result.announcements)} 案{suffix}、"
            f"執行異動 {len(result.changed)} 案{warn}")
