"""Gap 1: Historical-recall backtest — spec §10 success metric.

Asserts: recall >= 3/5 deep cases recalled offline (hold-one-out).
Run: PYTHONIOENCODING=utf-8 python tests/test_backtest_recall.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from polydig_mcp.reviewer.backtest import run_recall_suite, recall_at_k, DEEP_CASE_IDS


def main() -> int:
    print("=== Gap 1: Historical Recall Backtest ===\n")

    # -- Hold-one-out end-to-end recall --
    results = run_recall_suite()
    recalled_count = sum(1 for r in results if r.recalled)

    print(f"{'Theme ID':<30} {'Name':<20} {'Recalled':^9} {'Grade':<12} {'Note'}")
    print("-" * 100)
    for r in results:
        flag = "YES" if r.recalled else "NO"
        print(f"{r.theme_id:<30} {r.theme_name:<20} {flag:^9} {r.grade:<12} {r.note}")

    print(f"\nEnd-to-end recall (hold-one-out): {recalled_count}/{len(results)}")

    # -- RAG recall@3 (unmasked) --
    rag = recall_at_k(k=3)
    print(f"\nRAG recall@3 (unmasked, pure retrieval): {rag['hits']}/{rag['total']}")
    for d in rag["details"]:
        status = "HIT" if d["hit"] else "miss"
        print(f"  {d['theme_id']:<30} [{status}]  top-3: {d['top_k']}")

    # Assert success metric >= 3/5
    assert recalled_count >= 3, (
        f"FAIL: recall {recalled_count}/5 < 3/5 (spec §10 requirement)"
    )
    print(f"\n=== PASS — recall {recalled_count}/5 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
