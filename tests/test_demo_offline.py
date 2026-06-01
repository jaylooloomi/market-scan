"""Gap 4: Offline demo test.

Runs the demo path (canned signals, no network) and asserts:
- Report is non-empty
- Contains causal trees
- Contains at least one non-reject verdict

Network is NOT patched because demo_signals() never makes network calls.

Run: PYTHONIOENCODING=utf-8 python tests/test_demo_offline.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from polydig_mcp.daily_cli import demo_signals
from polydig_mcp.history.store import ThemeStore
from polydig_mcp.reviewer.pipeline import run_daily


def main() -> int:
    print("=== Gap 4: Offline Demo ===\n")

    store = ThemeStore()  # offline fallback RAG, no network
    result = run_daily(store=store, reviewer_mode="dry", signal_provider=demo_signals)

    # Check signals are the canned ones
    sigs = result["signals"]
    assert len(sigs) >= 3, f"expected >=3 demo signals, got {len(sigs)}"
    stypes = {s["signal_type"] for s in sigs}
    assert "news_anomaly" in stypes, "expected news_anomaly in demo signals"
    assert "limit_up_cluster" in stypes, "expected limit_up_cluster in demo signals"
    print(f"signals: {len(sigs)} ({sorted(stypes)})")

    # Check candidates
    cands = result["candidates"]
    assert len(cands) >= 3, f"expected >=3 candidates, got {len(cands)}"
    print(f"candidates: {len(cands)}")

    # Check verdicts
    verdicts = result["verdicts"]
    assert len(verdicts) >= 3, f"expected >=3 verdicts, got {len(verdicts)}"
    grades = {v["signal_grade"] for v in verdicts}
    assert grades & {"strong", "watchlist"}, f"expected at least one non-reject verdict, got {grades}"
    print(f"verdicts: {len(verdicts)}, grades={sorted(grades)}")

    # Check report
    md = result["report_md"]
    assert len(md) > 200, f"report too short ({len(md)} chars)"
    assert "PolyDig 每日研究報告" in md, "report missing header"
    assert "因果樹" in md, "report missing causal tree section"

    # At least one verdict should have a non-empty causal tree
    trees_present = any(
        any(v.get("causal_tree", {}).get(tier) for tier in ("tier_1", "tier_2", "tier_3"))
        for v in verdicts
    )
    assert trees_present, "no verdict has a causal tree — expected at least one"
    print("report: non-empty with causal trees present")

    print("\n=== REPORT (first 1000 chars) ===")
    print(md[:1000])
    print("\n=== PASS — offline demo works with zero network calls ===")
    return 0


def test_demo_offline():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
