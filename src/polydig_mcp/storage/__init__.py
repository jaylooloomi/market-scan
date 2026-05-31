"""SQLite storage layer for PolyDig (spec §6.4).

Tables:
    signals        — raw sensor output log
    term_history   — cross-week news-term baselines
    verdicts       — Reviewer verdicts (strong / watchlist / reject)
    missed_catch   — backfill findings from price safety-net triggers
"""
from .db import PolyDigDB

__all__ = ["PolyDigDB"]
