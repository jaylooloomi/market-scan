"""End-to-end daily pipeline (headless): sensors -> Scout -> Reviewer -> report.

This is the dry/headless orchestration used for testing and cron runs. In the
Claude Code plugin, the same flow is driven by the Scout/Reviewer subagents
calling the MCP tools; here we call the sensor tool functions in-process.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from polydig_mcp.history.store import ThemeStore
from polydig_mcp.reporting.generator import generate_report
from polydig_mcp.reviewer.engine import review
from polydig_mcp.reviewer.scout import signals_to_candidates


def collect_signals(news_queries: list[str] | None = None) -> list[dict[str, Any]]:
    """Gather raw signals from the sensors (in-process). Each sensor failure is
    contained — a dead source never aborts the run."""
    signals: list[dict[str, Any]] = []

    try:
        from polydig_mcp.news import server as news
        signals.extend(news.detect_news_anomaly(window_days=1.0, threshold=0.3, max_terms=10))
    except Exception as e:  # noqa: BLE001
        signals.append({"source": "news", "signal_type": "error", "content": {"error": str(e)}})

    try:
        from polydig_mcp.data import server as data
        for c in ("copper", "crude"):
            signals.append(data.get_commodity_price(c))
        signals.append(data.get_shipping_index("BDI"))
    except Exception as e:  # noqa: BLE001
        signals.append({"source": "data", "signal_type": "error", "content": {"error": str(e)}})

    try:
        from polydig_mcp.price import server as price
        signals.append(price.detect_limit_up_cluster(min_size=3))
    except Exception as e:  # noqa: BLE001
        signals.append({"source": "price", "signal_type": "error", "content": {"error": str(e)}})

    return signals


def run_daily(
    *,
    store: ThemeStore | None = None,
    reviewer_mode: str = "dry",
    signal_provider: Callable[[], list[dict[str, Any]]] | None = None,
    report_date: date | None = None,
) -> dict[str, Any]:
    """Run one daily cycle. Returns {signals, candidates, verdicts, report_md}."""
    store = store or ThemeStore()
    signals = (signal_provider or collect_signals)()
    candidates = signals_to_candidates(signals)

    verdicts = [review(c, store, mode=reviewer_mode) for c in candidates]

    missed = [
        {"industry": c["theme_hint"].replace("族群漲停潮", ""), "members": c["raw_signals"][0]["content"].get("clusters", {})}
        for c in candidates
        if c.get("is_safety_net")
    ]
    report_md = generate_report(verdicts, report_date=report_date)

    return {
        "signals": signals,
        "candidates": candidates,
        "verdicts": verdicts,
        "report_md": report_md,
    }
