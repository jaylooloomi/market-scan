"""Gap 2: SQLite storage layer round-trip test.

Creates a temp DB, inserts signals/verdicts/term_history/missed_catch,
queries back, asserts round-trip correctness.

Run: PYTHONIOENCODING=utf-8 python tests/test_storage.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from polydig_mcp.storage.db import PolyDigDB


def main() -> int:
    print("=== Gap 2: SQLite Storage Layer ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_polydig.db"
        db = PolyDigDB(db_path)

        # ── signals round-trip ─────────────────────────────────────────────
        sig = {
            "timestamp": "2026-05-31T06:00:00+00:00",
            "source": "news.anomaly",
            "signal_type": "news_anomaly",
            "content": {"term": "AI伺服器", "count": 8},
            "anomaly_score": 0.85,
        }
        row_id = db.insert_signal(sig)
        assert isinstance(row_id, int), f"insert_signal returned non-int: {row_id}"

        rows = db.query_signals(source="news.anomaly", limit=10)
        assert len(rows) == 1, f"expected 1 signal, got {len(rows)}"
        assert rows[0]["source"] == "news.anomaly"
        assert rows[0]["content"]["term"] == "AI伺服器"
        assert rows[0]["anomaly_score"] == 0.85
        print("signals: PASS (insert + query round-trip)")

        # ── term_history / baseline ────────────────────────────────────────
        for i in range(7):
            from datetime import date, timedelta
            d = (date(2026, 5, 24) + timedelta(days=i)).isoformat()
            db.upsert_term_count(d, "AI伺服器", 3 + i, "news.anomaly")

        baseline = db.term_baseline("AI伺服器", "news.anomaly", lookback_days=30)
        assert 3.0 <= baseline <= 10.0, f"baseline out of expected range: {baseline}"
        print(f"term_history: PASS (baseline={baseline:.1f})")

        # missing term baseline should return 0.0
        empty = db.term_baseline("某個不存在的詞", "news.anomaly", lookback_days=30)
        assert empty == 0.0, f"expected 0.0 for missing term, got {empty}"
        print("term_history missing term: PASS")

        # ── verdicts round-trip ────────────────────────────────────────────
        verdict = {
            "theme": "AI概念股",
            "trigger": "ChatGPT爆紅",
            "signal_grade": "strong",
            "confidence": 0.87,
            "causal_tree": {},
            "historical_match": [],
            "reasoning": "dry-run",
        }
        v_id = db.insert_verdict(verdict, report_date="2026-05-31")
        assert isinstance(v_id, int)

        # Also insert a reject (negative sample)
        reject_v = {**verdict, "theme": "某某概念", "signal_grade": "reject", "confidence": 0.1}
        db.insert_verdict(reject_v, report_date="2026-05-31")

        all_v = db.query_verdicts(limit=10)
        assert len(all_v) == 2, f"expected 2 verdicts, got {len(all_v)}"

        strong_v = db.query_verdicts(grade="strong", limit=10)
        assert len(strong_v) == 1
        assert strong_v[0]["theme"] == "AI概念股"

        reject_list = db.query_verdicts(grade="reject", limit=10)
        assert len(reject_list) == 1
        print("verdicts: PASS (strong + reject round-trip)")

        # ── missed_catch round-trip ────────────────────────────────────────
        mc_id = db.insert_missed_catch(
            industry="半導體",
            members=[{"code": "3661", "name": "世芯-KY"}],
            backfill_findings={"leading_signal": "AI伺服器 news anomaly 30d ago"},
            date_str="2026-05-31",
        )
        assert isinstance(mc_id, int)

        mcs = db.query_missed_catch(limit=10)
        assert len(mcs) == 1
        assert mcs[0]["industry"] == "半導體"
        assert mcs[0]["backfill"]["leading_signal"] == "AI伺服器 news anomaly 30d ago"
        print("missed_catch: PASS (insert + query round-trip)")

        db.close()

    print("\n=== PASS — all storage round-trips OK ===")
    return 0


def test_storage():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
