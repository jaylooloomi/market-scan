"""The standard signal envelope every sensor tool returns.

Contract (must not break — Reviewer agent depends on this shape):

    {
      "timestamp": "ISO-8601",
      "source": "news.economic-daily",
      "signal_type": "news_anomaly",
      "content": {...},
      "raw_url": "https://..." | null,
      "anomaly_score": 0.0-1.0 | null
    }
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    """Current time as a timezone-aware ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Signal:
    """One unit of sensor output."""

    source: str
    signal_type: str
    content: dict[str, Any]
    raw_url: str | None = None
    anomaly_score: float | None = None
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def error_signal(source: str, signal_type: str, message: str, **content: Any) -> dict[str, Any]:
    """A signal that carries a structured error instead of crashing the server.

    Graceful failure is part of the sensor contract: a missing token, a dead
    feed, or an API change must surface as data, never as an exception that
    takes the whole MCP server down.
    """
    return Signal(
        source=source,
        signal_type=signal_type,
        content={"error": message, **content},
        anomaly_score=None,
    ).to_dict()
