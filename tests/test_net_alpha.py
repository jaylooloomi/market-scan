"""net-alpha 純函式測試(離線):成本、出場規則、毛→淨 haircut 方向。pytest 可收集。"""
from __future__ import annotations

from datetime import date, timedelta

from market_scan_validator.net_alpha import (
    compute_case_ticker,
    compute_ticker_net,
    exit_with_rules,
    parse_hold_period,
    round_trip_net,
    theme_aware_net,
)


def test_round_trip_net() -> None:
    assert round(round_trip_net(1.0, 0.005), 6) == round(2.0 * 0.995 - 1.0, 6)  # +99%
    assert round(round_trip_net(0.0, 0.005), 6) == -0.005
    assert round_trip_net(-0.5, 0.0) == -0.5


def test_exit_hits_stop_loss() -> None:
    closes = [10.0, 9.5, 7.9]  # -21% at idx 2
    idx, ret = exit_with_rules(closes, 0, stop_loss=-0.20, time_stop=30)
    assert idx == 2 and ret <= -0.20


def test_exit_hits_time_stop() -> None:
    closes = [10.0, 11.0, 12.0, 13.0, 14.0]  # never drops; time-stop should bite
    idx, ret = exit_with_rules(closes, 0, stop_loss=-0.20, time_stop=2)
    assert idx == 2 and round(ret, 4) == round(12.0 / 10.0 - 1.0, 4)


def test_exit_hits_take_profit() -> None:
    closes = [10.0, 13.0]
    idx, ret = exit_with_rules(closes, 0, take_profit=0.25, time_stop=30)
    assert idx == 1 and round(ret, 4) == 0.3


def test_haircut_direction_t1_entry_beats_late_entry() -> None:
    """If the stock runs up after the trigger, a T-1 entry (gross A) must beat a
    realistic T+2 entry (net B) — the core 'limit-up haircut' the doc claims."""
    trigger = date(2020, 1, 20)
    dates = [date(2020, 1, 10) + timedelta(days=i) for i in range(200)]
    closes = []
    for d in dates:
        if d < trigger:
            closes.append(10.0)                       # flat, fillable, pre-run
        else:
            run = min((d - trigger).days, 8)
            closes.append(min(30.0, 10.0 * (1.10 ** run)))  # limit-up run, then plateau
    r = compute_ticker_net(dates, closes, trigger, fill_lag_trading_days=2)
    assert r is not None
    assert r.gross_A is not None and r.net_B is not None
    assert r.gross_A > r.net_B          # late + costed entry is worse
    assert r.exit_C_days is not None and r.exit_C_days > 0


def test_case_ticker_horizon_sensitivity_slow_theme() -> None:
    """A steadily-rising (slow) theme: a longer exit horizon captures more."""
    trigger = date(2020, 1, 20)
    dates = [date(2020, 1, 10) + timedelta(days=i) for i in range(220)]
    closes = [10.0 if d < trigger else 10.0 + (d - trigger).days * 0.1 for d in dates]
    r = compute_case_ticker(dates, closes, trigger, horizons=(30, 90, 180))
    assert r is not None
    assert r["net_C"][180] > r["net_C"][90] > r["net_C"][30]   # longer = more captured
    assert r["gross_A"] > r["net_B"]                            # late + costed entry worse


def test_case_ticker_stop_loss_caps_crash() -> None:
    """A crashing theme: the -20% stop bounds the loss (not a -80% wipeout)."""
    trigger = date(2020, 1, 20)
    dates = [date(2020, 1, 10) + timedelta(days=i) for i in range(220)]
    closes = [10.0 if d < trigger else max(2.0, 10.0 - (d - trigger).days * 0.2) for d in dates]
    r = compute_case_ticker(dates, closes, trigger, horizons=(30, 90, 180), stop_loss=-0.20)
    assert r is not None
    assert r["net_C"][180] is not None and r["net_C"][180] > -0.30   # stop bounded the loss


def test_parse_hold_period_real_themes() -> None:
    # the actual hold_period strings from themes.json
    assert parse_hold_period("1-3 個月(漲快跌也快)") == (30, 90)
    assert parse_hold_period("6-12 個月") == (180, 360)
    assert parse_hold_period("1-3 年(主升段)") == (365, 1095)
    assert parse_hold_period("1-2 年(到 2026/2027 量產主升段)") == (365, 730)  # "1-2", not "2026/2027"
    assert parse_hold_period("3-6 個月(戰爭越久效應遞減)") == (90, 180)
    assert parse_hold_period("") is None
    assert parse_hold_period("沒有數字也沒有單位") is None


def test_theme_aware_net_caps_when_hold_exceeds_data() -> None:
    trigger = date(2020, 1, 20)
    dates = [date(2020, 1, 10) + timedelta(days=i) for i in range(120)]  # ~110d after trigger
    closes = [10.0 if d < trigger else 10.0 + (d - trigger).days * 0.05 for d in dates]
    long_hold = theme_aware_net(dates, closes, trigger, 365)   # 1yr hold, only ~110d data
    assert long_hold is not None and long_hold["capped"] is True
    short_hold = theme_aware_net(dates, closes, trigger, 60)   # 60d hold, within data
    assert short_hold is not None and short_hold["capped"] is False
