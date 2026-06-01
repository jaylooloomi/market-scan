"""Turn Reviewer verdicts into a daily markdown research report.

Sections (design spec §6.6):
  - 今日強訊號 (strong)
  - 觀察清單 (watchlist)
  - 駁回但有趣 (reject, FYI)
  - 漏抓案例 (price safety-net backfill, if any)
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _themes_by_id() -> dict[str, Any]:
    """Lookup of the historical theme DB (id -> theme) for enriching the
    歷史 section with date + that theme's beneficiary stocks."""
    try:
        from polydig_mcp.history.store import load_themes
        return {t["id"]: t for t in load_themes()}
    except Exception:  # noqa: BLE001
        return {}


_TIER_LABEL = {"tier_1": "一階", "tier_2": "二階", "tier_3": "三階", "tier_4": "四階"}


def _stock_bullets(tree: dict[str, Any], indent: str = "  ") -> list[str]:
    """Bulleted (條列式) beneficiary stocks by tier."""
    lines: list[str] = []
    for tier, label in _TIER_LABEL.items():
        for m in tree.get(tier, []):
            lag = f"，T+{m['lag_days']}d" if m.get("lag_days") else ""
            role = f" — {m['role']}" if m.get("role") else ""
            lines.append(f"{indent}• {m['name']}({m['ticker']}){role}（{label}{lag}）")
    return lines or [f"{indent}• (無對應個股)"]


def _history_lines(hist: list[dict[str, Any]]) -> list[str]:
    """歷史 → 日期 → 題材 → 哪些股票 (條列式), enriched from the theme DB."""
    if not hist:
        return ["  • (無歷史對應)"]
    by_id = _themes_by_id()
    lines: list[str] = []
    for h in hist:
        theme = by_id.get(h.get("theme_id"))
        date_str = theme.get("trigger_date", "—") if theme else "—"
        name = (theme.get("name") if theme else None) or h.get("event", "?")
        sim = h.get("similarity")
        sim_str = f"，相似 {sim:.2f}" if isinstance(sim, (int, float)) else ""
        outcome = h.get("outcome") or (theme.get("outcome") if theme else "")
        lines.append(f"  • {date_str}｜{name}{sim_str}" + (f"（結果:{outcome}）" if outcome else ""))
        # that historical theme's own beneficiary stocks (條列)
        if theme:
            t1 = theme.get("causal_tree", {}).get("tier_1", [])
            if t1:
                stocks = "、".join(f"{m['name']}({m['ticker']})" for m in t1)
                lines.append(f"    當時受益股:{stocks}")
            # deeper analogue (e.g. SARS) noted if present
            for a in theme.get("historical_analogue", [])[:1]:
                lines.append(f"    更早對應:{a.get('event','')}（{a.get('outcome','')}）")
    return lines


def _source_lines(sources: list[dict[str, Any]]) -> list[str]:
    """新聞/資料來源連結 (條列). URL where available, else source name only."""
    if not sources:
        return []
    out = ["- 來源/連結:"]
    seen: set[str] = set()
    for s in sources:
        key = f"{s.get('source')}|{s.get('url')}"
        if key in seen:
            continue
        seen.add(key)
        url = s.get("url")
        if url:
            out.append(f"  • [{s.get('source','?')}] {url}")
        else:
            out.append(f"  • [{s.get('source','?')}]（{s.get('signal_type','')},無新聞連結）")
    return out


def _verdict_block(v: dict[str, Any]) -> str:
    grade_label = {"strong": "強訊號", "watchlist": "觀察清單", "reject": "駁回"}.get(
        v.get("signal_grade", ""), ""
    )
    lead = v.get("expected_lead_days")
    lead_md = f" · 預期領先 ~{lead} 天" if lead else ""
    lines = [
        f"### {v['theme']}（{grade_label} · 信心 {v.get('confidence', 0):.2f}{lead_md}）",
        "",
        "**📰 新聞 → 題材 → 股票**",
        f"- 新聞/觸發:{v['trigger']}",
        *_source_lines(v.get("sources", [])),
        f"- 題材:{v['theme']}",
        "- 受益股因果樹(一/二/三階,條列):",
        *_stock_bullets(v.get("causal_tree", {})),
        "",
        "**📜 歷史 → 日期 → 題材 → 股票**",
        *_history_lines(v.get("historical_match", [])),
    ]
    if v.get("reasoning"):
        lines += ["", f"- 推理:{v['reasoning']}"]
    return "\n".join(lines) + "\n"


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
            url = next((s["url"] for s in v.get("sources", []) if s.get("url")), None)
            link = f" — 🔗 {url}" if url else ""
            out.append(f"- **{v['theme']}**{link}")
        out.append("")

    if missed_clusters:
        out.append("## ⚠️ 漏抓案例(Price safety-net 觸發)")
        out.append("")
        out.append("以下族群已出現漲停潮(領先感測器可能漏抓)。系統已自動回溯近 90 天訊號:")
        out.append("")
        _concl_label = {
            "found_leading_signals": "🔁 回溯找到前期訊號(漏抓)",
            "no_fundamental_basis": "🎲 回溯無對應訊號(疑純散戶)",
        }
        for c in missed_clusters:
            members = "、".join(m.get("name", m.get("code", "?")) for m in c.get("members", []))
            out.append(f"- **{c.get('industry', '?')}**({len(c.get('members', []))} 檔)：{members}")
            bf = c.get("backfill")
            if bf:
                label = _concl_label.get(bf.get("conclusion"), bf.get("conclusion", ""))
                out.append(f"  - **回溯結論**:{label}")
                if bf.get("reason_missed"):
                    out.append(f"    - {bf['reason_missed']}")
                for ls in bf.get("leading_signals", [])[:3]:
                    out.append(
                        f"    - 前期訊號:`{ls.get('source')}` @ {ls.get('timestamp','')[:10]} "
                        f"(score {ls.get('anomaly_score')}, 命中 {','.join(ls.get('matched_tokens', [])[:5])})"
                    )
            else:
                out.append("  - 回溯:未啟用(需以 --db 執行才會自動回溯)")
        out.append("")

    return "\n".join(out)


def write_report(content: str, output_dir: str | Path = "reports", report_date: date | None = None) -> Path:
    report_date = report_date or date.today()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report_date.isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path
