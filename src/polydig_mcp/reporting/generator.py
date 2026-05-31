"""Turn Reviewer verdicts into a daily markdown research report.

Sections (design spec §6.6):
  - 今日強訊號 (strong)
  - 觀察清單 (watchlist)
  - 駁回但有趣 (reject, FYI)
  - 漏抓案例 (price safety-net backfill, if any)
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


def _tree_md(tree: dict[str, Any]) -> str:
    labels = {"tier_1": "一階", "tier_2": "二階", "tier_3": "三階", "tier_4": "四階"}
    lines = []
    for tier, label in labels.items():
        members = tree.get(tier)
        if not members:
            continue
        reps = "、".join(
            f"{m['name']}({m['ticker']}{f', T+{m['lag_days']}d' if m.get('lag_days') else ''})"
            for m in members
        )
        lines.append(f"  - **{label}**：{reps}")
    return "\n".join(lines) if lines else "  - (無因果樹)"


def _verdict_block(v: dict[str, Any]) -> str:
    hist = v.get("historical_match", [])
    hist_md = (
        "；".join(f"{h['event']}(相似 {h['similarity']:.2f} → {h['outcome']})" for h in hist)
        if hist else "無歷史對應"
    )
    lead = v.get("expected_lead_days")
    lead_md = f"，預期領先 ~{lead} 天" if lead else ""
    return (
        f"### {v['theme']}\n"
        f"- **觸發**：{v['trigger']}\n"
        f"- **信心**：{v.get('confidence', 0):.2f}{lead_md}\n"
        f"- **因果樹**：\n{_tree_md(v.get('causal_tree', {}))}\n"
        f"- **歷史對應**：{hist_md}\n"
        f"- **推理**：{v.get('reasoning', '')}\n"
    )


def generate_report(
    verdicts: list[dict[str, Any]],
    *,
    report_date: date | None = None,
    missed_clusters: list[dict[str, Any]] | None = None,
) -> str:
    report_date = report_date or date.today()
    by_grade = {"strong": [], "watchlist": [], "reject": []}
    for v in verdicts:
        by_grade.setdefault(v.get("signal_grade", "reject"), []).append(v)

    out: list[str] = [
        f"# PolyDig 每日研究報告 — {report_date.isoformat()}",
        "",
        "> 系統靈魂:找的是事件還沒發酵、有領先效果的訊號。本報告為研究助理輸出,**非投資建議**,使用者自行判斷進場。",
        "",
        f"**摘要**：強訊號 {len(by_grade['strong'])} · 觀察清單 {len(by_grade['watchlist'])} · 駁回 {len(by_grade['reject'])}",
        "",
    ]

    out.append("## 🟢 今日強訊號")
    out.append("")
    if by_grade["strong"]:
        out += [_verdict_block(v) for v in by_grade["strong"]]
    else:
        out.append("_(今日無強訊號)_\n")

    out.append("## 🟡 觀察清單(邏輯成立但歷史對應弱)")
    out.append("")
    if by_grade["watchlist"]:
        out += [_verdict_block(v) for v in by_grade["watchlist"]]
    else:
        out.append("_(今日無觀察清單)_\n")

    if by_grade["reject"]:
        out.append("## ⚪ 駁回但有趣 (FYI)")
        out.append("")
        for v in by_grade["reject"]:
            out.append(f"- **{v['theme']}** — {v.get('reasoning', '')}")
        out.append("")

    if missed_clusters:
        out.append("## ⚠️ 漏抓案例(Price safety-net 觸發)")
        out.append("")
        out.append("以下族群已出現漲停潮,代表領先感測器可能漏抓,建議回溯檢視:")
        out.append("")
        for c in missed_clusters:
            members = "、".join(m.get("name", m.get("code", "?")) for m in c.get("members", []))
            out.append(f"- **{c.get('industry', '?')}**({len(c.get('members', []))} 檔)：{members}")
        out.append("")

    return "\n".join(out)


def write_report(content: str, output_dir: str | Path = "reports", report_date: date | None = None) -> Path:
    report_date = report_date or date.today()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report_date.isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path
