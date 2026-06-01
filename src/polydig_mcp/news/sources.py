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
from polydig_mcp.common.http import polite_get


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
        # ec.ltn.com.tw/rss/all.xml went dead (serves HTML now); the live 財經 feed
        # is on the news subdomain.
        "ltn-ec", "自由財經", "https://news.ltn.com.tw/rss/business.xml", "zh", "finance",
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
# Fallback CJK 2-4 char chunks (used only if jieba is unavailable)
_CJK_RE = re.compile(r"[一-鿿]{2,4}")

# jieba POS tags worth keeping (nouns + proper nouns + foreign words).
# Drop nr (person names — reporter bylines etc.) and verbs/particles → kills the
# cross-boundary junk the old bigram tokenizer produced.
_KEEP_POS = {"n", "ns", "nt", "nz", "nl", "eng"}
# Common Chinese finance-noise terms to drop even if tagged as nouns.
_ZH_STOP = {
    "公司", "表示", "指出", "今天", "今日", "昨天", "國際", "億元", "萬元", "美元",
    "台幣", "市場", "投資", "營收", "業績", "股價", "預期", "消息", "報導", "新聞",
    "記者", "目前", "未來", "持續", "相關", "方面", "部分", "問題", "影響", "可能",
}


# Domain terms jieba's default dict doesn't know (would get fragmented, e.g.
# 矽光子 → 矽+光子). Stocks themes live in the history DB; we also curate a core set.
_CORE_DOMAIN_TERMS = [
    "矽光子", "光通訊", "光模組", "光學引擎", "CPO", "CoWoS", "SoIC", "先進封裝",
    "載板", "ABF", "散熱", "液冷", "重電", "電網", "銅纜", "電纜", "機器人",
    "低軌衛星", "衛星", "半導體", "矽晶圓", "航運", "貨櫃", "散裝", "塞港", "缺櫃",
    "國防", "無人機", "軍工", "疫苗", "口罩", "不織布", "熔噴布", "防疫",
    "BBU", "電池備援", "ASIC", "矽智財", "記憶體", "伺服器", "高速網路",
    "化肥", "尿素", "鋼鐵", "原物料", "宅經濟", "電商", "筆電", "網通",
]
_userdict_loaded = False


def _ensure_userdict() -> None:
    """Teach jieba domain terms once (curated + theme names/roles from history DB)."""
    global _userdict_loaded
    if _userdict_loaded:
        return
    try:
        import jieba

        words = set(_CORE_DOMAIN_TERMS)
        try:
            from polydig_mcp.history.store import load_themes
            for t in load_themes():
                words.add(t.get("name", "").split("(")[0].split("/")[0].strip())
                for tier in t.get("causal_tree", {}).values():
                    for m in tier:
                        if m.get("role"):
                            words.add(m["role"].split("(")[0].split("→")[0].strip())
        except Exception:  # noqa: BLE001
            pass
        for w in words:
            if w and len(w) >= 2:
                jieba.add_word(w, tag="nz")  # tag so posseg keeps it (nz ∈ _KEEP_POS)
    except Exception:  # noqa: BLE001
        pass
    _userdict_loaded = True


def _jieba_terms(text: str) -> list[str] | None:
    """POS-filtered jieba tokens; None if jieba unavailable (caller falls back)."""
    try:
        import jieba.posseg as pseg
    except Exception:  # noqa: BLE001
        return None
    _ensure_userdict()
    out: list[str] = []
    for w, flag in pseg.cut(text):
        w = w.strip()
        if len(w) < 2 or w in _ZH_STOP:
            continue
        if flag in _KEEP_POS or flag.startswith("nz"):
            out.append(w)
    return out


def _entry_time(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(mktime(t), tz=timezone.utc)
    return None


def fetch_feed(feed: Feed) -> list[dict[str, Any]]:
    """Parse one feed into normalized items. Raises SensorError on hard failure."""
    # Fetch via the shared session (timeout/retry/UA) instead of letting
    # feedparser do its own untimed urllib fetch — a hung feed would otherwise
    # block the sensor forever (feedparser.parse has no timeout).
    parsed = feedparser.parse(polite_get(feed.url).content)
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
        jt = _jieba_terms(text)
        if jt is not None:
            return jt
        return _CJK_RE.findall(text)  # fallback if jieba missing
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _EN_STOP]


# Sample-size confidence: the article count at which we fully trust the spike
# ratio. The score is multiplied by min(1, recent_count / FULL_CONFIDENCE_COUNT)
# so a tiny-sample ratio can't max out the score. Source-scale dependent — should
# be calibrated by the replay harness (see reports/optimization/01-architect-optimization.md).
FULL_CONFIDENCE_COUNT = 8


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
    recent_links: dict[str, list[str]] = {}  # term -> up to 3 distinct article links

    for it in items:
        dt = it.get("_dt")
        bucket = recent if (dt is None or (now - dt).total_seconds() <= window_days * 86400) else older
        for term in _terms(f"{it['title']} {it['summary']}", it["lang"]):
            bucket[term] += 1
            if bucket is recent:
                link = it.get("link")
                links = recent_links.setdefault(term, [])
                if link and link not in links and len(links) < 3:
                    links.append(link)

    spikes = []
    for term, rc in recent.items():
        if rc < min_recent_count:
            continue
        oc = older.get(term, 0)
        # ratio with smoothing; unbounded when term is brand-new (oc == 0)
        ratio = rc / (oc + 1)
        # squash into 0..1, then damp by sample-size confidence: a ratio computed
        # from very few articles is unreliable (a brand-new term seen 3-4 times off
        # a ~0 baseline would otherwise score 0.6-0.8 — a false positive on noise,
        # demonstrated on real GDELT data for 2019-11 "Wuhan pneumonia").
        vol_conf = min(1.0, rc / FULL_CONFIDENCE_COUNT)
        score = min(1.0, ratio / 5.0) * vol_conf
        links = recent_links.get(term, [])
        spikes.append(
            {
                "term": term,
                "recent_count": rc,
                "prior_count": oc,
                "spike_ratio": round(ratio, 2),
                "anomaly_score": round(score, 3),
                "example_url": links[0] if links else None,
                "article_urls": links,
            }
        )
    spikes.sort(key=lambda s: s["anomaly_score"], reverse=True)
    return spikes
