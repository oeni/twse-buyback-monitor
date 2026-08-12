"""Render a monitoring result as Traditional Chinese Markdown."""
from __future__ import annotations

from . import config

__all__ = ["render", "render_line"]

FIELD_LABELS = {
    "done": "執行狀態",
    "bought_shares": "已買回股數",
    "bought_ratio_pct": "買回比例",
    "bought_amount": "已買回金額",
    "period_end": "買回期限",
    "note": "備註",
}


def _market(rec) -> str:
    return config.MARKET_NAME.get(rec["market"], rec["market"])


def _format_new(rec) -> str:
    return (f"- **{rec['code']} {rec['name']}**（{_market(rec)}）"
            f"｜決議 {rec['board_date']}｜預定 {rec['planned_shares']} 股"
            f"｜價格 {rec['price_low']}–{rec['price_high']}"
            f"｜期間 {rec['period_start']}～{rec['period_end']}"
            f"｜目的 {rec['purpose_text']}")


def _format_changed(rec, deltas) -> str:
    body = "；".join(
        f"{FIELD_LABELS.get(field, field)}：{old or '空白'} → {new or '空白'}"
        for field, old, new in deltas
    )
    return f"- **{rec['code']} {rec['name']}**｜決議 {rec['board_date']}｜{body}"


def render(result) -> str:
    """Return the daily Markdown report."""
    lines = [f"# {result.date} 庫藏股", ""]

    if result.anomalies:
        lines.append("## 資料異常")
        lines.append("")
        lines.append("本次結果需要人工確認：")
        lines += [f"- {a}" for a in result.anomalies]
        lines.append("")

    if result.baseline:
        total = sum(result.counts.values())
        lines.append(f"首次執行已建立基準資料，共 {total} 筆；既有案件不列為今日新公告。")
        lines.append("")
        return "\n".join(lines)

    if not (result.announcements or result.changed or result.backfill or result.removed):
        lines.append("今日無新增公告或執行進度異動。")
        lines.append("")
        return "\n".join(lines)

    if result.announcements:
        lines.append(f"## 新公告（{len(result.announcements)}）")
        lines.append("")
        lines += [_format_new(r) for r in result.announcements]
        lines.append("")

    if result.changed:
        lines.append(f"## 執行進度（{len(result.changed)}）")
        lines.append("")
        lines += [_format_changed(r, d) for r, d in result.changed]
        lines.append("")

    if result.backfill:
        lines.append(f"## 回補舊案（{len(result.backfill)}，非今日公告）")
        lines.append("")
        lines += [_format_new(r) for r in result.backfill[:20]]
        if len(result.backfill) > 20:
            lines.append(f"- …另有 {len(result.backfill) - 20} 筆，詳見 changes_log.csv")
        lines.append("")

    if result.removed:
        lines.append(f"## 從 MOPS 資料中消失（{len(result.removed)}）")
        lines.append("")
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
    warn = "（資料異常）" if result.anomalies else ""
    return (f"- **{time_str} {label}（自動）** — "
            f"新公告 {len(result.announcements)} 案{suffix}、"
            f"執行異動 {len(result.changed)} 案{warn}")
