"""Unit tests: FinMind missing-token path + Scout/Reviewer prompt builders (offline)."""
from __future__ import annotations

import sys

sys.path.insert(0, "src")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import polydig_mcp.data.finmind as fm
from polydig_mcp.common.errors import SensorError
from polydig_mcp.common.settings import Settings
from polydig_mcp.reviewer.prompt import (
    REVIEWER_SYSTEM,
    build_reviewer_user_prompt,
    build_scout_user_prompt,
)


def main() -> int:
    # FinMind without a token -> SensorError("missing_token"), made deterministic by
    # swapping get_settings (restored in finally) so it doesn't depend on a real .env.
    orig = fm.get_settings
    try:
        fm.get_settings = lambda: Settings(
            finmind_token=None, http_timeout=15.0, user_agent="ua",
            telegram_bot_token=None, telegram_chat_id=None,
        )
        try:
            fm.query("price", "2330")
            raise AssertionError("expected SensorError for missing token")
        except SensorError as e:
            assert e.code == "missing_token", e.code
    finally:
        fm.get_settings = orig
    assert fm.DATASETS["price"] == "TaiwanStockPrice"  # friendly alias -> raw dataset id
    print("finmind missing-token + dataset alias: PASS")

    # Reviewer prompt embeds the candidate + retrieved matches + asks for a causal tree
    rp = build_reviewer_user_prompt(
        {"theme_hint": "矽光子", "trigger_summary": "TSMC CPO"},
        [{"id": "silicon_photonics_2024", "similarity": 0.8}],
    )
    assert "矽光子" in rp and "silicon_photonics_2024" in rp and "因果樹" in rp, rp[:160]

    # Scout prompt embeds the raw signals and asks for candidates
    assert "候選主題" in build_scout_user_prompt({"news": "x"})
    assert "Sonnet" in REVIEWER_SYSTEM
    print("prompt builders (reviewer + scout): PASS")

    print("\n=== PASS ===")
    return 0


def test_finmind_prompt():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
