"""Crash-watch sensor — risk-off confluence from FRED structural-stress indicators.

Downside North Star (see docs/research/02-crash-precursors.md): crashes lead in
DATA / credit / funding markets, not in headlines. This watches a few keyless FRED
series and fires a 'risk_off confluence' ONLY when MULTIPLE indicators are stressed
at once — a deliberately high bar to suppress false positives (e.g. the 2022-23
yield-curve inversion that produced no recession by 2026).

⚠️ This is a CAUTION / de-risk signal, NOT a crash predictor. The confluence
threshold is a PARAMETER that must be calibrated out-of-sample (replay harness),
not treated as gospel. Same requests-based FRED path as macro.py (no new deps).
"""
from __future__ import annotations

from typing import Any

from polydig_mcp.data.macro import _fred_series  # keyless FRED CSV fetch (reused)

# Keyless FRED series (daily). value units noted.
CRASHWATCH_SERIES = {
    "yield_curve_10y3m": "T10Y3M",   # 10yr−3mo, % ; <0 = inverted (LEADING, months)
    "hy_oas": "BAMLH0A0HYM2",        # ICE BofA US HY OAS, % ; widening = stress (LEADING, wks-mo)
    "vix": "VIXCLS",                 # CBOE VIX spot, index pts ; elevated = stress (COINCIDENT)
}


def assess_indicators(
    yc: float | None,
    hy_latest: float | None,
    hy_min: float | None,
    vix: float | None,
    *,
    hy_abs: float = 5.0,       # HY OAS >= 5.0% (500bps) = elevated
    hy_widen: float = 1.0,     # HY OAS up >= 1.0% (100bps) off its window low = widening
    vix_level: float = 25.0,   # VIX spot >= 25 = elevated
) -> dict[str, Any]:
    """Pure: map raw readings → per-indicator {stressed, value, lead}. None inputs skipped."""
    ind: dict[str, Any] = {}
    if yc is not None:
        ind["yield_curve_inverted"] = {
            "stressed": yc < 0, "value": round(yc, 2), "lead": "leading(月)",
            "note": "倒掛;2022-23 曾長期假陽性,單獨不足",
        }
    if hy_latest is not None:
        widen = (hy_min is not None) and (hy_latest - hy_min >= hy_widen)
        ind["credit_spread_stress"] = {
            "stressed": bool(hy_latest >= hy_abs or widen),
            "value": round(hy_latest, 2),
            "lead": "leading(週-月)",
            "note": f"HY OAS;>={hy_abs}% 或自窗內低點走闊 >={hy_widen}%",
        }
    if vix is not None:
        ind["vix_elevated"] = {
            "stressed": vix >= vix_level, "value": round(vix, 2),
            "lead": "coincident(確認,非領先)",
            "note": "VIX 現貨;期限結構 backwardation 才是領先,但 FRED keyless 取不到",
        }
    return ind


def assess_confluence(indicators: dict[str, Any], threshold: int = 2) -> dict[str, Any]:
    """Pure: count stressed indicators → state. `threshold` MUST be calibrated OOS."""
    stressed = [k for k, v in indicators.items() if v.get("stressed")]
    n, total = len(stressed), len(indicators)
    state = "risk_off" if n >= threshold else ("caution" if n >= 1 else "calm")
    return {
        "state": state,
        "n_stressed": n,
        "total": total,
        "stressed": stressed,
        "score": round(n / total, 3) if total else 0.0,
        "threshold": threshold,
    }


def crash_watch_signal(days: int = 120, threshold: int = 2) -> dict[str, Any]:
    """Fetch the FRED stress series and assess risk-off confluence.

    Returns confluence + per-indicator detail. Each FRED fetch failure degrades to
    a skipped indicator (None) rather than aborting; if ALL fail, SensorError bubbles.
    """
    series = {}
    for key, sid in CRASHWATCH_SERIES.items():
        try:
            series[key] = _fred_series(sid, days)
        except Exception:  # noqa: BLE001 — one dead series shouldn't kill the rest
            series[key] = []

    def latest(s):
        return s[-1][1] if s else None

    yc_s = series["yield_curve_10y3m"]
    hy_s = series["hy_oas"]
    vix_s = series["vix"]
    hy_min = min((v for _, v in hy_s), default=None)

    indicators = assess_indicators(latest(yc_s), latest(hy_s), hy_min, latest(vix_s))
    conf = assess_confluence(indicators, threshold=threshold)
    as_of = next((s[-1][0].isoformat() for s in (yc_s, hy_s, vix_s) if s), None)
    return {
        **conf,
        "indicators": indicators,
        "as_of": as_of,
        "note": "risk-off confluence — de-risk 訊號,非崩盤預測器;threshold 需 out-of-sample "
                "校準。見 docs/research/02-crash-precursors.md。",
    }
