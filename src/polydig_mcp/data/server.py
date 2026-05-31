"""data-mcp MCP server.

Tools:
    get_finmind(dataset, data_id, start_date, end_date)  -> raw FinMind rows
    get_institutional_flow(stock_id, days)               -> 三大法人買賣超
    get_commodity_price(commodity, days)                 -> commodity futures
    get_shipping_index(index, days)                      -> freight index (proxy)
    get_us_sector_move(sector, days)                     -> US sector % change (FRED keyless)
    get_dram_price()                                     -> STUB (paywalled)
    list_datasets()                                      -> available helpers
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from polydig_mcp.common.envelope import Signal, error_signal
from polydig_mcp.common.errors import SensorError
from polydig_mcp.data import finmind, macro

mcp = FastMCP("polydig-data")


@mcp.tool()
def list_datasets() -> dict[str, Any]:
    """List FinMind dataset aliases, mapped commodities, and shipping proxies."""
    return {
        "finmind_datasets": finmind.DATASETS,
        "commodities": sorted(set(macro.COMMODITY_SERIES)),
        "shipping": "not_implemented (no keyless SCFI/BDI feed — see README)",
    }


@mcp.tool()
def get_finmind(
    dataset: str,
    data_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Generic FinMind passthrough. `dataset` is a friendly alias (price,
    institutional, margin, shareholding, financials, per) or a raw dataset id."""
    try:
        rows = finmind.query(dataset, data_id, start_date, end_date)
    except SensorError as e:
        return error_signal("data.finmind", "finmind_query", e.message, dataset=dataset)
    return Signal(
        source="data.finmind",
        signal_type="finmind_query",
        content={"dataset": dataset, "data_id": data_id, "rows": rows[-limit:], "count": len(rows)},
        anomaly_score=None,
    ).to_dict()


@mcp.tool()
def get_institutional_flow(stock_id: str, days: int = 20) -> dict[str, Any]:
    """三大法人買賣超 over the last `days` days, with a net-buy anomaly score."""
    start = (date.today() - timedelta(days=days * 2)).isoformat()  # *2 for trading-day gaps
    try:
        rows = finmind.query("institutional", stock_id, start)
    except SensorError as e:
        return error_signal("data.finmind", "institutional_flow", e.message, stock_id=stock_id)

    # FinMind returns per-investor-type buy/sell; net = buy - sell summed.
    net_by_day: dict[str, float] = {}
    for r in rows:
        d = r.get("date")
        net_by_day[d] = net_by_day.get(d, 0.0) + (r.get("buy", 0) - r.get("sell", 0))
    series = [net_by_day[d] for d in sorted(net_by_day)]
    recent_net = sum(series[-5:]) if series else 0.0
    avg_abs = (sum(abs(x) for x in series) / len(series)) if series else 0.0
    score = min(1.0, abs(recent_net) / (avg_abs * 5)) if avg_abs else None

    return Signal(
        source="data.institutional",
        signal_type="institutional_flow",
        content={
            "stock_id": stock_id,
            "recent_5d_net_shares": recent_net,
            "days_observed": len(series),
            "direction": "net_buy" if recent_net > 0 else "net_sell",
        },
        anomaly_score=round(score, 3) if score is not None else None,
    ).to_dict()


@mcp.tool()
def get_commodity_price(commodity: str, days: int = 60) -> dict[str, Any]:
    """Commodity futures price + period change (copper, crude, natgas, gold, ...).

    pct_change feeds a simple momentum anomaly_score (|change| capped at 1.0).
    """
    try:
        data = macro.commodity_price(commodity, days)
    except SensorError as e:
        return error_signal("data.commodity", "commodity_price", e.message, commodity=commodity)
    pct = data.get("pct_change")
    score = min(1.0, abs(pct) * 2) if pct is not None else None
    return Signal(
        source="data.commodity",
        signal_type="commodity_price",
        content=data,
        anomaly_score=round(score, 3) if score is not None else None,
    ).to_dict()


@mcp.tool()
def get_shipping_index(index: str = "BDI", days: int = 60) -> dict[str, Any]:
    """Shipping freight index (ETF proxy — true SCFI/BDI paywalled, see note)."""
    try:
        data = macro.shipping_index(index, days)
    except SensorError as e:
        return error_signal("data.shipping", "shipping_index", e.message, index=index)
    pct = data.get("pct_change")
    score = min(1.0, abs(pct) * 2) if pct is not None else None
    return Signal(
        source="data.shipping",
        signal_type="shipping_index",
        content=data,
        anomaly_score=round(score, 3) if score is not None else None,
    ).to_dict()


@mcp.tool()
def get_us_sector_move(sector: str = "nasdaq", days: int = 30) -> dict[str, Any]:
    """US sector / index % change (FRED keyless, requests-based, stdio-safe).

    sector: nasdaq | sp500 | us_10y | vix
    (PHLX Semiconductor/SOX has no keyless FRED feed — semis covered via nasdaq.)
    Returns the % change over the period plus the TW family mapping
    (so Scout can translate a strong US move to a TW candidate theme).
    """
    try:
        data = macro.us_sector_move(sector, days)
    except SensorError as e:
        return error_signal("data.us_sector", "us_sector_move", e.message, sector=sector)
    pct = data.get("pct_change")
    score = min(1.0, abs(pct) * 3) if pct is not None else None
    tw_families = macro.US_TW_MAPPING.get(sector.lower(), [])
    return Signal(
        source="data.us_sector",
        signal_type="us_sector_move",
        content={**data, "tw_theme_families": tw_families},
        anomaly_score=round(score, 3) if score is not None else None,
    ).to_dict()


@mcp.tool()
def get_dram_price() -> dict[str, Any]:
    """DRAM/NAND spot price — STUB (TrendForce/DRAMeXchange paywalled)."""
    try:
        data = macro.dram_spot()
    except SensorError as e:
        return error_signal("data.dram", "dram_price", e.message)
    return data


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
