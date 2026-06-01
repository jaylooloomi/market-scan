"""news-mcp MCP server.

Tools:
    list_sources()                         -> available RSS feeds
    fetch_news(source, since_days, query)  -> recent news items
    detect_news_anomaly(window_days, ...)  -> spiking terms (anomaly signals)
    google_trends_check(keyword, region)   -> search-interest trend
    fetch_ptt(board)                       -> STUB (anti-bot; Phase 5+)
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from polydig_mcp.common.envelope import Signal, error_signal, now_iso
from polydig_mcp.common.errors import SensorError
from polydig_mcp.news.sources import (
    FEEDS,
    FULL_CONFIDENCE_COUNT,
    Feed,
    detect_term_spikes,
    fetch_feed,
)

mcp = FastMCP("polydig-news")


def _selected_feeds(source: str | None) -> list[Feed]:
    if source is None:
        return list(FEEDS.values())
    if source in FEEDS:
        return [FEEDS[source]]
    # allow filtering by lang or category
    matches = [f for f in FEEDS.values() if source in (f.lang, f.category)]
    return matches


@mcp.tool()
def list_sources() -> list[dict[str, str]]:
    """List the news sources this sensor can read (RSS feeds)."""
    return [
        {"id": f.id, "name": f.name, "lang": f.lang, "category": f.category}
        for f in FEEDS.values()
    ]


@mcp.tool()
def fetch_news(
    source: str | None = None,
    since_days: float = 2.0,
    query: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch recent news items.

    Args:
        source: feed id (e.g. "udn-money"), or a lang ("zh"/"en"), or a
            category ("finance"/"technology"). None = all feeds.
        since_days: only items published within this many days (best-effort;
            items without a date are always included).
        query: optional case-insensitive substring filter on title+summary.
        limit: max items returned.
    """
    feeds = _selected_feeds(source)
    if not feeds:
        return [error_signal("news", "news_fetch", f"no feed matches source={source!r}")]

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    for feed in feeds:
        try:
            items = fetch_feed(feed)
        except SensorError as e:
            out.append(error_signal("news." + feed.id, "news_fetch", e.message))
            continue
        for it in items:
            dt = it.pop("_dt", None)
            if dt is not None and (now - dt).total_seconds() > since_days * 86400:
                continue
            if query and query.lower() not in f"{it['title']} {it['summary']}".lower():
                continue
            out.append(
                Signal(
                    source="news." + it["source"],
                    signal_type="news_item",
                    content={
                        "title": it["title"],
                        "summary": it["summary"],
                        "source_name": it["source_name"],
                        "lang": it["lang"],
                        "published": it["published"],
                    },
                    raw_url=it["link"],
                    anomaly_score=None,
                ).to_dict()
            )
    return out[:limit]


