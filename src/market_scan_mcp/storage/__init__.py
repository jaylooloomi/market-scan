"""SQLite storage layer for Market Scan (spec §6.4).

Tables:
    signals        — raw sensor output log
    term_history   — cross-week news-term baselines
    verdicts       — Reviewer verdicts (strong / watchlist / reject)
    missed_catch   — backfill findings from price safety-net triggers
"""
from .db import MarketScanDB

__all__ = ["MarketScanDB"]
