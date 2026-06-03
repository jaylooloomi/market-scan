"""Spec §10 operational metrics: signal_volume (offline) + hit_rate (fake fetcher).

Seeds a DB with graded verdicts and asserts the noise-control stats and the
month-hit-rate computation. Run: PYTHONIOENCODING=utf-8 python tests/test_metrics.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, "src")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from market_scan_mcp.reviewer.metrics import (
    compute_metrics,
    finmind_forward_return,
    hit_rate,
    signal_volume,
)
from market_scan_mcp.storage.db import MarketScanDB


def main() -> int:
    print("=== Spec §10 operational metrics ===\n")
    db = MarketScanDB(os.path.join(tempfile.mkdtemp(), "metrics.db"))

    base = {
        "theme": "AI", "trigger": "ChatGPT", "signal_grade": "strong", "confidence": 0.9,
        "causal_tree": {"tier_1": [{"ticker": "3231", "name": "緯創", "lag_days": 150}]},
        "historical_match": [], "reasoning": "x",
    }
    # 2026-01-01: 1 strong + 1 reject (within noise target)
    db.insert_verdict(base, report_date="2026-01-01")
    db.insert_verdict({**base, "theme": "junk", "signal_grade": "reject"}, report_date="2026-01-01")
    # 2026-01-02: 6 strong (exceeds the noise target of 5)
    for i in range(6):
        db.insert_verdict({**base, "theme": f"S{i}"}, report_date="2026-01-02")

    verdicts = db.query_verdicts(limit=1000)

    # ── signal_volume (fully offline) ──────────────────────────────────────
    sv = signal_volume(verdicts)
    print("signal_volume:", sv)
    assert sv["days_observed"] == 2, sv
    assert sv["max_daily_strong"] == 6, sv
    assert "2026-01-02" in sv["days_over_noise_target"], sv
    assert sv["noise_ok"] is False, sv
    assert sv["grade_totals"]["strong"] == 7 and sv["grade_totals"]["reject"] == 1, sv
    print("signal_volume / noise-control: PASS")

    # ── hit_rate with an injected (fake) forward-return source ─────────────
    def fake_fwd(ticker: str, since: str, days: int):
        return 0.5 if ticker == "3231" else 0.05  # 緯創 hits >=20%, others don't

    hr = hit_rate(verdicts, fake_fwd)
    print("hit_rate:", {k: hr[k] for k in ("scored", "hits", "hit_rate", "meets_target")})
    assert hr["scored"] == 7, hr            # 7 strong verdicts scored
    assert hr["hit_rate"] == 1.0, hr        # all tier_1 = 3231 -> all hit
    assert hr["meets_target"] is True, hr

    # a stricter fake where nothing hits -> below target
    miss = hit_rate(verdicts, lambda t, s, d: 0.05)
    assert miss["hit_rate"] == 0.0 and miss["meets_target"] is False, miss
    print("hit_rate (hit + miss cases): PASS")

    # ── compute_metrics without a fetcher -> hit_rate reports needs-data ───
    m = compute_metrics(db)
    assert "status" in m["hit_rate"], m
    assert m["signal_volume"]["max_daily_strong"] == 6, m
    print("compute_metrics (no fetcher -> needs-data status): PASS")

    # ── finmind_forward_return with a mocked FinMind query (no token/network) ─
    def fake_query(dataset, ticker, start, end):
        return [{"date": start, "close": 100.0}, {"date": end, "close": 130.0}]  # +30%

    r = finmind_forward_return("3231", "2026-01-01", 90, query=fake_query)
    assert r is not None and abs(r - 0.30) < 1e-9, r
    assert finmind_forward_return("X", "2026-01-01", 90, query=lambda *a: []) is None
    print("finmind_forward_return (mocked): PASS")

    db.close()
    print("\n=== PASS ===")
    return 0


def test_metrics():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
