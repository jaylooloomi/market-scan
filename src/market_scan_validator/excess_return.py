"""Compute excess returns of a stock relative to a baseline (TAIEX) over time windows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from market_scan_validator.data_fetcher import (
    PriceSeries,
    close_at,
    trading_day_at_or_after,
    trading_day_at_or_before,
)


@dataclass
class WindowReturns:
    """Returns over multiple windows relative to a trigger date.

    All returns are arithmetic: (P_end / P_start) - 1, expressed as decimal.
    "excess" = stock_return - baseline_return.
    """
    trigger_date: date
    pre_days: int
    post_days: list[int]

    # Anchors actually used (nearest trading days)
    anchor_t_minus_1: date | None = None  # T-1 trading day (or earlier if holiday)
    anchor_t_minus_pre: date | None = None  # T-pre_days trading day
    anchor_t_plus_post: dict[int, date | None] = field(default_factory=dict)

    # Returns
    stock_pre_return: float | None = None  # T-pre → T-1
    baseline_pre_return: float | None = None
    pre_excess: float | None = None

    stock_post_returns: dict[int, float | None] = field(default_factory=dict)
    baseline_post_returns: dict[int, float | None] = field(default_factory=dict)
    post_excess: dict[int, float | None] = field(default_factory=dict)

    error: str | None = None


def compute_window_returns(
    stock: PriceSeries,
    baseline: PriceSeries,
    trigger_date: date,
    pre_days: int,
    post_days: list[int],
) -> WindowReturns:
    """Compute excess returns for a stock vs baseline around trigger_date."""
    wr = WindowReturns(
        trigger_date=trigger_date,
        pre_days=pre_days,
        post_days=list(post_days),
    )

    # Anchor: T-1 (the day before trigger). Use latest trading day strictly before trigger.
    t_minus_1 = trading_day_at_or_before(
        stock.df,
        trigger_date - timedelta(days=1),
    )
    t_minus_1_base = trading_day_at_or_before(
        baseline.df,
        trigger_date - timedelta(days=1),
    )

    if t_minus_1 is None or t_minus_1_base is None:
        wr.error = f"No T-1 trading day before {trigger_date}"
        return wr

    # Use the earlier of the two so both have data
    t_minus_1_common = min(t_minus_1, t_minus_1_base)
    if t_minus_1_common not in stock.df.index or t_minus_1_common not in baseline.df.index:
        # fall back
        for cand in sorted({t_minus_1, t_minus_1_base}, reverse=True):
            if cand in stock.df.index and cand in baseline.df.index:
                t_minus_1_common = cand
                break
        else:
            wr.error = f"No common T-1 trading day"
            return wr

    wr.anchor_t_minus_1 = t_minus_1_common.date()

    # T-pre_days
    t_minus_pre_target = trigger_date - timedelta(days=pre_days)
    t_minus_pre_stock = trading_day_at_or_after(stock.df, t_minus_pre_target)
    t_minus_pre_base = trading_day_at_or_after(baseline.df, t_minus_pre_target)

    if t_minus_pre_stock is None or t_minus_pre_base is None:
        wr.error = f"No T-{pre_days} trading day around {t_minus_pre_target}"
        return wr

    t_minus_pre_common = max(t_minus_pre_stock, t_minus_pre_base)
    while t_minus_pre_common not in stock.df.index or t_minus_pre_common not in baseline.df.index:
        # walk forward 1 day
        next_idx_stock = stock.df.index[stock.df.index > t_minus_pre_common]
        next_idx_base = baseline.df.index[baseline.df.index > t_minus_pre_common]
        if len(next_idx_stock) == 0 or len(next_idx_base) == 0:
            wr.error = "Cannot align T-pre anchor across stock+baseline"
            return wr
        t_minus_pre_common = max(next_idx_stock[0], next_idx_base[0])
        if t_minus_pre_common >= t_minus_1_common:
            wr.error = "T-pre walked past T-1"
            return wr

    wr.anchor_t_minus_pre = t_minus_pre_common.date()

    # Compute pre-trigger returns
    stock_pre_start = close_at(stock.df, t_minus_pre_common)
    stock_pre_end = close_at(stock.df, t_minus_1_common)
    base_pre_start = close_at(baseline.df, t_minus_pre_common)
    base_pre_end = close_at(baseline.df, t_minus_1_common)

    wr.stock_pre_return = (stock_pre_end / stock_pre_start) - 1.0
    wr.baseline_pre_return = (base_pre_end / base_pre_start) - 1.0
    wr.pre_excess = wr.stock_pre_return - wr.baseline_pre_return

    # Post-trigger returns: from T-1 close to T+N close
    for n in post_days:
        target = trigger_date + timedelta(days=n)
        post_stock = trading_day_at_or_before(stock.df, target)
        post_base = trading_day_at_or_before(baseline.df, target)

        if post_stock is None or post_base is None:
            wr.anchor_t_plus_post[n] = None
            wr.stock_post_returns[n] = None
            wr.baseline_post_returns[n] = None
            wr.post_excess[n] = None
            continue

        post_common = min(post_stock, post_base)
        # ensure both have it
        while post_common not in stock.df.index or post_common not in baseline.df.index:
            prev_stock = stock.df.index[stock.df.index < post_common]
            prev_base = baseline.df.index[baseline.df.index < post_common]
            if len(prev_stock) == 0 or len(prev_base) == 0:
                post_common = None
                break
            post_common = min(prev_stock[-1], prev_base[-1])
            if post_common <= t_minus_1_common:
                post_common = None
                break

        if post_common is None:
            wr.anchor_t_plus_post[n] = None
            wr.stock_post_returns[n] = None
            wr.baseline_post_returns[n] = None
            wr.post_excess[n] = None
            continue

        wr.anchor_t_plus_post[n] = post_common.date()
        s_ret = (close_at(stock.df, post_common) / stock_pre_end) - 1.0
        b_ret = (close_at(baseline.df, post_common) / base_pre_end) - 1.0
        wr.stock_post_returns[n] = s_ret
        wr.baseline_post_returns[n] = b_ret
        wr.post_excess[n] = s_ret - b_ret

    return wr


def average_window_returns(
    returns_per_stock: list[WindowReturns],
) -> WindowReturns:
    """Average a list of WindowReturns (assumed same trigger/pre/post config)."""
    if not returns_per_stock:
        raise ValueError("empty list of returns")

    template = returns_per_stock[0]
    avg = WindowReturns(
        trigger_date=template.trigger_date,
        pre_days=template.pre_days,
        post_days=list(template.post_days),
    )

    valid = [r for r in returns_per_stock if r.error is None and r.pre_excess is not None]
    if not valid:
        avg.error = "no valid per-stock returns to average"
        return avg

    avg.pre_excess = sum(r.pre_excess for r in valid) / len(valid)
    avg.stock_pre_return = sum(r.stock_pre_return for r in valid) / len(valid)
    avg.baseline_pre_return = valid[0].baseline_pre_return  # same baseline

    for n in template.post_days:
        valid_n = [r for r in valid if r.post_excess.get(n) is not None]
        if valid_n:
            avg.post_excess[n] = sum(r.post_excess[n] for r in valid_n) / len(valid_n)
            avg.stock_post_returns[n] = (
                sum(r.stock_post_returns[n] for r in valid_n) / len(valid_n)
            )
            avg.baseline_post_returns[n] = valid_n[0].baseline_post_returns[n]
        else:
            avg.post_excess[n] = None
            avg.stock_post_returns[n] = None
            avg.baseline_post_returns[n] = None

    return avg
