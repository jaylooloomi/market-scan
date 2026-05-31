"""price-mcp MCP server (safety net).

Tools:
    get_quote(symbol)                  -> latest price/volume
    detect_limit_up_cluster(min_size)  -> today's limit-up clusters by industry
    volume_anomaly(symbol, days)       -> volume spike vs trailing average

Data backend: FinMind + TWSE OpenAPI (both requests-based). NOT yfinance —
yfinance pulls in curl_cffi which corrupts the MCP stdio transport on Windows.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from polydig_mcp.common.envelope import Signal, error_signal
from polydig_mcp.common.errors import SensorError
from polydig_mcp.data import finmind
from polydig_mcp.price import twse

mcp = FastMCP("polydig-price")


def _stock_id(symbol: str) -> str:
    """Strip .TW/.TWO suffix → bare FinMind stock_id (covers TWSE + TPEx)."""
    return symbol.split(".")[0]


def _finmind_prices(stock_id: str, days: int) -> list[dict[str, Any]]:
    start = (date.today() - timedelta(days=days)).isoformat()
    rows = finmind.query("price", stock_id, start)
    rows.sort(key=lambda r: r.get("date", ""))
    return rows


@mcp.tool()
def get_quote(symbol: str) -> dict[str, Any]:
    """Latest quote for a Taiwan stock (FinMind). Accepts 2330, 2330.TW, 3163.TWO."""
    sid = _stock_id(symbol)
    try:
        rows = _finmind_prices(sid, days=10)
    except SensorError as e:
        return error_signal("price.quote", "quote", e.message, symbol=sid)
    if not rows:
        return error_signal("price.quote", "quote", f"no data for {sid}", symbol=sid)

    last = rows[-1]
    close = last.get("close")
    prev_close = rows[-2].get("close") if len(rows) > 1 else last.get("open")
    pct = (close / prev_close - 1.0) if prev_close else None
    return Signal(
        source="price.quote",
        signal_type="quote",
        content={
            "symbol": sid,
            "close": close,
            "pct_change": round(pct, 4) if pct is not None else None,
            "volume": last.get("Trading_Volume"),
            "as_of": last.get("date"),
        },
        anomaly_score=None,
    ).to_dict()


@mcp.tool()
def detect_limit_up_cluster(min_size: int = 2) -> dict[str, Any]:
    """Detect today's limit-up clusters grouped by industry (SAFETY NET).

    A cluster of limit-ups means the leading sensors missed an early signal —
    the Reviewer should backfill-investigate (Phase 5+). Uses TWSE OpenAPI
    (latest trading day only; historical dates need per-stock queries).
    """
    try:
        result = twse.limit_up_clusters(min_cluster_size=min_size)
    except SensorError as e:
        return error_signal("price.cluster", "limit_up_cluster", e.message)

    n_clusters = len(result["clusters"])
    score = min(1.0, n_clusters / 5.0) if n_clusters else 0.0
    return Signal(
        source="price.cluster",
        signal_type="limit_up_cluster",
        content={
            "total_limit_up": result["total_limit_up"],
            "cluster_count": n_clusters,
            "clusters": result["clusters"],
            "note": "safety-net signal: leading sensors likely missed this; backfill candidate",
        },
        anomaly_score=round(score, 3),
    ).to_dict()


@mcp.tool()
def volume_anomaly(symbol: str, days: int = 20) -> dict[str, Any]:
    """Detect a volume spike: latest volume vs trailing `days`-day average (FinMind)."""
    sid = _stock_id(symbol)
    try:
        rows = _finmind_prices(sid, days=days * 2 + 10)
    except SensorError as e:
        return error_signal("price.volume", "volume_anomaly", e.message, symbol=sid)
    vols = [r.get("Trading_Volume") for r in rows if r.get("Trading_Volume") is not None]
    if len(vols) < 5:
        return error_signal("price.volume", "volume_anomaly", f"insufficient data for {sid}", symbol=sid)

    latest = vols[-1]
    trailing = vols[-(days + 1):-1] or vols[:-1]
    avg = sum(trailing) / len(trailing) if trailing else 0
    ratio = (latest / avg) if avg else None
    score = min(1.0, (ratio - 1.0) / 3.0) if ratio and ratio > 1 else 0.0
    return Signal(
        source="price.volume",
        signal_type="volume_anomaly",
        content={
            "symbol": sid,
            "latest_volume": int(latest),
            "avg_volume": int(avg),
            "volume_ratio": round(ratio, 2) if ratio else None,
            "days": days,
        },
        anomaly_score=round(score, 3),
    ).to_dict()


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
