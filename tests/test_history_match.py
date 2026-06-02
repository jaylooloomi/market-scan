"""get_history_match MCP tool — offline test (token-overlap fallback, no network).

Confirms the Reviewer's history lookup works via the installed package (not a
CWD-relative themes.json path), which is what makes it survive a plugin install.
"""
from __future__ import annotations


def test_get_history_match_returns_similar_themes() -> None:
    from polydig_mcp.data import server as data

    r = data.get_history_match("航運 貨櫃 運價 SCFI 長榮 陽明 萬海 散裝", n_results=3)
    assert r["signal_type"] == "history_match"
    ids = [m["id"] for m in r["content"]["matches"]]
    assert "shipping_2020" in ids          # the shipping theme should surface
    assert len(r["content"]["matches"]) <= 3


def test_get_history_match_shape() -> None:
    from polydig_mcp.data import server as data

    r = data.get_history_match("AI 伺服器 CoWoS", n_results=2)
    assert r["source"] == "data.history"
    for m in r["content"]["matches"]:
        assert {"id", "name", "similarity"} <= set(m)
