"""roadmap-mcp MCP server (Phase 4).

Tools:
    list_tracked_companies()             -> companies whose roadmaps we watch
    parse_earnings_call(text, company)   -> extract roadmap/spec-upgrade keyword hits

The keyword extractor is real and testable (give it transcript text). Fetching
the transcripts (MOPS PDFs, intl earnings calls) is the part that needs robust
source-specific work — stubbed with honest TODOs.
"""
from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import FastMCP

from market_scan_mcp.common.envelope import Signal

mcp = FastMCP("market-scan-roadmap")

# HANDOFF P4.2: confirmed + suggested companies whose roadmaps lead Taiwan supply chain.
TRACKED_COMPANIES = {
    "intl_platform": ["Apple", "Microsoft", "Google", "Meta", "Tesla"],
    "intl_semi": ["TSMC", "NVIDIA", "AMD", "Intel", "ARM", "Broadcom", "Marvell",
                  "Qualcomm", "Samsung", "SK Hynix", "ASML"],
    "tw_via_mops": ["台積電", "聯發科", "鴻海", "廣達", "緯創", "日月光"],
}

# Spec-upgrade / supply-tightening keywords that precede price moves.
ROADMAP_KEYWORDS = [
    "缺貨", "供應吃緊", "供不應求", "漲價", "擴產", "新規格", "新製程", "合作", "認證",
    "量產", "導入", "升級", "瓶頸",
    "CPO", "COUPE", "HBM", "HBM4", "800G", "1.6T", "CoWoS", "SoIC", "矽光子",
    "advanced packaging", "shortage", "ramp", "capacity", "tape-out", "next-gen",
]
_KW_RE = re.compile("|".join(re.escape(k) for k in ROADMAP_KEYWORDS), re.IGNORECASE)


@mcp.tool()
def list_tracked_companies() -> dict[str, list[str]]:
    """List companies whose roadmaps / earnings calls we track."""
    return TRACKED_COMPANIES


@mcp.tool()
def parse_earnings_call(text: str, company: str = "") -> dict[str, Any]:
    """Extract roadmap/spec-upgrade keyword hits from earnings-call / roadmap text.

    Returns the matched keywords + a short context window for each, plus an
    anomaly_score scaled by hit density. Sensor stays dumb — the Reviewer
    interprets what the upgrade means for the Taiwan supply chain.
    """
    hits: list[dict[str, str]] = []
    for m in _KW_RE.finditer(text or ""):
        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 30)
        hits.append({"keyword": m.group(), "context": text[start:end].strip()})

    unique_kw = sorted({h["keyword"].lower() for h in hits})
    score = min(1.0, len(hits) / 10.0) if hits else 0.0
    return Signal(
        source="roadmap.earnings",
        signal_type="roadmap_signal",
        content={
            "company": company,
            "keyword_hits": hits[:30],
            "unique_keywords": unique_kw,
            "hit_count": len(hits),
        },
        anomaly_score=round(score, 3),
    ).to_dict()


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
