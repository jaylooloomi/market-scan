"""End-to-end daily pipeline (headless): sensors -> Scout -> Reviewer -> report.

This is the dry/headless orchestration used for testing and cron runs. In the
Claude Code plugin, the same flow is driven by the Scout/Reviewer subagents
calling the MCP tools; here we call the sensor tool functions in-process.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable

from polydig_mcp.history.store import ThemeStore
from polydig_mcp.reporting.generator import generate_report
from polydig_mcp.reviewer.engine import review
from polydig_mcp.reviewer.scout import signals_to_candidates


def collect_signals(
    news_queries: list[str] | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Gather raw signals from all 5 sensors (in-process). Each sensor failure is
    contained — a dead source never aborts the run.

    When *db_path* is given, news anomaly uses the cross-week SQLite baseline.
    The top news spikes are cross-checked against Google Trends, and US sector
    moves are pulled (cross-market US→TW linkage, spec §4.2).
    """
    signals: list[dict[str, Any]] = []

    # ── News anomaly (cross-week baseline when db_path given) ────────────────
    news_signals: list[dict[str, Any]] = []
    try:
        from polydig_mcp.news import server as news
        news_signals = news.detect_news_anomaly(
            window_days=1.0, threshold=0.3, max_terms=10, db_path=str(db_path) if db_path else None
        )
        signals.extend(news_signals)
    except Exception as e:  # noqa: BLE001
        signals.append({"source": "news", "signal_type": "error", "content": {"error": str(e)}})

    # ── Google Trends on the top spiking news terms (cross-source confirm) ────
    try:
        from polydig_mcp.news import server as news
        top_terms = [
            s["content"]["term"]
            for s in news_signals
            if s.get("signal_type") == "news_anomaly" and "term" in s.get("content", {})
        ][:3]
        for term in top_terms:
            signals.append(news.google_trends_check(term, region="TW", timeframe="now 7-d"))
    except Exception as e:  # noqa: BLE001
        signals.append({"source": "news.gtrends", "signal_type": "error", "content": {"error": str(e)}})

    # ── Data: commodities + shipping ─────────────────────────────────────────
    try:
        from polydig_mcp.data import server as data
        for c in ("copper", "crude"):
            signals.append(data.get_commodity_price(c))
        signals.append(data.get_shipping_index("BDI"))
    except Exception as e:  # noqa: BLE001
        signals.append({"source": "data", "signal_type": "error", "content": {"error": str(e)}})

    # ── Cross-market: US sector moves → TW family candidates ─────────────────
    try:
        from polydig_mcp.data import server as data
        for sector in ("nasdaq", "sp500"):
            signals.append(data.get_us_sector_move(sector, days=30))
    except Exception as e:  # noqa: BLE001
        signals.append({"source": "data.us_sector", "signal_type": "error", "content": {"error": str(e)}})

    # ── Price safety net ─────────────────────────────────────────────────────
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
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run one daily cycle. Returns {signals, candidates, verdicts, report_md}.

    When *db_path* is provided, verdicts (including rejects as negative samples)
    and missed_catch records are persisted to SQLite (spec §6.4).
    """
    store = store or ThemeStore()
    if signal_provider is not None:
        signals = signal_provider()
    else:
        signals = collect_signals(db_path=db_path)
    candidates = signals_to_candidates(signals)

    verdicts = [review(c, store, mode=reviewer_mode) for c in candidates]

    safety_net_candidates = [c for c in candidates if c.get("is_safety_net")]

    def _flatten_members(clusters: dict | list) -> list[dict[str, Any]]:
        """Flatten a clusters dict (industry -> [members]) into a flat list."""
        if isinstance(clusters, list):
            return clusters
        out: list[dict[str, Any]] = []
        for members in clusters.values():
            if isinstance(members, list):
                out.extend(members)
        return out

    def _members_for(candidate: dict[str, Any], industry: str) -> list[dict[str, Any]]:
        """Members of THIS candidate's own industry cluster (not the whole signal)."""
        clusters = candidate["raw_signals"][0]["content"].get("clusters", {})
        if isinstance(clusters, dict) and industry in clusters:
            return clusters[industry]
        return _flatten_members(clusters)

    missed: list[dict[str, Any]] = [
        {
            "industry": (ind := c["theme_hint"].replace("族群漲停潮", "")),
            "members": _members_for(c, ind),
        }
        for c in safety_net_candidates
    ]

    # ── persist to SQLite if db_path given ───────────────────────────────────
    if db_path is not None:
        try:
            from polydig_mcp.storage.db import PolyDigDB

            db = PolyDigDB(db_path)
            date_str = (report_date or date.today()).isoformat()

            # Persist all signals
            for sig in signals:
                if "error" not in sig.get("content", {}):
                    try:
                        db.insert_signal(sig)
                    except Exception:  # noqa: BLE001
                        pass

            # Persist all verdicts (rejects = negative samples)
            for v in verdicts:
                try:
                    db.insert_verdict(v, report_date=date_str)
                except Exception:  # noqa: BLE001
                    pass

            # Run backfill + persist missed_catch
            if safety_net_candidates:
                try:
                    from polydig_mcp.reviewer.backfill import run_backfill

                    enriched_missed: list[dict[str, Any]] = []
                    for c in safety_net_candidates:
                        industry = c["theme_hint"].replace("族群漲停潮", "")
                        members_list = _members_for(c, industry)
                        findings = run_backfill(industry, members_list, db)
                        db.insert_missed_catch(industry, members_list, findings, date_str)
                        enriched_missed.append({
                            "industry": industry,
                            "members": members_list,
                            "backfill": findings,
                        })
                    missed = enriched_missed  # replace with enriched version
                except Exception:  # noqa: BLE001
                    pass  # backfill failure must not abort the run

            db.close()
        except Exception:  # noqa: BLE001
            pass  # storage failure must not abort the run

    report_md = generate_report(verdicts, report_date=report_date, missed_clusters=missed or None)

    return {
        "signals": signals,
        "candidates": candidates,
        "verdicts": verdicts,
        "report_md": report_md,
    }
