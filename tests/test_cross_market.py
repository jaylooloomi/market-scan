"""Gap 5: Cross-market US → TW linkage test.

Feeds a mock US-sector-move signal, asserts TW candidate themes are generated.
No network calls.

Run: PYTHONIOENCODING=utf-8 python tests/test_cross_market.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from market_scan_mcp.reviewer.scout import signals_to_candidates, us_signal_to_tw_candidates


def make_us_signal(sector: str, pct: float) -> dict:
    from market_scan_mcp.data.macro import US_TW_MAPPING
    return {
        "source": "data.us_sector",
        "signal_type": "us_sector_move",
        "content": {
            "sector": sector,
            "pct_change": pct,
            "latest": 5000.0,
            "period_start": 4762.0,
            "tw_theme_families": US_TW_MAPPING.get(sector, []),
            "days": 30,
        },
        "anomaly_score": min(1.0, abs(pct) * 3),
        "timestamp": "2023-01-01T06:00:00+00:00",
    }


def main() -> int:
    print("=== Gap 5: Cross-Market US → TW Linkage ===\n")

    # ── 1. Direct helper test ─────────────────────────────────────────────
    # NASDAQ carries the semi/AI families (PHLX/SOX has no keyless FRED feed,
    # so it was removed from US_TW_MAPPING — semis ride nasdaq instead).
    from market_scan_mcp.data.macro import US_TW_MAPPING
    sig_strong = make_us_signal("nasdaq", 0.12)  # +12% NASDAQ
    cands = us_signal_to_tw_candidates(sig_strong)
    print(f"NASDAQ +12% → {len(cands)} TW candidates:")
    for c in cands:
        print(f"  - {c['theme_hint']}")
        assert c["cross_market"] is True
        assert c["us_moves"][0]["sector"] == "nasdaq"
        assert c["tw_family"] in US_TW_MAPPING["nasdaq"]
    assert len(cands) >= 1, "expected >=1 TW candidate for NASDAQ +12%"
    print("direct helper: PASS")

    # ── 2. Below threshold → no candidates ───────────────────────────────
    sig_weak = make_us_signal("nasdaq", 0.02)  # +2% (below 5% threshold)
    weak_cands = us_signal_to_tw_candidates(sig_weak)
    assert len(weak_cands) == 0, f"expected 0 candidates for weak move, got {len(weak_cands)}"
    print("below-threshold: PASS (0 candidates as expected)")

    # ── 3. Error signal → no candidates ──────────────────────────────────
    error_sig = {
        "source": "data.us_sector",
        "signal_type": "us_sector_move",
        "content": {"error": "FRED timeout"},
        "anomaly_score": None,
    }
    err_cands = us_signal_to_tw_candidates(error_sig)
    assert len(err_cands) == 0, "error signal should produce no candidates"
    print("error signal: PASS (0 candidates)")

    # ── 4. Integration: signals_to_candidates routes us_sector_move ──────
    mixed_signals = [
        make_us_signal("nasdaq", +0.08),  # strong NASDAQ +8%
        {   # regular news anomaly
            "source": "news.anomaly", "signal_type": "news_anomaly",
            "content": {"term": "AI伺服器"}, "anomaly_score": 0.7,
        },
    ]
    all_cands = signals_to_candidates(mixed_signals)
    us_cands = [c for c in all_cands if c.get("cross_market")]
    news_cands = [c for c in all_cands if not c.get("cross_market") and not c.get("is_safety_net")]
    assert len(us_cands) >= 1, f"expected >=1 US→TW candidate, got {len(us_cands)}"
    assert len(news_cands) >= 1, f"expected >=1 news candidate, got {len(news_cands)}"
    print(f"integration: PASS — {len(us_cands)} US→TW + {len(news_cands)} news candidates")
    for c in us_cands:
        print(f"  US→TW: {c['theme_hint']}")

    print("\n=== PASS ===")
    return 0


def test_cross_market():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
