"""Freight-index anomaly detection (SCFI/BDI) — the "data leads price" sensor.

Shipping is the canonical case where the freight rate rises *before* the stock
(長榮/陽明/萬海) does. So this watches the index series itself, not news.

Data-source reality (honest): SCFI (sse.net.cn) is behind a login and BDI
(Baltic Exchange) is paywalled — there is no keyless live feed. So values are
fed into SQLite `index_history` via `ingest_shipping_index` (manual weekly entry,
or a future authenticated/paid source), and the anomaly is computed over the
stored series. The detection below is the valuable, source-agnostic part.

"Anomaly" is RELATIVE to the index's own recent history, combining:
  1. streak    — consecutive rising periods (SCFI is weekly → 連 3-4 週上漲)
  2. magnitude — cumulative % change over the trailing window (案例書: 連 4 週 ≥20%)
  3. z-score   — how many std devs the latest value sits above its trailing mean
A single small wobble won't fire; a sustained, large, unusual rise will.
"""
from __future__ import annotations

import statistics
from typing import Any

from polydig_mcp.common.errors import SensorError
from polydig_mcp.common.http import polite_get

# East Money (东方财富) datacenter — free JSON API with date+value history.
# Free dry-bulk freight complex (all confirmed). Container (SCFI/CCFI) has NO
# keyless source — sse.net.cn login-gated, MacroMicro behind Cloudflare,
# Freightos/sina/cnyes no clean API — so SCFI uses ingest_shipping_index.
_EASTMONEY_API = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EASTMONEY_INDICATORS = {
    "BDI": "EMI00107664",   # 波羅的海乾散貨綜合指數 (dry bulk — 慧洋/裕民/新興)
    "BPI": "EMI00107665",   # 巴拿馬型運費指數
    "BCI": "EMI00107666",   # 海岬型運費指數
    "BSI": "EMI00107667",   # 超靈便型船運價指數
}


def fetch_eastmoney_index(name: str, limit: int = 120) -> list[tuple[str, float]]:
    """Fetch [(date, value)] history for a freight index from East Money (free).

    Raises SensorError if the index isn't mapped or the API fails.
    """
    ind_id = EASTMONEY_INDICATORS.get(name.upper())
    if not ind_id:
        raise SensorError("unknown_index", f"{name} has no East Money id (try ingest_shipping_index)")
    params = {
        "reportName": "RPT_INDUSTRY_INDEX",
        "columns": "REPORT_DATE,INDICATOR_VALUE",
        "filter": f'(INDICATOR_ID="{ind_id}")',
        "pageSize": str(limit),
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
    }
    resp = polite_get(_EASTMONEY_API, params=params)
    rows = ((resp.json() or {}).get("result") or {}).get("data") or []
    series: list[tuple[str, float]] = []
    for r in rows:
        d = (r.get("REPORT_DATE") or "")[:10]
        v = r.get("INDICATOR_VALUE")
        if d and v is not None:
            series.append((d, float(v)))
    if not series:
        raise SensorError("fetch_failed", f"East Money returned no data for {name}")
    series.sort(key=lambda x: x[0])  # ascending
    return series


# ── SCFI (container) via free news (numeric index is login-gated) ────────────
# Google News RSS is free + reliable + requests-based (stdio-safe). It can't give
# the exact composite (that's gated), but it reliably gives DIRECTION + magnitude
# (連N升 / 大漲15% / 連三漲) — which IS the leading signal for 長榮/陽明/萬海.
_SCFI_NEWS_RSS = (
    "https://news.google.com/rss/search?q=SCFI%20%E9%81%8B%E5%83%B9%E6%8C%87%E6%95%B8"
    "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
)
_RISE_KW = ["升", "漲", "飆", "紅", "彈", "揚", "走高", "走揚", "創高", "噴"]
_FALL_KW = ["跌", "降", "落", "黑", "走弱", "回落", "下滑", "崩"]
_PCT_RE = __import__("re").compile(r"(\d+(?:\.\d+)?)\s*[%％]")
_PT_RE = __import__("re").compile(r"(\d{3,4}(?:\.\d+)?)\s*點")
_STREAK_RE = __import__("re").compile(r"連(\d+|[一二三四五六七八九十]+)(?:周|週|日|升|漲|紅|黑)")


