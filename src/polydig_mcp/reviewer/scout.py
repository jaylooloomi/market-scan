"""Scout candidate generation (heuristic, headless parity).

In the plugin, Scout is a Claude Haiku subagent. Here we provide a deterministic
heuristic that turns raw sensor signals into candidate themes, so the pipeline is
testable offline. High false-positive tolerance by design — Reviewer filters.
"""
from __future__ import annotations

from typing import Any


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
