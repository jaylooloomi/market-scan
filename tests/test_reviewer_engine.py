"""Safety net: lock the Reviewer engine's heuristic (dry-mode) grading and
source extraction — the core signal->verdict path, previously only tested
indirectly via the pipeline.

Uses a fake store so grading is deterministic and offline.
Run: python tests/test_reviewer_engine.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from market_scan_mcp.reviewer.engine import _extract_sources, review


class _FakeMatch:
    def __init__(self, d):
        self._d = d

    def to_dict(self):
        return self._d


class _FakeStore:
    """Duck-typed stand-in for ThemeStore: returns canned precedents."""
    def __init__(self, matches):
        self._m = matches

    def query(self, _text, n_results=3):
        return [_FakeMatch(d) for d in self._m[:n_results]]


def _candidate(**kw):
    return {
        "theme_hint": kw.get("theme", "AI 伺服器"),
        "trigger_summary": kw.get("trigger", "AI 需求爆發"),
        "raw_signals": kw.get("raw_signals", []),
    }


def _match(sim, verdict="strong"):
    return {
        "id": "ai-2023",
        "name": "AI 伺服器 2023",
        "similarity": sim,
        "reviewer_verdict": verdict,
        "outcome": "+50%",
        "causal_tree": {"tier_1": [{"name": "台積電", "ticker": "2330", "role": "代工", "lag_days": 0}]},
    }


def main() -> int:
    cand = _candidate()

    # strong precedent (sim>=0.5, verdict=strong) -> strong, carries tree + confidence
    v = review(cand, _FakeStore([_match(0.8, "strong")]), mode="dry")
    assert v["signal_grade"] == "strong", v["signal_grade"]
    assert v["confidence"] == 0.8, v["confidence"]
    assert v["causal_tree"]["tier_1"][0]["ticker"] == "2330"
    assert v["theme"] == "AI 伺服器"

    # strong similarity but the precedent itself was a reject -> downgraded to watchlist
    v = review(cand, _FakeStore([_match(0.8, "reject")]), mode="dry")
    assert v["signal_grade"] == "watchlist", v["signal_grade"]

    # weak precedent (0.2<=sim<0.5) -> watchlist
    v = review(cand, _FakeStore([_match(0.3, "strong")]), mode="dry")
    assert v["signal_grade"] == "watchlist", v["signal_grade"]

    # negligible precedent (sim<0.2) -> reject
    v = review(cand, _FakeStore([_match(0.1, "strong")]), mode="dry")
    assert v["signal_grade"] == "reject", v["signal_grade"]

    # no precedent at all -> reject, zero confidence
    v = review(cand, _FakeStore([]), mode="dry")
    assert v["signal_grade"] == "reject" and v["confidence"] == 0.0

    # source extraction: article links, FRED series page, limit-up TWSE link
    cand2 = _candidate(raw_signals=[
        {"source": "news", "signal_type": "news_anomaly", "content": {"article_urls": ["u1", "u2"]}},
        {"source": "data", "signal_type": "commodity_price", "content": {"fred_series": "DCOILWTICO"}},
        {"source": "price", "signal_type": "limit_up_cluster", "content": {}},
    ])
    srcs = _extract_sources(cand2)
    urls = [s["url"] for s in srcs]
    assert "u1" in urls and "u2" in urls, urls
    assert "https://fred.stlouisfed.org/series/DCOILWTICO" in urls, urls
    assert any("openapi.twse.com.tw" in (u or "") for u in urls), urls

    print("reviewer engine heuristic grading + source extraction locked ✓")
    return 0


def test_reviewer_engine():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
