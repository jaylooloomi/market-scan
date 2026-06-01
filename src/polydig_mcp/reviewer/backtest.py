"""Historical-recall backtest harness (spec §10 success metric).

End-to-end dry run that checks whether the pipeline CAN recall the correct
historical precedent for each of the 5 deep-case themes, given synthesised
sensor signals derived from the theme's own metadata.

Key design:
- Hold-one-out: when testing theme X, X is MASKED from the store so the
  retrieval has to find X via analogue or token overlap with other themes —
  this avoids trivially self-matching.
- Synthesise signals from each theme's trigger_type + trigger_event keywords
  (no network calls needed).
- Recall (hold-one-out): the correct theme is MASKED, so recall honestly means
  the synthesised signal still surfaces a NON-REJECTED sibling analogue
  (signal_grade != "reject"). tier-1 ticker overlap with the masked theme is
  reported as a stricter sub-signal. This is a lenient "an analogue exists"
  measure — NOT proof of identifying the exact right theme. A rigorous test needs
  negative cases (themes that did NOT play out); see audit finding M2.
- recall_at_k: fraction of cases where the correct theme is in the top-k RAG
  results — but the query is built from the theme's OWN keywords while the store
  contains that theme, so this is near-circular (self-retrieval). Treat as a
  sanity check, not a discrimination metric.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polydig_mcp.history.store import ThemeStore, load_themes, theme_document, Match
from polydig_mcp.reviewer.engine import review
from polydig_mcp.reviewer.scout import signals_to_candidates

# ── The 5 deep cases ────────────────────────────────────────────────────────
DEEP_CASE_IDS = [
    "mask_2020",
    "shipping_2020",
    "ai_first_wave_2023",
    "defense_2022",
    "silicon_photonics_2024",
]

# Extra keyword hints that make each case's synthetic signal richer
_EXTRA_HINTS: dict[str, list[str]] = {
    "mask_2020":              ["武漢肺炎", "口罩", "防疫", "COVID", "coronavirus"],
    "shipping_2020":          ["運價", "航運", "SCFI", "BDI", "貨櫃", "container freight"],
    "ai_first_wave_2023":     ["AI伺服器", "ChatGPT", "NVIDIA", "人工智慧", "算力"],
    "defense_2022":           ["俄烏戰爭", "國防", "無人機", "軍備", "漢翔", "Ukraine"],
    "silicon_photonics_2024": ["矽光子", "CPO", "光通訊", "TSMC量產", "光模組"],
}


def _synthesise_signals(theme: dict[str, Any]) -> list[dict[str, Any]]:
    """Build synthetic sensor signals that would plausibly fire for this theme."""
    tid = theme["id"]
    ttype = theme.get("trigger_type", "News")
    trigger_text = theme.get("trigger_event", "")
    extra = _EXTRA_HINTS.get(tid, [])
    keywords = [theme["name"], trigger_text] + extra

    signals: list[dict[str, Any]] = []

    # Always add a news_anomaly signal
    signals.append({
        "source": "news.anomaly",
        "signal_type": "news_anomaly",
        "content": {
            "term": theme["name"],
            "keywords": keywords,
            "recent_count": 8,
            "prior_count": 1,
        },
        "anomaly_score": 0.85,
        "timestamp": f"{theme.get('trigger_date', '2023-01-01')}T06:00:00+00:00",
    })

    # Data / Roadmap secondary signals
    if "Data" in ttype:
        signals.append({
            "source": "data.shipping",
            "signal_type": "shipping_index",
            "content": {"proxy_for": "BDI", "pct_change": 0.42, "note": " ".join(keywords[:3])},
            "anomaly_score": 0.80,
            "timestamp": f"{theme.get('trigger_date', '2023-01-01')}T06:00:00+00:00",
        })

    if "Roadmap" in ttype:
        signals.append({
            "source": "roadmap.event",
            "signal_type": "roadmap_announcement",
            "content": {"keyword": keywords[0], "event": trigger_text},
            "anomaly_score": 0.75,
            "timestamp": f"{theme.get('trigger_date', '2023-01-01')}T06:00:00+00:00",
        })

    return signals


class _MaskedStore(ThemeStore):
    """ThemeStore with one theme masked out (for hold-one-out eval)."""

    def __init__(self, masked_id: str) -> None:
        super().__init__()
        self._masked_id = masked_id
        # rebuild docs without the masked theme
        self._themes = [t for t in self._themes if t["id"] != masked_id]
        self._docs = {t["id"]: theme_document(t) for t in self._themes}
        self._by_id = {t["id"]: t for t in self._themes}

    def query(self, text: str, n_results: int = 3) -> list[Match]:  # type: ignore[override]
        return self._fallback_query(text, n_results)


@dataclass
class BacktestCase:
    theme_id: str
    theme_name: str
    recalled: bool            # (a) top historical_match.theme_id == masked theme, or tier_1 overlap
    grade: str
    top_match_id: str | None
    tier1_overlap: bool
    note: str


def run_backtest_case(theme: dict[str, Any]) -> BacktestCase:
    """Run one hold-one-out backtest for a deep-case theme.

    Recall (honest, post-M2-fix): ``grade != "reject"`` — i.e. with the correct
    theme MASKED, the synthesised signal still surfaces a non-rejected sibling
    analogue. tier-1 ticker overlap with the masked theme is computed and reported
    as a stricter sub-signal, but is NOT required for recall. (The previous
    ``keyword_hit`` criterion was tautological — the candidate hint is literally the
    theme name — so it always passed and was removed; see audit M2.)
    """
    tid = theme["id"]
    # All tickers across all tiers of the expected theme
    expected_tickers: set[str] = set()
    for tier_key in ("tier_1", "tier_2", "tier_3", "tier_4"):
        for m in theme["causal_tree"].get(tier_key, []):
            expected_tickers.add(m["ticker"])

    # Masked store (excludes the theme under test)
    store = _MaskedStore(masked_id=tid)

    signals = _synthesise_signals(theme)
    candidates = signals_to_candidates(signals, min_anomaly=0.3)

    if not candidates:
        return BacktestCase(
            theme_id=tid, theme_name=theme["name"],
            recalled=False, grade="no_candidates",
            top_match_id=None, tier1_overlap=False,
            note="no candidates generated from synthetic signals",
        )

    # Use the most relevant candidate (highest anomaly_score in raw_signals)
    best_candidate = max(
        candidates,
        key=lambda c: (c["raw_signals"][0].get("anomaly_score") or 0.0),
    )

    # Enrich the candidate's trigger_summary with all synthesised signal keywords
    # so the RAG query is richer (the scout would normally inject these)
    extra_keywords = " ".join(_EXTRA_HINTS.get(tid, []))
    if extra_keywords:
        best_candidate = dict(best_candidate)
        best_candidate["trigger_summary"] = (
            best_candidate.get("trigger_summary", "") + " " + extra_keywords
        )

    verdict = review(best_candidate, store, mode="dry")
    grade = verdict.get("signal_grade", "reject")

    hist_matches = verdict.get("historical_match", [])
    top_match_id = hist_matches[0]["theme_id"] if hist_matches else None

    # Check ticker overlap between verdict tree (all tiers) and expected theme
    verdict_tickers: set[str] = set()
    for tier_key in ("tier_1", "tier_2", "tier_3", "tier_4"):
        for m in verdict.get("causal_tree", {}).get(tier_key, []):
            verdict_tickers.add(m.get("ticker", ""))
    tier1_overlap = bool(expected_tickers & verdict_tickers)

    # Hold-one-out: the correct theme is MASKED, so we can't check "found the right
    # theme". Honest recall = a non-rejected sibling analogue was surfaced. tier-1
    # ticker overlap is reported as a stricter sub-signal but not required.
    recalled = (grade != "reject")

    note_parts = [f"grade={grade}", f"top_match={top_match_id}"]
    if tier1_overlap:
        note_parts.append(f"ticker_overlap={expected_tickers & verdict_tickers}")

    return BacktestCase(
        theme_id=tid, theme_name=theme["name"],
        recalled=recalled, grade=grade,
        top_match_id=top_match_id, tier1_overlap=tier1_overlap,
        note="; ".join(note_parts),
    )


def run_recall_suite(theme_ids: list[str] | None = None) -> list[BacktestCase]:
    """Run backtest over all (or specified) deep-case themes."""
    all_themes = {t["id"]: t for t in load_themes()}
    ids = theme_ids or DEEP_CASE_IDS
    results: list[BacktestCase] = []
    for tid in ids:
        theme = all_themes.get(tid)
        if theme is None:
            results.append(BacktestCase(
                theme_id=tid, theme_name="?",
                recalled=False, grade="missing",
                top_match_id=None, tier1_overlap=False,
                note="theme_id not found in themes.json",
            ))
            continue
        results.append(run_backtest_case(theme))
    return results


def recall_at_k(k: int = 3) -> dict[str, Any]:
    """Pure-retrieval recall@k: fraction of deep cases where the correct theme
    is in the top-k RAG results (unmasked store — measures retrieval quality
    when the theme IS in the store but query has no direct id reference)."""
    all_themes = {t["id"]: t for t in load_themes()}
    store = ThemeStore()  # unmasked, fallback mode
    hits = 0
    details: list[dict[str, Any]] = []
    for tid in DEEP_CASE_IDS:
        theme = all_themes[tid]
        signals = _synthesise_signals(theme)
        # build query text similar to scout
        query = " ".join(
            s["content"].get("term", "") + " " + " ".join(s["content"].get("keywords", []))
            for s in signals
        ).strip()
        matches = store.query(query, n_results=k)
        found_ids = [m.to_dict()["id"] for m in matches]
        hit = tid in found_ids
        if hit:
            hits += 1
        details.append({"theme_id": tid, "hit": hit, "top_k": found_ids})
    return {"k": k, "hits": hits, "total": len(DEEP_CASE_IDS),
            "recall": hits / len(DEEP_CASE_IDS), "details": details}
