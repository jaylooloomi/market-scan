"""Gap 6: Missed-catch backfill + negative-sample learning loop.

Seeds storage with trailing signals + a limit-up cluster, runs backfill,
asserts a missed-catch record is produced with the trailing signal referenced.

Run: PYTHONIOENCODING=utf-8 python tests/test_backfill.py
"""
from __future__ import annotations

import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from market_scan_mcp.storage.db import MarketScanDB
from market_scan_mcp.reviewer.backfill import run_backfill


def main() -> int:
    print("=== Gap 6: Missed-catch Backfill ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        db = MarketScanDB(Path(tmpdir) / "backfill_test.db")

        # ── Seed trailing signals 45 days ago ────────────────────────────
        trailing_date = (date.today() - timedelta(days=45)).isoformat()

        # A news_anomaly for 半導體 that was there but not promoted
        leading_sig = {
            "timestamp": f"{trailing_date}T06:00:00+00:00",
            "source": "news.anomaly",
            "signal_type": "news_anomaly",
            "content": {
                "term": "半導體缺貨",
                "keywords": ["半導體", "世芯", "晶片"],
                "recent_count": 5,
                "prior_count": 1,
            },
            "anomaly_score": 0.60,  # was above threshold but not promoted
        }
        db.insert_signal(leading_sig)

        # A roadmap signal for the same family
        roadmap_sig = {
            "timestamp": f"{trailing_date}T07:00:00+00:00",
            "source": "roadmap.event",
            "signal_type": "roadmap_announcement",
            "content": {
                "keyword": "ASIC",
                "event": "世芯 AI ASIC 訂單擴增",
            },
            "anomaly_score": 0.55,
        }
        db.insert_signal(roadmap_sig)

        # Seed term history for the industry keywords
        for i in range(10):
            d = (date.today() - timedelta(days=i + 40)).isoformat()
            db.upsert_term_count(d, "半導體", 3 + i % 3, "news.anomaly")
            db.upsert_term_count(d, "世芯", 2, "news.anomaly")

        # ── Run backfill for the limit-up cluster ────────────────────────
        members = [
            {"code": "3661", "name": "世芯-KY"},
            {"code": "2330", "name": "台積電"},
            {"code": "3443", "name": "創意"},
        ]
        findings = run_backfill("半導體", members, db, lookback_days=90)

        print(f"conclusion: {findings['conclusion']}")
        print(f"leading_signals found: {len(findings['leading_signals'])}")
        print(f"leading_terms found: {len(findings['leading_terms'])}")
        print(f"reason_missed: {findings['reason_missed']}")

        # Should find the leading signals we seeded
        assert findings["conclusion"] == "found_leading_signals", (
            f"expected found_leading_signals, got {findings['conclusion']}"
        )
        assert len(findings["leading_signals"]) >= 1, (
            f"expected >=1 leading signal, got {len(findings['leading_signals'])}"
        )
        print("backfill found leading signals: PASS")

        # ── Persist to missed_catch table ────────────────────────────────
        mc_id = db.insert_missed_catch("半導體", members, findings)
        mcs = db.query_missed_catch(limit=10)
        assert len(mcs) == 1
        assert mcs[0]["industry"] == "半導體"
        assert mcs[0]["backfill"]["conclusion"] == "found_leading_signals"
        print("missed_catch persisted: PASS")

        # ── Test no-fundamental-basis case ────────────────────────────────
        no_signal_findings = run_backfill("某偏門族群XYZ", [], db, lookback_days=90)
        assert no_signal_findings["conclusion"] == "no_fundamental_basis", (
            f"expected no_fundamental_basis, got {no_signal_findings['conclusion']}"
        )
        print("no-fundamental-basis case: PASS")

        # ── Verify negative samples (rejects) stored as verdicts ────────
        reject_verdict = {
            "theme": "某某概念",
            "signal_grade": "reject",
            "confidence": 0.1,
            "reasoning": "no meaningful precedent",
        }
        db.insert_verdict(reject_verdict)
        rejects = db.query_verdicts(grade="reject", limit=10)
        assert len(rejects) >= 1
        print(f"negative samples (rejects) stored: PASS ({len(rejects)} reject verdicts)")

        db.close()

    print("\n=== PASS ===")
    return 0


def test_backfill():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
