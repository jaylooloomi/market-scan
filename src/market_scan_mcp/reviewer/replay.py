"""Real-news replay harness (MVP) — architect P0.

Feeds REAL historical daily news volume (GDELT) through the system's cross-week
anomaly formula (vol_conf damping + an absolute-volume floor) to answer: "on what
day would the sensor first fire on this event, and how many days ahead of
mainstream?" — the out-of-sample lead-time gross backtests can't show.

SCOPE (honest): this MVP uses GDELT DOC `TimelineVolRaw` (article volume for a
query) — NOT the full GKG ETL with a jieba-equivalent tokenizer (the ~2-week job
flagged in reports/optimization/01-architect-optimization.md §2). It measures
event *detectability + lead time* and lets you calibrate threshold/abs_floor on
real data. `replay_series` is PURE (offline-testable); `fetch_gdelt_volume` needs
network (GDELT asks for >=5s between calls).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from market_scan_mcp.news.sources import FULL_CONFIDENCE_COUNT


@dataclass
class ReplayPoint:
    day: date
    count: float
    baseline: float
    ratio: float
    score: float
    fire: bool


def replay_series(
    series: list[tuple[date, float]],
    *,
    threshold: float = 0.3,
    lookback: int = 21,
    abs_floor: float = 0,
    full_conf: float = FULL_CONFIDENCE_COUNT,
    min_count: int = 3,
) -> tuple[list[ReplayPoint], date | None]:
    """Apply the cross-week + vol_conf formula day-by-day over a real volume series.

    series: [(date, count)] ascending. Returns (points, first_fire_date | None).
    A day fires iff count >= max(min_count, abs_floor) AND score >= threshold,
    where score = min(1, ratio/5) * min(1, count/full_conf) and
    ratio = count / (trailing-`lookback`-day mean + 1). The absolute floor is what
    stops a tiny-count ratio off a ~0 baseline from false-firing (GDELT 2019-11).
    """
    counts = [c for _, c in series]
    floor = max(min_count, abs_floor)
    points: list[ReplayPoint] = []
    first_fire: date | None = None
    for i, (d, c) in enumerate(series):
        window = counts[max(0, i - lookback):i]
        baseline = sum(window) / len(window) if window else 0.0
        ratio = c / (baseline + 1.0)
        vol_conf = min(1.0, c / full_conf)
        score = min(1.0, ratio / 5.0) * vol_conf
        fire = (c >= floor) and (score >= threshold)
        if fire and first_fire is None:
            first_fire = d
        points.append(ReplayPoint(d, c, round(baseline, 2), round(ratio, 2), round(score, 3), fire))
    return points, first_fire


def fetch_gdelt_volume(query: str, start: date, end: date) -> list[tuple[date, float]]:
    """[(date, count)] daily article volume from GDELT DOC TimelineVolRaw.

    Network; sleeps 6s to respect GDELT's 1-request/5s limit.
    """
    import time

    import requests

    time.sleep(6)
    resp = requests.get(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        params={
            "query": query,
            "mode": "timelinevolraw",
            "startdatetime": start.strftime("%Y%m%d000000"),
            "enddatetime": end.strftime("%Y%m%d000000"),
            "format": "json",
        },
        timeout=40,
        headers={"User-Agent": "market-scan-replay/0.1"},
    )
    data = (resp.json().get("timeline") or [{}])[0].get("data", [])
    out = [(datetime.strptime(p["date"][:8], "%Y%m%d").date(), float(p["value"])) for p in data]
    out.sort()
    return out


def replay_event(
    query: str,
    event_date: date,
    mainstream_date: date,
    *,
    abs_floor: float = 30,
    threshold: float = 0.3,
) -> dict[str, Any]:
    """Fetch + replay one event; return first_fire + lead-days vs mainstream."""
    series = fetch_gdelt_volume(query, event_date - timedelta(days=60), mainstream_date + timedelta(days=40))
    points, first_fire = replay_series(series, threshold=threshold, abs_floor=abs_floor)
    lead = (mainstream_date - first_fire).days if first_fire else None
    return {
        "query": query,
        "event_date": event_date.isoformat(),
        "mainstream_date": mainstream_date.isoformat(),
        "first_fire": first_fire.isoformat() if first_fire else None,
        "lead_days": lead,
        "points": len(series),
        "fires": sum(p.fire for p in points),
        "abs_floor": abs_floor,
    }


def main() -> int:
    """Demo: replay COVID/Wuhan-pneumonia and print lead time."""
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    res = replay_event("Wuhan pneumonia", date(2019, 12, 31), date(2020, 1, 20), abs_floor=30)
    print("Market Scan replay —", res["query"])
    print(f"  first fire: {res['first_fire']}  (abs_floor={res['abs_floor']}, {res['fires']} fire-days / {res['points']} days)")
    print(f"  vs mainstream {res['mainstream_date']}: lead = {res['lead_days']} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
