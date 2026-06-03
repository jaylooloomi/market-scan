"""Safety net: end-to-end lock that a crash-watch (risk_off_confluence) signal
flows pipeline -> report banner, and that it is NOT promoted to a theme
candidate. This whole wiring was previously untested end-to-end.

Offline (mocked signal provider, dry reviewer).
Run: python tests/test_daily_report_snapshot.py
"""
from __future__ import annotations

import sys
from datetime import date

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from market_scan_mcp.history.store import ThemeStore
from market_scan_mcp.reviewer.pipeline import run_daily


def provider():
    return [
        {
            "source": "news.anomaly", "signal_type": "news_anomaly",
            "content": {"term": "AI伺服器", "recent_count": 8, "prior_count": 1},
            "anomaly_score": 0.8,
        },
        {
            "source": "price.cluster", "signal_type": "limit_up_cluster",
            "content": {"total_limit_up": 12, "clusters": {"半導體": [{"code": "3661", "name": "世芯-KY"}]}},
            "anomaly_score": 0.6,
        },
        {  # crash-watch macro signal — should surface as a banner, not a theme
            "source": "data.crashwatch", "signal_type": "risk_off_confluence",
            "content": {"state": "risk_off", "stressed": ["yield_curve_10y3m", "hy_oas"], "n_stressed": 2, "total": 3},
            "anomaly_score": 0.8,
        },
    ]


def main() -> int:
    result = run_daily(
        store=ThemeStore(), reviewer_mode="dry",
        signal_provider=provider, report_date=date(2026, 1, 1),
    )
    md = result["report_md"]

    # standard report skeleton still there
    assert "# Market Scan 每日研究報告 — 2026-01-01" in md
    assert "🟢 今日強訊號" in md

    # crash-watch flowed all the way to the banner
    assert "今日大盤風險" in md and "🔴 風險升高" in md, "crash-watch banner not wired through pipeline"
    assert "yield_curve_10y3m" in md

    # the risk_off_confluence signal must NOT become a theme candidate/verdict
    cand_themes = " ".join(c.get("theme_hint", "") for c in result["candidates"])
    assert "risk_off" not in cand_themes, "crash-watch wrongly promoted to a candidate"
    assert all(v.get("theme") != "risk_off_confluence" for v in result["verdicts"])

    print("end-to-end crash-watch -> banner wiring locked ✓")
    return 0


def test_daily_report_snapshot():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
