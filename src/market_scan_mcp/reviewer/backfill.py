"""Missed-catch backfill + negative-sample learning loop (spec §6.5).

When a price limit-up cluster fires (safety-net candidate), this module
runs a backfill investigation:
1. Query storage signals/term_history for trailing 30-90 days.
2. Find leading signals that were present but not promoted.
3. Produce a "missed-catch" record explaining why.
4. If no prior signal found → mark "no fundamental basis (likely retail-driven)".

Rejected verdicts are persisted to the `verdicts` table as negative samples
(grade=reject) by the pipeline automatically (via storage wiring in pipeline.py).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from market_scan_mcp.storage.db import MarketScanDB

# How many days back to search for leading signals
BACKFILL_LOOKBACK_DAYS = 90
# Minimum anomaly_score to consider a prior signal "notable"
MIN_PRIOR_ANOMALY = 0.3


def run_backfill(
    industry: str,
    members: list[dict[str, Any]],
    db: "MarketScanDB",
    lookback_days: int = BACKFILL_LOOKBACK_DAYS,
) -> dict[str, Any]:
    """Run backfill investigation for a price-cluster miss.

    Parameters
    ----------
    industry:
        Industry / theme label (e.g. "半導體").
    members:
        List of stock members in the cluster (dicts with 'code'/'name').
    db:
        Open MarketScanDB instance to query prior signals and term history.
    lookback_days:
        How many days back to search.

    Returns
    -------
    A backfill findings dict:
        {
          "industry": str,
          "lookback_days": int,
          "leading_signals": [list of prior signals found],
          "leading_terms": [list of prior news terms found],
          "conclusion": str,
          "reason_missed": str,
        }
    """
    since = (date.today() - timedelta(days=lookback_days)).isoformat()
    member_names = [m.get("name", m.get("code", "?")) for m in members]

    # ── 1. Search prior signals by keyword overlap ────────────────────────
    leading_signals: list[dict[str, Any]] = []

    # Query all signals in the window
    prior_signals = db.query_signals(since=since, limit=500)

    # Score each prior signal for relevance to the industry/members
    industry_tokens = _tokenise(industry)
    member_tokens: set[str] = set()
    for name in member_names:
        member_tokens |= _tokenise(name)

    for sig in prior_signals:
        content = sig.get("content", {})
        if "error" in content:
            continue
        score = sig.get("anomaly_score") or 0.0
        if score < MIN_PRIOR_ANOMALY:
            continue
        # Check keyword overlap with content text
        content_text = _content_to_text(content)
        sig_tokens = _tokenise(content_text)
        overlap = (industry_tokens | member_tokens) & sig_tokens
        if overlap:
            leading_signals.append({
                "source": sig["source"],
                "signal_type": sig["signal_type"],
                "timestamp": sig["timestamp"],
                "anomaly_score": score,
                "matched_tokens": sorted(overlap),
                "content_preview": content_text[:200],
            })

    # ── 2. Search term_history baselines ─────────────────────────────────
    leading_terms: list[dict[str, Any]] = []
    for term_kw in list(industry_tokens | member_tokens):
        if len(term_kw) < 2:
            continue
        baseline = db.term_baseline(term_kw, "news.anomaly", lookback_days=lookback_days)
        if baseline > 0:
            leading_terms.append({
                "term": term_kw,
                "avg_daily_count": round(baseline, 2),
                "source": "news.anomaly",
            })

    # ── 3. Build conclusion ───────────────────────────────────────────────
    if leading_signals or leading_terms:
        conclusion = "found_leading_signals"
        reason_missed = (
            f"發現 {len(leading_signals)} 個前期訊號 + {len(leading_terms)} 個新聞詞彙趨勢，"
            "但未被 Scout 提升為候選主題。建議調低 min_anomaly 閾值或增加跨源關聯偵測。"
        )
    else:
        conclusion = "no_fundamental_basis"
        reason_missed = (
            f"回溯 {lookback_days} 天未找到相關領先訊號。"
            "該族群可能為純散戶炒作，無基本面支撐 (likely retail-driven)。"
        )

    return {
        "industry": industry,
        "members": member_names,
        "lookback_days": lookback_days,
        "leading_signals": leading_signals,
        "leading_terms": leading_terms,
        "conclusion": conclusion,
        "reason_missed": reason_missed,
    }


# ── helpers ──────────────────────────────────────────────────────────────────

import re as _re

_CJK = _re.compile(r"[一-鿿]+")
_LATIN = _re.compile(r"[A-Za-z0-9]{2,}")


def _tokenise(text: str) -> set[str]:
    """CJK bigram + Latin word tokeniser (same as store.py)."""
    out = {t.lower() for t in _LATIN.findall(text)}
    for run in _CJK.findall(text):
        if len(run) == 1:
            out.add(run)
        else:
            out.update(run[i : i + 2] for i in range(len(run) - 1))
    return out


def _content_to_text(content: dict[str, Any]) -> str:
    """Flatten a signal content dict to a single searchable string."""
    parts: list[str] = []
    for v in content.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(x) for x in v)
    return " ".join(parts)
