"""RSS source registry + fetch + lightweight news-anomaly detection.

Sensor philosophy: detect *that* a term is spiking, not *what it means*. The
Reviewer agent (Phase 2) does the semantic interpretation.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from time import mktime
from typing import Any

import feedparser

from polydig_mcp.common.errors import SensorError


@dataclass(frozen=True)
class Feed:
    id: str
    name: str
    url: str
    lang: str  # "zh" | "en"
    category: str


# Curated, publicly-available RSS feeds. If one dies, fetch_news degrades
# gracefully (per-feed errors are reported, the rest still return).
FEEDS: dict[str, Feed] = {
    "udn-money": Feed(
        "udn-money", "經濟日報", "https://money.udn.com/rssfeed/news/1001/5591?ch=money",
        "zh", "finance",
    ),
    "ltn-ec": Feed(
        "ltn-ec", "自由財經", "https://ec.ltn.com.tw/rss/all.xml", "zh", "finance",
    ),
    "cna-finance": Feed(
        "cna-finance", "中央社財經", "https://feeds.feedburner.com/rsscna/finance",
        "zh", "finance",
    ),
    "cnbc-top": Feed(
        "cnbc-top", "CNBC Top News",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html", "en", "finance",
    ),
    "cnbc-tech": Feed(
        "cnbc-tech", "CNBC Technology",
        "https://www.cnbc.com/id/19854910/device/rss/rss.html", "en", "technology",
    ),
    "marketwatch-top": Feed(
        "marketwatch-top", "MarketWatch Top Stories",
        "http://feeds.marketwatch.com/marketwatch/topstories/", "en", "finance",
    ),
}

# Stopwords kept tiny on purpose — sensor stays dumb, Reviewer is smart.
_EN_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "as", "at", "by", "is", "are", "be", "this", "that", "from", "it", "its",
    "will", "has", "have", "new", "says", "after", "over", "up", "down", "amid",
}
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]{2,}")
# CJK 2-4 char chunks as crude "terms"
_CJK_RE = re.compile(r"[一-鿿]{2,4}")


def _entry_time(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(mktime(t), tz=timezone.utc)
    return None


def fetch_feed(feed: Feed) -> list[dict[str, Any]]:
    """Parse one feed into normalized items. Raises SensorError on hard failure."""
    parsed = feedparser.parse(feed.url)
    if parsed.bozo and not parsed.entries:
        raise SensorError(
            "fetch_failed",
            f"feed '{feed.id}' returned no entries ({getattr(parsed, 'bozo_exception', 'unknown')})",
        )
    items = []
    for e in parsed.entries:
        dt = _entry_time(e)
        items.append(
            {
                "source": feed.id,
                "source_name": feed.name,
                "lang": feed.lang,
                "title": e.get("title", "").strip(),
                "summary": re.sub(r"<[^>]+>", "", e.get("summary", "")).strip()[:500],
                "link": e.get("link"),
                "published": dt.isoformat() if dt else None,
                "_dt": dt,
            }
        )
    return items


def _terms(text: str, lang: str) -> list[str]:
    text = text or ""
    if lang == "zh":
        return _CJK_RE.findall(text)
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _EN_STOP]


def detect_term_spikes(
    items: list[dict[str, Any]],
    window_days: float,
    min_recent_count: int = 3,
) -> list[dict[str, Any]]:
    """Split items into recent (<= window_days old) vs older, and surface terms
    whose recent frequency exceeds their older-period frequency.

    This is a within-available-feed-window heuristic. True multi-week temporal
    anomaly detection needs the persisted history store (Phase 3) — documented
    honestly rather than faked here.
    """
    now = datetime.now(timezone.utc)
    recent: Counter = Counter()
    older: Counter = Counter()
    recent_links: dict[str, str | None] = {}

    for it in items:
        dt = it.get("_dt")
        bucket = recent if (dt is None or (now - dt).total_seconds() <= window_days * 86400) else older
        for term in _terms(f"{it['title']} {it['summary']}", it["lang"]):
            bucket[term] += 1
            if bucket is recent and term not in recent_links:
                recent_links[term] = it.get("link")

    spikes = []
    for term, rc in recent.items():
        if rc < min_recent_count:
            continue
        oc = older.get(term, 0)
        # ratio with smoothing; unbounded when term is brand-new (oc == 0)
        ratio = rc / (oc + 1)
        # squash into 0..1 anomaly score
        score = min(1.0, ratio / 5.0)
        spikes.append(
            {
                "term": term,
                "recent_count": rc,
                "prior_count": oc,
                "spike_ratio": round(ratio, 2),
                "anomaly_score": round(score, 3),
                "example_url": recent_links.get(term),
            }
        )
    spikes.sort(key=lambda s: s["anomaly_score"], reverse=True)
    return spikes