def fetch_scfi_news_signal(max_items: int = 8) -> dict[str, Any]:
    """Free SCFI direction/momentum signal from Google News RSS headlines.

    Returns rise/fall counts, any magnitude (% or 點), recent headlines+links,
    and an anomaly_score that's high when SCFI is in a sustained rise. Raises
    SensorError on fetch failure.
    """
    import html as _html
    import re as _re

    import feedparser

    parsed = feedparser.parse(_SCFI_NEWS_RSS)
    if parsed.bozo and not parsed.entries:
        raise SensorError("fetch_failed", f"SCFI news RSS unavailable: {getattr(parsed,'bozo_exception','?')}")

    rise = fall = 0
    pct = pts = None
    streak = 0
    headlines: list[dict[str, Any]] = []
    for e in parsed.entries[:max_items]:
        title = _html.unescape(e.get("title", ""))
        if "SCFI" not in title.upper() and "運價" not in title and "运价" not in title:
            continue
        r_hit = sum(title.count(k) for k in _RISE_KW)
        f_hit = sum(title.count(k) for k in _FALL_KW)
        rise += 1 if r_hit > f_hit else 0
        fall += 1 if f_hit > r_hit else 0
        if pct is None and (m := _PCT_RE.search(title)):
            pct = float(m.group(1))
        if pts is None and (m := _PT_RE.search(title)):
            pts = float(m.group(1))
        if (m := _STREAK_RE.search(title)):
            g = m.group(1)
            cn = int(g) if g.isdigit() else "一二三四五六七八九十".find(g[0]) + 1
            streak = max(streak, cn)
        headlines.append({"title": title, "link": e.get("link")})

    if not headlines:
        raise SensorError("no_data", "no SCFI headlines found in news RSS")

    direction = "rising" if rise > fall else ("falling" if fall > rise else "mixed")
    # score: rising consensus + sustained streak + magnitude
    score = 0.0
    if direction == "rising":
        score = min(1.0, 0.4 + 0.1 * rise + 0.1 * streak + (0.2 if (pct and pct >= 5) else 0))
    return {
        "index": "SCFI",
        "direction": direction,
        "rise_headlines": rise,
        "fall_headlines": fall,
        "streak": streak,
        "pct_move": pct,
        "points": pts,
        "anomaly_score": round(score, 3),
        "headlines": headlines[:5],
        "note": "SCFI numeric index is login-gated; this is a free news-derived "
                "direction/momentum signal (Google News RSS).",
    }


def detect_index_anomaly(
    series: list[tuple[str, float]],
    window: int = 8,
    momentum_periods: int = 4,
    momentum_target: float = 0.20,
) -> dict[str, Any]:
    """Score how anomalous the latest reading is vs the index's own history.

    series: [(date, value)] ascending. Returns metrics + anomaly_score (0..1).
    """
    if len(series) < 3:
        return {"anomaly_score": 0.0, "reason": "insufficient history (<3 points)",
                "points": len(series)}

    values = [v for _, v in series]
    latest = values[-1]

    # 1. streak: trailing consecutive rises
    streak = 0
    for i in range(len(values) - 1, 0, -1):
        if values[i] > values[i - 1]:
            streak += 1
        else:
            break

    # 2. magnitude: cumulative change over the trailing momentum_periods
    k = min(momentum_periods, len(values) - 1)
    base = values[-1 - k]
    cum_change = (latest / base - 1.0) if base else 0.0

    # 3. z-score vs trailing window (exclude the latest point from the baseline)
    win = values[-(window + 1):-1] if len(values) > window else values[:-1]
    if len(win) >= 2:
        mu = statistics.mean(win)
        sd = statistics.pstdev(win)
        z = (latest - mu) / sd if sd > 0 else 0.0
    else:
        z = 0.0

    # Only a *rising* index is interesting (data-leads-price is about upturns).
    if cum_change <= 0:
        score = 0.0
    else:
        momentum_score = min(1.0, cum_change / momentum_target)
        streak_score = min(1.0, streak / 4.0)
        z_norm = min(1.0, max(0.0, (z - 1.0) / 2.0))  # z=1→0, z=3→1
        score = max(momentum_score, 0.5 * streak_score + 0.5 * z_norm)

    hits = []
    if cum_change >= momentum_target:
        hits.append(f"{momentum_periods}期累積 {cum_change*100:.0f}% ≥ {momentum_target*100:.0f}%")
    if streak >= 3:
        hits.append(f"連 {streak} 期上漲")
    if z >= 2:
        hits.append(f"z={z:.1f}(顯著高於近期均值)")

    return {
        "latest": round(latest, 1),
        "points": len(series),
        "consecutive_up": streak,
        "cum_change": round(cum_change, 4),
        "momentum_periods": k,
        "zscore": round(z, 2),
        "anomaly_score": round(min(1.0, score), 3),
        "rule_hits": hits,
        "reason": "；".join(hits) if hits else "未達異常門檻",
    }
