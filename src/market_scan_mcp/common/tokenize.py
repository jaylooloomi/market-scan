"""Cheap CJK-bigram + Latin-word tokeniser.

Shared by the RAG fallback retriever (history/store.py) and the missed-catch
backfill (reviewer/backfill.py). Bigrams keep query/doc vocab aligned:
'航運三雄' -> {航運, 運三, 三雄} so a query '航運' still matches. Single chars
are kept for length-1 runs.
"""
from __future__ import annotations

import re

_CJK = re.compile(r"[一-鿿]+")
_LATIN = re.compile(r"[A-Za-z0-9]{2,}")


def tokenize(text: str) -> set[str]:
    """Latin words (lowercased, length >= 2) + CJK character bigrams."""
    out = {t.lower() for t in _LATIN.findall(text)}
    for run in _CJK.findall(text):
        if len(run) == 1:
            out.add(run)
        else:
            out.update(run[i : i + 2] for i in range(len(run) - 1))
    return out
