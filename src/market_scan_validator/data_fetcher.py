"""Fetch historical OHLC data from yfinance for Taiwan stocks + TAIEX baseline.

FinMind integration is stubbed (requires API token) — yfinance is primary for Phase 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import yfinance as yf


@dataclass
class PriceSeries:
    symbol: str
    df: pd.DataFrame  # columns: Open, High, Low, Close, Volume; index: DatetimeIndex


class DataFetcher:
    """yfinance wrapper. Handles batched download and date alignment."""

    def __init__(self, cache: dict[str, PriceSeries] | None = None):
        self._cache: dict[str, PriceSeries] = cache or {}

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        force_refresh: bool = False,
    ) -> PriceSeries:
        key = f"{symbol}|{start.isoformat()}|{end.isoformat()}"
        if not force_refresh and key in self._cache:
            return self._cache[key]

        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=True,
        )

        if df.empty:
            raise ValueError(
                f"yfinance returned empty data for {symbol} "
                f"between {start} and {end}"
            )

        df = df[["Open", "High", "Low", "Close", "Volume"]]
        df.index = pd.DatetimeIndex(df.index).tz_localize(None)

        series = PriceSeries(symbol=symbol, df=df)
        self._cache[key] = series
        return series

    def fetch_window(
        self,
        symbol: str,
        anchor: date,
        pre_days: int,
        post_days: int,
        *,
        buffer_days: int = 15,
    ) -> PriceSeries:
        """Fetch a window around an anchor date with buffer to handle holidays."""
        start = anchor - timedelta(days=pre_days + buffer_days)
        end = anchor + timedelta(days=post_days + buffer_days)
        return self.fetch(symbol, start, end)


def trading_day_at_or_before(df: pd.DataFrame, target: date) -> pd.Timestamp | None:
    """Find the latest trading day on or before target. Returns None if none exist."""
    ts = pd.Timestamp(target)
    valid_idx = df.index[df.index <= ts]
    if len(valid_idx) == 0:
        return None
    return valid_idx[-1]


def trading_day_at_or_after(df: pd.DataFrame, target: date) -> pd.Timestamp | None:
    """Find the earliest trading day on or after target. Returns None if none exist."""
    ts = pd.Timestamp(target)
    valid_idx = df.index[df.index >= ts]
    if len(valid_idx) == 0:
        return None
    return valid_idx[0]


def close_at(df: pd.DataFrame, target_day: pd.Timestamp) -> float:
    return float(df.loc[target_day, "Close"])
