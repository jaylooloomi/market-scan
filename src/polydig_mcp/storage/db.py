"""SQLite wrapper for PolyDig (spec §6.4). stdlib sqlite3, no ORM.

DB path default: ./polydig.db  (*.db is gitignored).

Tables
------
signals:
    id            INTEGER PK AUTOINCREMENT
    timestamp     TEXT    ISO-8601
    source        TEXT    sensor source (e.g. "news.anomaly")
    signal_type   TEXT
    content_json  TEXT    JSON blob
    anomaly_score REAL    nullable

term_history:
    id            INTEGER PK AUTOINCREMENT
    date          TEXT    YYYY-MM-DD
    term          TEXT
    count         INTEGER
    source        TEXT

verdicts:
    id            INTEGER PK AUTOINCREMENT
    date          TEXT    YYYY-MM-DD
    theme         TEXT
    grade         TEXT    strong | watchlist | reject
    confidence    REAL
    reasoning_json TEXT   full verdict dict as JSON

missed_catch:
    id            INTEGER PK AUTOINCREMENT
    date          TEXT    YYYY-MM-DD
    industry      TEXT
    members_json  TEXT    JSON list
    backfill_json TEXT    JSON with leading-signal findings
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Generator

_DEFAULT_PATH = "./polydig.db"

_DDL = """
CREATE TABLE IF NOT EXISTS signals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    signal_type   TEXT    NOT NULL,
    content_json  TEXT    NOT NULL,
    anomaly_score REAL
);

CREATE TABLE IF NOT EXISTS term_history (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    date   TEXT NOT NULL,
    term   TEXT NOT NULL,
    count  INTEGER NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verdicts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    theme          TEXT NOT NULL,
    grade          TEXT NOT NULL,
    confidence     REAL,
    reasoning_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS missed_catch (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT NOT NULL,
    industry      TEXT NOT NULL,
    members_json  TEXT NOT NULL,
    backfill_json TEXT NOT NULL
);
"""


class PolyDigDB:
    """Thin wrapper around sqlite3. Thread-safe via check_same_thread=False
    (single writer assumed; fine for the daily cron use-case)."""

    def __init__(self, db_path: str | Path = _DEFAULT_PATH) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_DDL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self) -> Generator[sqlite3.Cursor, None, None]:
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ── signals ──────────────────────────────────────────────────────────────

    def insert_signal(self, signal: dict[str, Any]) -> int:
        """Insert a raw sensor signal envelope. Returns row id."""
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO signals (timestamp, source, signal_type, content_json, anomaly_score) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    signal.get("timestamp", datetime.utcnow().isoformat()),
                    signal.get("source", ""),
                    signal.get("signal_type", ""),
                    json.dumps(signal.get("content", {}), ensure_ascii=False),
                    signal.get("anomaly_score"),
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def query_signals(
        self,
        source: str | None = None,
        signal_type: str | None = None,
        since: str | None = None,  # ISO date string
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Retrieve signals, optionally filtered."""
        clauses: list[str] = []
        params: list[Any] = []
        if source:
            clauses.append("source = ?")
            params.append(source)
        if signal_type:
            clauses.append("signal_type = ?")
            params.append(signal_type)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM signals {where} ORDER BY timestamp DESC LIMIT ?",
            params,
        ).fetchall()
        return [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "source": r["source"],
                "signal_type": r["signal_type"],
                "content": json.loads(r["content_json"]),
                "anomaly_score": r["anomaly_score"],
            }
            for r in rows
        ]

    # ── term_history ─────────────────────────────────────────────────────────

    def upsert_term_count(self, date_str: str, term: str, count: int, source: str) -> None:
        """Insert or replace a term frequency record for baseline tracking."""
        with self._tx() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO term_history (date, term, count, source) "
                "VALUES (?, ?, ?, ?)",
                (date_str, term, count, source),
            )

    def term_baseline(self, term: str, source: str, lookback_days: int = 21) -> float:
        """Cross-week baseline: mean daily count over past `lookback_days` days.

        Returns 0.0 if no history. The news server can compare today's count
        to this baseline to compute a cross-week anomaly score.
        """
        since = (date.today() - timedelta(days=lookback_days)).isoformat()
        rows = self._conn.execute(
            "SELECT count FROM term_history WHERE term=? AND source=? AND date>=?",
            (term, source, since),
        ).fetchall()
        if not rows:
            return 0.0
        return sum(r["count"] for r in rows) / len(rows)

    # ── verdicts ─────────────────────────────────────────────────────────────

    def insert_verdict(self, verdict: dict[str, Any], report_date: str | None = None) -> int:
        """Persist a Reviewer verdict (including reject = negative sample)."""
        date_str = report_date or date.today().isoformat()
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO verdicts (date, theme, grade, confidence, reasoning_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    date_str,
                    verdict.get("theme", ""),
                    verdict.get("signal_grade", "reject"),
                    verdict.get("confidence"),
                    json.dumps(verdict, ensure_ascii=False),
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def query_verdicts(
        self,
        grade: str | None = None,
        since: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if grade:
            clauses.append("grade = ?")
            params.append(grade)
        if since:
            clauses.append("date >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM verdicts {where} ORDER BY date DESC LIMIT ?",
            params,
        ).fetchall()
        return [
            {
                "id": r["id"],
                "date": r["date"],
                "theme": r["theme"],
                "grade": r["grade"],
                "confidence": r["confidence"],
                "verdict": json.loads(r["reasoning_json"]),
            }
            for r in rows
        ]

    # ── missed_catch ─────────────────────────────────────────────────────────

    def insert_missed_catch(
        self,
        industry: str,
        members: list[Any],
        backfill_findings: dict[str, Any],
        date_str: str | None = None,
    ) -> int:
        date_str = date_str or date.today().isoformat()
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO missed_catch (date, industry, members_json, backfill_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    date_str,
                    industry,
                    json.dumps(members, ensure_ascii=False),
                    json.dumps(backfill_findings, ensure_ascii=False),
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def query_missed_catch(
        self, since: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if since:
            where = "WHERE date >= ?"
            params.append(since)
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM missed_catch {where} ORDER BY date DESC LIMIT ?",
            params,
        ).fetchall()
        return [
            {
                "id": r["id"],
                "date": r["date"],
                "industry": r["industry"],
                "members": json.loads(r["members_json"]),
                "backfill": json.loads(r["backfill_json"]),
            }
            for r in rows
        ]
