"""Scout candidate generation (heuristic, headless parity).

In the plugin, Scout is a Claude Haiku subagent. Here we provide a deterministic
heuristic that turns raw sensor signals into candidate themes, so the pipeline is
testable offline. High false-positive tolerance by design — Reviewer filters.

Two refinements:
- Friendly names: cross-market candidates show the Chinese theme name (from the
  history DB) instead of the raw theme id.
- Dedup: candidates for the same theme (e.g. AI from both NASDAQ and S&P500) are
  merged into one, combining their source signals and triggers.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _id_to_name() -> dict[str, str]:
    """Map history theme id -> friendly Chinese name."""
    try:
        from polydig_mcp.history.store import load_themes
        return {t["id"]: t.get("name", t["id"]) for t in load_themes()}
    except Exception:  # noqa: BLE001
        return {}


def _theme_name(theme_id: str) -> str:
    return _id_to_name().get(theme_id, theme_id)


def us_signal_to_tw_candidates(us_signal: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate a US sector-move signal into TW candidate themes (spec §4.2 item 5)."""
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
        name = _theme_name(family)
        candidates.append({
            "theme_hint": name,
            "trigger_summary": f"美股 {sector} {direction} {pct_str} → 預期 TW「{name}」族群跟漲滯後效應",
            "source": us_signal.get("source", "data.us_sector"),
            "raw_signals": [us_signal],
            "is_safety_net": False,
            "cross_market": True,
            "us_moves": [{"sector": sector, "pct_change": pct}],
            "tw_family": family,
            "dedup_key": f"theme:{family}",
        })
    return candidates


def _merge(into: dict[str, Any], other: dict[str, Any]) -> None:
    """Merge `other` candidate into `into` (same dedup_key)."""
    into["raw_signals"].extend(other.get("raw_signals", []))
    into["is_safety_net"] = into.get("is_safety_net") or other.get("is_safety_net")
    if other.get("cross_market"):
        into.setdefault("us_moves", []).extend(other.get("us_moves", []))


def _finalize_trigger(c: dict[str, Any]) -> None:
    """Rebuild a combined trigger for merged cross-market candidates."""
    moves = c.get("us_moves")
    if c.get("cross_market") and moves:
        seen: dict[str, float] = {}
        for m in moves:
            seen.setdefault(m["sector"], m["pct_change"])
        joined = "、".join(f"{s} {p * 100:+.1f}%" for s, p in seen.items())
        c["trigger_summary"] = f"美股聯動({joined}) → 預期 TW「{c['theme_hint']}」族群跟漲滯後效應"


def signals_to_candidates(
    sensor_signals: list[dict[str, Any]],
    min_anomaly: float = 0.3,
) -> list[dict[str, Any]]:
    """Promote anomalous signals into candidate themes, then dedup by theme."""
    raw: list[dict[str, Any]] = []
    for sig in sensor_signals:
        content = sig.get("content", {})
        if "error" in content:
            continue
        stype = sig.get("signal_type")
        score = sig.get("anomaly_score")

        if stype == "us_sector_move":
            raw.extend(us_signal_to_tw_candidates(sig))
            continue

        if stype == "limit_up_cluster":
            for industry, members in content.get("clusters", {}).items():
                raw.append({
                    "theme_hint": f"{industry}族群漲停潮",
                    "trigger_summary": f"{len(members)} 檔漲停 (safety-net,可能漏抓)",
                    "source": sig.get("source"),
                    "raw_signals": [sig],
                    "is_safety_net": True,
                    "dedup_key": f"cluster:{industry}",
                })
            continue

        # Freight (BDI shipping_index / SCFI news) → 航運 candidate (data-leads-price)
        if stype in ("scfi_signal", "shipping_index") and (score or 0) >= min_anomaly:
            idx = content.get("index", "運價")
            extra = (f"連{content['streak']}升 " if content.get("streak") else "") + \
                    (f"+{content['pct_move']}% " if content.get("pct_move") else "")
            raw.append({
                "theme_hint": _theme_name("shipping_2020"),  # 航運三雄(貨櫃)
                "trigger_summary": f"{idx} 運價{content.get('direction','異常')} {extra}→ 航運族群領先訊號",
                "source": sig.get("source"),
                "raw_signals": [sig],
                "is_safety_net": False,
                "dedup_key": "theme:shipping_2020",
            })
            continue

        if score is None or score < min_anomaly:
            continue

        hint = (
            content.get("term") or content.get("keyword") or content.get("commodity")
            or content.get("symbol") or content.get("proxy_for") or stype
        )
        raw.append({
            "theme_hint": str(hint),
            "trigger_summary": f"{stype} anomaly_score={score}",
            "source": sig.get("source"),
            "raw_signals": [sig],
            "is_safety_net": False,
            "dedup_key": f"hint:{hint}",
        })

    # ── dedup pass: merge candidates sharing a dedup_key ─────────────────────
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for c in raw:
        key = c.get("dedup_key", c["theme_hint"])
        if key in merged:
            _merge(merged[key], c)
        else:
            merged[key] = c
            order.append(key)

    out = [merged[k] for k in order]
    for c in out:
        _finalize_trigger(c)
        c.pop("dedup_key", None)
    return out
