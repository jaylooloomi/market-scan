"""Macro / commodity indices — requests-based (FRED), NOT yfinance.

IMPORTANT: yfinance pulls in curl_cffi, which corrupts the MCP stdio transport
on Windows (BrokenResourceError). So MCP servers must avoid yfinance. We use
FRED's keyless CSV endpoint (fredgraph.csv) over plain requests, which is
stdio-safe. (yfinance remains fine for the Phase 0 CLI validator — no stdio.)
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import Any

from polydig_mcp.common.errors import SensorError
from polydig_mcp.common.http import polite_get

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# commodity -> FRED series id  (daily unless noted)
COMMODITY_SERIES = {
    "crude": "DCOILWTICO",       # WTI spot, daily
    "wti": "DCOILWTICO",
    "brent": "DCOILBRENTEU",     # Brent spot, daily
    "natgas": "DHHNGSP",         # Henry Hub, daily
    "copper": "PCOPPUSDM",       # global copper price, monthly
    "gold": "GOLDPMGBD228NLBM",  # London gold PM fix, daily
    "aluminum": "PALUMUSDM",     # global aluminum, monthly
}

# Shipping freight indices (SCFI/BDI) have no keyless feed — honest not_implemented.
SHIPPING_NOTE = (
    "SCFI/BDI need a paid Baltic/SSE feed and have no keyless API. "
    "TODO Phase 4: scrape sse.net.cn SCFI weekly print (HTML, needs retry+diff)."
)


def _fred_series(series_id: str, days: int) -> list[tuple[date, float]]:
    resp = polite_get(FRED_CSV, params={"id": series_id})
    rows: list[tuple[date, float]] = []
    reader = csv.reader(io.StringIO(resp.text))
    header = next(reader, None)  # DATE,<id>
    cutoff = date.today() - timedelta(days=days)
    for row in reader:
        if len(row) < 2 or row[1] in (".", ""):
            continue
        try:
            d = datetime.strptime(row[0], "%Y-%m-%d").date()
            v = float(row[1])
        except ValueError:
            continue
        if d >= cutoff:
            rows.append((d, v))
    return rows


def commodity_price(commodity: str, days: int = 60) -> dict[str, Any]:
    key = commodity.lower()
    if key not in COMMODITY_SERIES:
        raise SensorError(
            "unknown_commodity",
            f"'{commodity}' not mapped. Known: {', '.join(sorted(set(COMMODITY_SERIES)))}. "
            f"(urea/fertilizer: no keyless feed — TODO World Bank Pink Sheet.)",
        )
    series = _fred_series(COMMODITY_SERIES[key], days)
    if len(series) < 2:
        raise SensorError("fetch_failed", f"FRED returned insufficient data for {commodity}")
    first_v, last_v = series[0][1], series[-1][1]
    pct = (last_v / first_v - 1.0) if first_v else None
    return {
        "commodity": key,
        "fred_series": COMMODITY_SERIES[key],
        "latest": round(last_v, 4),
        "period_start": round(first_v, 4),
        "pct_change": round(pct, 4) if pct is not None else None,
        "days": days,
        "as_of": series[-1][0].isoformat(),
    }


def shipping_index(index: str = "BDI", days: int = 60) -> dict[str, Any]:
    """No keyless SCFI/BDI feed — return structured not_implemented (honest)."""
    raise SensorError("not_implemented", SHIPPING_NOTE)
