"""Safety net: lock the daily-report generator structure, especially the
crash-watch banner (previously untested) and all grade sections.

Deterministic (fixed date, historical_match=[] to avoid themes.json coupling).
Run: python tests/test_report_generator.py
"""
from __future__ import annotations

import sys
from datetime import date

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from market_scan_mcp.reporting.generator import generate_report


def _verdict(theme, grade, conf, **kw):
    return {
        "theme": theme,
        "signal_grade": grade,
        "confidence": conf,
        "trigger": kw.get("trigger", f"{theme} 觸發"),
        "sources": kw.get(
            "sources",
            [{"source": "news.anomaly", "signal_type": "news_anomaly", "url": "https://example.com/a"}],
        ),
        "causal_tree": kw.get(
            "causal_tree",
            {"tier_1": [{"name": "台積電", "ticker": "2330", "role": "代工", "lag_days": 0}]},
        ),
        "historical_match": [],  # keep deterministic — no themes.json lookup
        "reasoning": kw.get("reasoning", "test"),
        "expected_lead_days": kw.get("expected_lead_days"),
    }


def main() -> int:
    verdicts = [
        _verdict("AI 伺服器", "strong", 0.81, expected_lead_days=20),
        _verdict("航運", "watchlist", 0.35),
        _verdict("無聊題材", "reject", 0.05),
    ]
    market_risk = {
        "state": "risk_off",
        "stressed": ["yield_curve_10y3m", "hy_oas"],
        "n_stressed": 2,
        "total": 3,
    }
    md = generate_report(verdicts, report_date=date(2026, 1, 1), market_risk=market_risk)

    # header + summary line
    assert "# Market Scan 每日研究報告 — 2026-01-01" in md, "header/date missing"
    assert "強訊號 1 · 觀察清單 1 · 駁回 1" in md, "summary counts wrong"

    # crash-watch banner — the part with no prior coverage
    assert "今日大盤風險" in md and "crash-watch" in md, "crash-watch banner missing"
    assert "🔴 風險升高" in md, "risk_off label missing"
    assert "2/3 指標亮燈" in md, "stressed count missing"
    assert "yield_curve_10y3m、hy_oas" in md, "stressed list missing"

    # all three grade sections present
    assert "🟢 今日強訊號" in md
    assert "🟡 觀察清單" in md
    assert "⚪ 駁回但有趣" in md

    # strong verdict block detail (grade label, confidence, lead, causal tree)
    assert "AI 伺服器" in md and "強訊號" in md
    assert "信心 0.81" in md
    assert "預期領先 ~20 天" in md
    assert "台積電(2330)" in md and "一階" in md

    # reject rendered as a one-liner
    assert "**無聊題材**" in md

    # banner reflects each state
    for state, label in (("calm", "🟢 平穩"), ("caution", "🟡 留意"), ("risk_off", "🔴 風險升高")):
        m = generate_report(
            [], report_date=date(2026, 1, 1),
            market_risk={"state": state, "stressed": [], "n_stressed": 0, "total": 3},
        )
        assert label in m, f"banner label for state={state} missing"

    # no banner when crash-watch errored or absent (honest degradation)
    assert "crash-watch" not in generate_report([], report_date=date(2026, 1, 1), market_risk={"error": "fred down"})
    assert "crash-watch" not in generate_report([], report_date=date(2026, 1, 1))

    print("report generator + crash-watch banner structure locked ✓")
    return 0


def test_report_generator():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
