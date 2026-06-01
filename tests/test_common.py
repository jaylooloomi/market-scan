"""Unit tests for the shared envelope / errors / settings building blocks (offline)."""
from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, "src")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from polydig_mcp.common.envelope import Signal, error_signal, now_iso
from polydig_mcp.common.errors import SensorError
from polydig_mcp.common.settings import Settings


def _settings(**kw):
    base = dict(finmind_token=None, http_timeout=15.0, user_agent="ua",
                telegram_bot_token=None, telegram_chat_id=None)
    base.update(kw)
    return Settings(**base)


def main() -> int:
    # Signal.to_dict — the exact contract shape the Reviewer depends on
    d = Signal(source="news.x", signal_type="news_item", content={"a": 1},
               raw_url="http://u", anomaly_score=0.5).to_dict()
    assert set(d) == {"source", "signal_type", "content", "raw_url", "anomaly_score", "timestamp"}, d
    assert d["source"] == "news.x" and d["anomaly_score"] == 0.5

    # now_iso is timezone-aware ISO-8601
    assert datetime.fromisoformat(now_iso()).tzinfo is not None

    # error_signal: error in content, score None
    e = error_signal("data.x", "commodity_price", "boom", commodity="copper")
    assert e["content"]["error"] == "boom" and e["content"]["commodity"] == "copper"
    assert e["anomaly_score"] is None
    print("envelope: PASS")

    # SensorError attrs + formatted str
    err = SensorError("missing_token", "no token")
    assert err.code == "missing_token" and err.message == "no token"
    assert "[missing_token]" in str(err)
    print("errors: PASS")

    # Settings derived properties
    assert _settings(finmind_token="t").has_finmind is True
    assert _settings(finmind_token=None).has_finmind is False
    assert _settings(telegram_bot_token="b", telegram_chat_id="c").has_telegram is True
    assert _settings(telegram_bot_token="b", telegram_chat_id=None).has_telegram is False
    print("settings: PASS")

    print("\n=== PASS ===")
    return 0


def test_common():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
