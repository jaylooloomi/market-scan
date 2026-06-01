"""policy-mcp MCP server (Phase 4).

Tools:
    list_policy_sources()                      -> candidate gov sources + feasibility
    fetch_policy_announcements(source, limit)  -> recent announcements (RSS where available)

Feasibility research (HANDOFF P4.1): of the 4 candidates (金管會/衛福部/行政院/立法院),
those exposing an RSS/open-data feed are implemented; the rest are marked
'needs_html_scrape' with a TODO rather than faked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import feedparser

from mcp.server.fastmcp import FastMCP

from polydig_mcp.common.envelope import Signal, error_signal
from polydig_mcp.common.errors import SensorError
from polydig_mcp.common.http import polite_get

mcp = FastMCP("polydig-policy")


@dataclass(frozen=True)
class PolicySource:
    id: str
    name: str
    feasibility: str  # "rss" | "needs_html_scrape"
    url: str | None    # RSS url when feasibility == "rss"
    note: str


# Feasibility assessment — RSS feeds are implemented; HTML-only sources are
# flagged for a dedicated scraper (HTML structure changes → needs retry+diff).
POLICY_SOURCES: dict[str, PolicySource] = {
    "mohw": PolicySource(
        "mohw", "衛福部", "rss", "https://www.mohw.gov.tw/rss-16-1.html",
        "疫苗 EUA、健保藥價等。RSS feed 已驗證可用(text/xml,~20 則)。",
    ),
    "fsc": PolicySource(
        "fsc", "金管會", "needs_html_scrape", None,
        "金融法規、ETF/基金核准。新聞稿頁面為 HTML,需專屬爬蟲。",
    ),
    "ey": PolicySource(
        "ey", "行政院", "needs_html_scrape", None,
        "重大政策、產業補助。新聞頁 HTML,需爬蟲 + diff。",
    ),
    "ly": PolicySource(
        "ly", "立法院公報", "needs_html_scrape", None,
        "三讀法案(太空法等)。lis.ly.gov.tw,結構複雜,需專屬 parser。",
    ),
}


@mcp.tool()
def list_policy_sources() -> list[dict[str, str]]:
    """List candidate government policy sources and their crawl feasibility."""
    return [
        {"id": s.id, "name": s.name, "feasibility": s.feasibility, "note": s.note}
        for s in POLICY_SOURCES.values()
    ]


@mcp.tool()
def fetch_policy_announcements(source: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch recent policy announcements from a source.

    RSS-feasible sources return items; HTML-only sources return a structured
    not_implemented signal (Phase 4 scraper TODO).
    """
    src = POLICY_SOURCES.get(source)
    if src is None:
        return [error_signal("policy", "policy_announcement", f"unknown source {source!r}")]

    if src.feasibility != "rss" or not src.url:
        return [
            Signal(
                source=f"policy.{src.id}",
                signal_type="policy_announcement",
                content={"status": "not_implemented", "feasibility": src.feasibility, "todo": src.note},
                anomaly_score=None,
            ).to_dict()
        ]

    try:
        resp = polite_get(src.url)  # shared timeout/retry/UA (no untimed feedparser fetch)
    except SensorError as e:
        return [error_signal(f"policy.{src.id}", "policy_announcement", e.message)]
    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        return [error_signal(f"policy.{src.id}", "policy_announcement",
                             f"feed unavailable: {getattr(parsed, 'bozo_exception', 'unknown')}")]
    out = []
    for e in parsed.entries[:limit]:
        out.append(
            Signal(
                source=f"policy.{src.id}",
                signal_type="policy_announcement",
                content={"title": e.get("title", ""), "published": e.get("published"), "source_name": src.name},
                raw_url=e.get("link"),
                anomaly_score=None,
            ).to_dict()
        )
    return out


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
