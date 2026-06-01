"""net-alpha 純函式測試(離線):成本、出場規則、毛→淨 haircut 方向。pytest 可收集。"""
from __future__ import annotations

from datetime import date, timedelta

from polydig_validator.net_alpha import (
    compute_ticker_net,
    exit_with_rules,
    round_trip_net,
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
