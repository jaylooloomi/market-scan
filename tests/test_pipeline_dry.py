"""Phase 2 end-to-end (dry) pipeline test with mocked sensor signals.

Proves: signals -> Scout candidates -> Reviewer (RAG + heuristic) -> report,
deterministically and offline. Run: python tests/test_pipeline_dry.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from market_scan_mcp.history.store import ThemeStore
from market_scan_mcp.reviewer.pipeline import run_daily


def mock_signals():
    return [
        {  # news anomaly resembling the AI theme
            "source": "news.anomaly", "signal_type": "news_anomaly",
            "content": {"term": "AI伺服器", "recent_count": 8, "prior_count": 1}, "anomaly_score": 0.8,
        },
        {  # data anomaly resembling shipping
            "source": "data.shipping", "signal_type": "shipping_index",
            "content": {"proxy_for": "BDI", "pct_change": 0.4, "note": "運價 缺櫃 航運"}, "anomaly_score": 0.8,
        },
        {  # price safety-net cluster
            "source": "price.cluster", "signal_type": "limit_up_cluster",
            "content": {"total_limit_up": 12, "clusters": {"半導體": [{"code": "3661", "name": "世芯-KY"}]}},
            "anomaly_score": 0.6,
        },
        {"source": "data.commodity", "signal_type": "commodity_price",
         "content": {"error": "should be skipped"}, "anomaly_score": None},
    ]


def main() -> int:
    store = ThemeStore()
    result = run_daily(store=store, reviewer_mode="dry", signal_provider=mock_signals)

    print(f"RAG mode: {store.mode}")
    print(f"candidates: {len(result['candidates'])}")
    for v in result["verdicts"]:
        print(f"  - {v['theme']}: {v['signal_grade']} (conf {v['confidence']}) "
              f"tiers={list(v['causal_tree'].keys())}")

    assert len(result["candidates"]) >= 3, "expected >=3 candidates (error signal skipped)"
    grades = {v["signal_grade"] for v in result["verdicts"]}
    assert grades & {"strong", "watchlist"}, "expected at least one strong/watchlist verdict"
    assert "Market Scan 每日研究報告" in result["report_md"]
    assert "因果樹" in result["report_md"]

    print("\n=== REPORT (first 1200 chars) ===")
    print(result["report_md"][:1200])
    print("\n=== PASS ===")
    return 0


def test_pipeline_dry():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