@mcp.tool()
def detect_news_anomaly(
    window_days: float = 1.0,
    threshold: float = 0.3,
    min_recent_count: int = 3,
    source: str | None = None,
    max_terms: int = 30,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Detect terms spiking in recent news.

    Two modes:
    - Default: compares recent vs preceding period WITHIN the feed's available
      window (a few days).
    - With `db_path`: also computes a true CROSS-WEEK baseline — today's term
      count vs the mean daily count over the trailing 21 days (persisted in
      SQLite). The reported anomaly_score is the max of the within-window and
      cross-week scores, so a slow build-up over weeks is caught too. Today's
      counts are persisted for future baselines (builds up over daily runs).

    `min_recent_count` is the per-source ABSOLUTE-VOLUME floor: a term must appear
    at least this many times in the window to be a candidate at all (applied to
    both the within-window and cross-week paths). Default 3 suits RSS (the Scout is
    high-false-positive-tolerant by design); raise it for high-volume / aggregated
    sources — calibrate via the replay harness (`reviewer/replay.py`), which is
    where the GDELT-scale floor (abs_floor) lives.
    """
    feeds = _selected_feeds(source)
    if not feeds:
        return [error_signal("news", "news_anomaly", f"no feed matches source={source!r}")]

    all_items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for feed in feeds:
        try:
            all_items.extend(fetch_feed(feed))
        except SensorError as e:
            errors.append(error_signal("news." + feed.id, "news_anomaly", e.message))

    spikes = detect_term_spikes(all_items, window_days=window_days, min_recent_count=min_recent_count)

    # Optional cross-week baseline via the SQLite term_history store.
    db = None
    today = None
    if db_path:
        try:
            from datetime import date as _date

            from polydig_mcp.storage.db import PolyDigDB

            db = PolyDigDB(db_path)
            today = _date.today().isoformat()
        except Exception:  # noqa: BLE001 — storage optional, never abort detection
            db = None

    signals: list[dict[str, Any]] = []
    for s in spikes:
        score = s["anomaly_score"]
        cross_week_ratio = None
        if db is not None:
            try:
                baseline = db.term_baseline(s["term"], "news", lookback_days=21)
                cross_week_ratio = s["recent_count"] / (baseline + 1)
                cw_vol_conf = min(1.0, s["recent_count"] / FULL_CONFIDENCE_COUNT)
                cross_week_score = min(1.0, cross_week_ratio / 5.0) * cw_vol_conf
                score = max(score, cross_week_score)
                db.upsert_term_count(today, s["term"], s["recent_count"], "news")
            except Exception:  # noqa: BLE001
                pass
        if score < threshold:
            continue
        content = {
            "term": s["term"],
            "recent_count": s["recent_count"],
            "prior_count": s["prior_count"],
            "spike_ratio": s["spike_ratio"],
            "window_days": window_days,
            "article_urls": s.get("article_urls", []),
        }
        if cross_week_ratio is not None:
            content["cross_week_ratio"] = round(cross_week_ratio, 2)
        signals.append(
            Signal(
                source="news.anomaly",
                signal_type="news_anomaly",
                content=content,
                raw_url=s["example_url"],
                anomaly_score=round(score, 3),
            ).to_dict()
        )
        if len(signals) >= max_terms:
            break

    if db is not None:
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass
    return signals + errors


@mcp.tool()
def google_trends_check(
    keyword: str,
    region: str = "TW",
    timeframe: str = "now 7-d",
) -> dict[str, Any]:
    """Check Google search-interest trend for a keyword (via pytrends).

    Google Trends has no official API; pytrends scrapes it and is rate-limited
    (HTTP 429). On failure this returns a structured error signal, not a crash.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return error_signal("news.gtrends", "google_trends", "pytrends not installed")

    try:
        pt = TrendReq(hl="zh-TW", tz=-480)
        pt.build_payload([keyword], geo=region, timeframe=timeframe)
        df = pt.interest_over_time()
    except Exception as e:  # pytrends raises many ad-hoc error types
        return error_signal(
            "news.gtrends", "google_trends",
            f"pytrends query failed (often rate-limit/429): {e}", keyword=keyword,
        )

    if df is None or df.empty or keyword not in df.columns:
        return error_signal("news.gtrends", "google_trends", "no trend data", keyword=keyword)

    series = df[keyword].tolist()
    recent = series[-1] if series else 0
    baseline = (sum(series[:-1]) / len(series[:-1])) if len(series) > 1 else recent
    rising_ratio = (recent / baseline) if baseline else None
    score = None if rising_ratio is None else min(1.0, max(0.0, (rising_ratio - 1.0)))

    return Signal(
        source="news.gtrends",
        signal_type="google_trends",
        content={
            "keyword": keyword,
            "region": region,
            "timeframe": timeframe,
            "latest_interest": int(recent),
            "baseline_interest": round(baseline, 1),
            "rising_ratio": round(rising_ratio, 2) if rising_ratio else None,
            "series": [int(v) for v in series],
        },
        raw_url=f"https://trends.google.com/trends/explore?q={keyword}&geo={region}",
        anomaly_score=round(score, 3) if score is not None else None,
    ).to_dict()


@mcp.tool()
def fetch_ptt(board: str = "Stock", pages: int = 1) -> dict[str, Any]:
    """STUB — PTT/Dcard social-buzz sensor.

    PTT has an 18+ over-18 cookie gate plus anti-scraping; Dcard requires
    headers/tokens. Deferred to Phase 5+. Returns a not_implemented signal so
    the Scout agent can treat the source as "known but offline".
    """
    return Signal(
        source="news.ptt",
        signal_type="social_buzz",
        content={
            "status": "not_implemented",
            "board": board,
            "todo": "implement PTT over-18 cookie + Dcard header crawl in Phase 5+",
        },
        anomaly_score=None,
    ).to_dict()


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
