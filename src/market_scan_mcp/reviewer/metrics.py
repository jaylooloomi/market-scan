"""Operational success metrics (design spec §10), computed from the persisted DB.

Spec §10 targets this system committed to but never had code to measure:
  - 每日強訊號數量 0–5（雜訊控制）          → signal_volume()  [fully offline, works today]
  - 月命中率：推薦後 90 天漲 ≥20% 的比例 ≥30% → hit_rate()       [needs forward prices]
  - 領先性：報告日 → 族群明顯啟動日 平均 ≥14 天 → (needs a labelled 啟動日; out of scope here)

This module is the MEASUREMENT apparatus. The live data itself accrues by running
`market-scan-daily --db ./market-scan.db` daily over time — that part cannot be fast-forwarded.
`signal_volume` works against any populated DB right now; `hit_rate` takes an injectable
forward-return callable so it is testable offline and pluggable to FinMind / yfinance in
production (e.g. reuse market_scan_validator.excess_return).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Callable, Optional

# forward_return(ticker, since_date_iso, horizon_days) -> return as decimal, or None
ForwardReturn = Callable[[str, str, int], Optional[float]]


def signal_volume(verdicts: list[dict[str, Any]], noise_target: int = 5) -> dict[str, Any]:
    """Per-date grade counts + noise-control check (spec §10: daily strong ≤ 5).

    `verdicts` is the output of MarketScanDB.query_verdicts (each has date + grade).
    """
    by_date: dict[str, Counter] = defaultdict(Counter)
    for v in verdicts:
        by_date[v.get("date", "?")][v.get("grade", "reject")] += 1
    days = sorted(by_date)
    strong_per_day = {d: by_date[d].get("strong", 0) for d in days}
    over = [d for d, n in strong_per_day.items() if n > noise_target]
    totals: Counter = Counter()
    for c in by_date.values():
        totals.update(c)
    return {
        "days_observed": len(days),
        "grade_totals": dict(totals),
        "max_daily_strong": max(strong_per_day.values(), default=0),
        "avg_daily_strong": round(sum(strong_per_day.values()) / len(days), 2) if days else 0,
        "noise_target": noise_target,
        "days_over_noise_target": over,
        "noise_ok": not over,
    }


def hit_rate(
    verdicts: list[dict[str, Any]],
    forward_return: ForwardReturn,
    *,
    horizon_days: int = 90,
    hit_threshold: float = 0.20,
    grades: tuple[str, ...] = ("strong",),
) -> dict[str, Any]:
    """Spec §10 月命中率: a graded verdict 'hits' if the mean forward return of its
    tier-1 tickers over `horizon_days` ≥ `hit_threshold`. Target hit_rate ≥ 0.30.

    forward_return(ticker, since_date, days) supplies the price outcome (inject a
    real source in prod; a fake in tests). Verdicts whose tickers all return None
    (no price data) are skipped, not counted as misses.
    """
    scored: list[dict[str, Any]] = []
    for v in verdicts:
        if v.get("grade") not in grades:
            continue
        full = v.get("verdict", {}) or {}
        tier_1 = full.get("causal_tree", {}).get("tier_1", [])
        since = v.get("date")
        rets = [
            r for m in tier_1
            if (r := forward_return(m.get("ticker", ""), since, horizon_days)) is not None
        ]
        if not rets:
            continue
        mean_ret = sum(rets) / len(rets)
        scored.append({
            "theme": v.get("theme"), "date": since,
            "mean_tier1_forward_return": round(mean_ret, 4),
            "hit": mean_ret >= hit_threshold,
        })
    hits = sum(1 for s in scored if s["hit"])
    rate = (hits / len(scored)) if scored else None
    return {
        "scored": len(scored),
        "hits": hits,
        "hit_rate": round(rate, 4) if rate is not None else None,
        "horizon_days": horizon_days,
        "hit_threshold": hit_threshold,
        "target": 0.30,
        "meets_target": (rate >= 0.30) if rate is not None else None,
        "detail": scored,
    }


def compute_metrics(
    db: Any,
    *,
    forward_return: ForwardReturn | None = None,
    **hit_kwargs: Any,
) -> dict[str, Any]:
    """Compute the spec §10 dashboard from a MarketScanDB. `signal_volume` always runs;
    `hit_rate` runs only if a `forward_return` callable is supplied."""
    verdicts = db.query_verdicts(limit=1_000_000)
    out: dict[str, Any] = {"verdicts_observed": len(verdicts), "signal_volume": signal_volume(verdicts)}
    if forward_return is not None:
        out["hit_rate"] = hit_rate(verdicts, forward_return, **hit_kwargs)
    else:
        out["hit_rate"] = {
            "status": "needs forward prices — pass forward_return (FinMind/yfinance) "
                      "or measure after ≥1 quarter of daily --db runs accrues outcomes",
        }
    return out


def finmind_forward_return(
    ticker: str, since_date_iso: str, days: int, *, query: Any = None
) -> Optional[float]:
    """Forward return of `ticker` over ~`days` calendar days from since_date, via FinMind.

    Returns (close_on/after_target / first_close - 1.0), or None if unavailable.
    `query` is injectable for testing; defaults to market_scan_mcp.data.finmind.query
    (which needs FINMIND_TOKEN). Returns None gracefully on any failure so hit_rate
    stays robust. FinMind uses bare TW codes (no .TW/.TWO), matching stored tickers.
    """
    from datetime import date as _date
    from datetime import timedelta

    if query is None:
        from market_scan_mcp.data import finmind
        query = finmind.query
    try:
        start = since_date_iso
        end = (_date.fromisoformat(since_date_iso) + timedelta(days=days + 14)).isoformat()
        rows = query("price", ticker, start, end)
    except Exception:
        return None
    pts = sorted(
        (r["date"], r["close"]) for r in rows
        if r.get("date") and r.get("close") is not None
    )
    if len(pts) < 2:
        return None
    first_close = pts[0][1]
    target = (_date.fromisoformat(since_date_iso) + timedelta(days=days)).isoformat()
    on_or_after = [c for d, c in pts if d >= target]
    last_close = on_or_after[0] if on_or_after else pts[-1][1]
    return (last_close / first_close - 1.0) if first_close else None


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys

    p = argparse.ArgumentParser(description="Market Scan spec §10 operational metrics (from SQLite)")
    p.add_argument("--db", default="market-scan.db", help="SQLite db written by market-scan-daily --db")
    p.add_argument("--prices", choices=["none", "finmind"], default="none",
                   help="forward-price source for hit_rate (finmind needs FINMIND_TOKEN)")
    p.add_argument("--horizon", type=int, default=90, help="hit_rate horizon in days (spec §10: 90)")
    args = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from market_scan_mcp.storage.db import MarketScanDB

    fwd = finmind_forward_return if args.prices == "finmind" else None
    db = MarketScanDB(args.db)
    metrics = compute_metrics(db, forward_return=fwd, horizon_days=args.horizon)
    db.close()
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
