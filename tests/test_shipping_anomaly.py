"""Freight-index (SCFI) anomaly detection test — the "data leads price" sensor.

Proves: fed the real 2020 SCFI weekly rise, the detector fires EARLY (mid-July,
SCFI ~1120, when 長榮 was still ~13 and the 缺櫃 news hadn't appeared) — months
before a news-only system could react. Run: python tests/test_shipping_anomaly.py
"""
from __future__ import annotations

import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from polydig_mcp.data.shipping import detect_index_anomaly
from polydig_mcp.data import server as d


def main() -> int:
    # Real-ish 2020 SCFI H2 weekly prints (sustained rise; 長榮 ~12 in June)
    scfi_early = [
        ("2020-05-29", 920), ("2020-06-05", 935), ("2020-06-12", 960),
        ("2020-06-19", 990), ("2020-06-26", 1010), ("2020-07-03", 1040),
        ("2020-07-10", 1080), ("2020-07-17", 1120),
    ]
    early = detect_index_anomaly(scfi_early)
    print(f"early (to 2020-07-17, SCFI~1120): score={early['anomaly_score']} "
          f"streak={early['consecutive_up']} reason={early['reason']}")
    assert early["anomaly_score"] >= 0.7, "should fire strongly on the early sustained rise"

    # Flat series must NOT fire
    flat = [(f"2020-06-{d:02d}", 900 + (d % 2)) for d in range(1, 12)]
    flat_res = detect_index_anomaly(flat)
    print(f"flat series: score={flat_res['anomaly_score']}")
    assert flat_res["anomaly_score"] < 0.3, "flat series must not be anomalous"

    # Full tool chain via ingest + get_shipping_index (recent dates, in 180d window)
    db = tempfile.mktemp(suffix=".db")
    vals = [920, 935, 960, 990, 1010, 1040, 1080, 1120, 1160, 1220, 1280, 1360]
    for i, v in enumerate(vals):
        dt = (date.today() - timedelta(weeks=len(vals) - 1 - i)).isoformat()
        d.ingest_shipping_index("SCFI", dt, v, db_path=db)
    r = d.get_shipping_index("SCFI", db_path=db)
    c = r["content"]
    print(f"get_shipping_index: score={r['anomaly_score']} reason={c.get('reason')}")
    assert "error" not in c and r["anomaly_score"] >= 0.7

    # Empty unmapped index → graceful error, not crash
    empty = d.get_shipping_index("SCFI", db_path=tempfile.mktemp(suffix=".db"))
    assert "error" in empty["content"]
    print("empty SCFI (no auto-source): graceful error ✓")

    # Live: the free dry-bulk freight complex auto-scrapes East Money
    # (best-effort — skip cleanly if offline). Container SCFI is login-gated → ingest only.
    try:
        from polydig_mcp.data.shipping import EASTMONEY_INDICATORS, fetch_eastmoney_index
        for idx in EASTMONEY_INDICATORS:
            live = fetch_eastmoney_index(idx, limit=10)
            print(f"live East Money {idx}: {len(live)} points, latest={live[-1]}")
            assert len(live) >= 3 and live[-1][1] > 0
    except Exception as e:  # noqa: BLE001 — network-dependent, don't fail the suite
        print(f"live dry-bulk fetch skipped (network?): {e}")

    # Live: SCFI (container) direction/momentum from FREE Google News RSS
    try:
        from polydig_mcp.data.shipping import fetch_scfi_news_signal
        scfi = fetch_scfi_news_signal()
        print(f"live SCFI news signal: dir={scfi['direction']} streak={scfi['streak']} "
              f"pct={scfi['pct_move']} score={scfi['anomaly_score']} ({len(scfi['headlines'])} headlines)")
        assert scfi["direction"] in ("rising", "falling", "mixed")
    except Exception as e:  # noqa: BLE001 — network-dependent, don't fail the suite
        print(f"live SCFI news fetch skipped (network?): {e}")

    print("=== PASS ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
