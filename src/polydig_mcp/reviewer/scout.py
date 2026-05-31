"""Scout candidate generation (heuristic, headless parity).

In the plugin, Scout is a Claude Haiku subagent. Here we provide a deterministic
heuristic that turns raw sensor signals into candidate themes, so the pipeline is
testable offline. High false-positive tolerance by design — Reviewer filters.
"""
from __future__ import annotations

from typing import Any


def us_signal_to_tw_candidates(
    us_signal: dict[str, Any],
) -> list[dict[str, Any]]:
    """Translate a US sector-move signal into TW candidate themes (spec §4.2 item 5).

    A strong US-sector move (|pct_change| >= threshold) is translated into one
    TW candidate per mapped TW family. The Scout would call this when processing
    a ``us_sector_move`` signal.
    """
    content = us_signal.get("content", {})
    if "error" in content:
        return []

    pct = content.get("pct_change")
    if pct is None:
        return []

    try:
        from polydig_mcp.data.macro import US_STRONG_MOVE_THRESHOLD
    except ImportError:
        US_STRONG_MOVE_THRESHOLD = 0.05

    if abs(pct) < US_STRONG_MOVE_THRESHOLD:
        return []

    sector = content.get("sector", "")
    tw_families: list[str] = content.get("tw_theme_families", [])
    direction = "大漲" if pct > 0 else "大跌"
    pct_str = f"{pct * 100:+.1f}%"
    candidates: list[dict[str, Any]] = []
    for family in tw_families:
        candidates.append(
            {
                "theme_hint": f"{family} (US跨市聯動:{sector} {pct_str})",
                "trigger_summary": (
                    f"US {sector} {direction} {pct_str} → "
                    f"預期TW {family} 族群跟漲滯後效應"
                ),
                "source": us_signal.get("source", "data.us_sector"),
                "raw_signals": [us_signal],
                "is_safety_net": False,
                "cross_market": True,
                "us_sector": sector,
                "us_pct_change": pct,
                "tw_family": family,
            }
        )
    return candidates


def signals_to_candidates(
    sensor_signals: list[dict[str, Any]],
    min_anomaly: float = 0.3,
) -> list[dict[str, Any]]:
    """Promote anomalous signals into candidate themes.

    A candidate = one notable signal (anomaly_score >= min_anomaly) turned into a
    {theme_hint, trigger_summary, source, raw_signals} record the Reviewer can chew on.
    Limit-up clusters (price safety net) always become candidates.
    """
    candidates: list[dict[str, Any]] = []
    for sig in sensor_signals:
        content = sig.get("content", {})
        if "error" in content:
            continue
        stype = sig.get("signal_type")
        score = sig.get("anomaly_score")

        # Cross-market: US sector move → TW candidate families
        if stype == "us_sector_move":
            candidates.extend(us_signal_to_tw_candidates(sig))
            continue

        if stype == "limit_up_cluster":
            for industry, members in content.get("clusters", {}).items():
                candidates.append(
                    {
                        "theme_hint": f"{industry}族群漲停潮",
                        "trigger_summary": f"{len(members)} 檔漲停 (safety-net,可能漏抓)",
                        "source": sig.get("source"),
                        "raw_signals": [sig],
                        "is_safety_net": True,
                    }
                )
            continue

        if score is None or score < min_anomaly:
            continue

        hint = (
            content.get("term")
            or content.get("keyword")
            or content.get("commodity")
            or content.get("symbol")
            or content.get("proxy_for")
            or stype
        )
        candidates.append(
            {
                "theme_hint": str(hint),
                "trigger_summary": f"{stype} anomaly_score={score}",
                "source": sig.get("source"),
                "raw_signals": [sig],
                "is_safety_net": False,
            }
        )
    return candidates
