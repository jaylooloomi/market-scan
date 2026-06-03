"""Crash-watch sensor — offline tests for the pure confluence logic (no network)."""
from __future__ import annotations

from market_scan_mcp.data.crashwatch import assess_confluence, assess_indicators


def test_assess_indicators_flags_stress() -> None:
    ind = assess_indicators(yc=-0.5, hy_latest=6.0, hy_min=3.0, vix=30.0)
    assert ind["yield_curve_inverted"]["stressed"] is True   # inverted (<0)
    assert ind["credit_spread_stress"]["stressed"] is True   # 6.0 >= 5.0 absolute
    assert ind["vix_elevated"]["stressed"] is True            # 30 >= 25


def test_assess_indicators_calm() -> None:
    ind = assess_indicators(yc=1.2, hy_latest=3.2, hy_min=3.0, vix=15.0)
    assert ind["yield_curve_inverted"]["stressed"] is False
    assert ind["credit_spread_stress"]["stressed"] is False   # 3.2<5 and widen 0.2<1.0
    assert ind["vix_elevated"]["stressed"] is False


def test_credit_spread_widening_trigger() -> None:
    # below the 5.0 absolute floor but widened >=1.0 off the window low -> stressed
    ind = assess_indicators(yc=0.5, hy_latest=4.3, hy_min=3.0, vix=18.0)
    assert ind["credit_spread_stress"]["stressed"] is True     # 4.3 - 3.0 = 1.3 >= 1.0


def test_assess_confluence_threshold_is_respected() -> None:
    ind = assess_indicators(yc=-0.5, hy_latest=6.0, hy_min=3.0, vix=15.0)  # 2/3 stressed
    assert assess_confluence(ind, threshold=2)["state"] == "risk_off"
    assert assess_confluence(ind, threshold=3)["state"] == "caution"      # 2 < 3
    calm = assess_confluence(assess_indicators(1.0, 3.0, 3.0, 15.0), threshold=2)
    assert calm["state"] == "calm" and calm["n_stressed"] == 0


def test_missing_indicators_are_skipped() -> None:
    ind = assess_indicators(yc=None, hy_latest=6.0, hy_min=3.0, vix=None)
    assert "yield_curve_inverted" not in ind and "vix_elevated" not in ind
    c = assess_confluence(ind, threshold=2)
    assert c["total"] == 1 and c["n_stressed"] == 1 and c["state"] == "caution"


def test_risk_off_requires_credit_confirmation() -> None:
    """Deep-research: inversion ALONE is insufficient (the 2022-23 false positive) —
    credit must confirm. yield-curve + VIX stressed but credit calm -> caution, not risk_off."""
    ind = assess_indicators(yc=-0.5, hy_latest=3.0, hy_min=3.0, vix=30.0)  # yc+vix, credit NOT
    c = assess_confluence(ind, threshold=2, require_credit=True)
    assert c["n_stressed"] == 2 and c["credit_confirmed"] is False
    assert c["state"] == "caution"                              # credit didn't confirm -> not risk_off
    # credit stressed too -> risk_off
    ind2 = assess_indicators(yc=-0.5, hy_latest=6.0, hy_min=3.0, vix=30.0)
    assert assess_confluence(ind2, threshold=2, require_credit=True)["state"] == "risk_off"
    # require_credit=False reverts to pure count
    assert assess_confluence(ind, threshold=2, require_credit=False)["state"] == "risk_off"
