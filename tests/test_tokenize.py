"""Unit test for the shared CJK-bigram + Latin tokeniser (common/tokenize.py),
extracted from the duplicate copies in history/store.py and reviewer/backfill.py.
Run: python tests/test_tokenize.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

from market_scan_mcp.common.tokenize import tokenize


def main() -> int:
    # Latin: lowercased, length >= 2 only
    assert tokenize("AI GPU") == {"ai", "gpu"}
    assert "a" not in tokenize("a AI"), "single-char latin should be dropped"
    assert tokenize("CoWoS 封裝") == {"cowos", "封裝"}

    # CJK: character bigrams, single char kept for length-1 runs
    assert tokenize("航運三雄") == {"航運", "運三", "三雄"}
    assert tokenize("金") == {"金"}

    # the point of bigrams: a short query stays a subset of a longer doc
    assert tokenize("航運") <= tokenize("台股航運三雄大漲")

    print("tokenize() behaviour locked ✓")
    return 0


def test_tokenize():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
