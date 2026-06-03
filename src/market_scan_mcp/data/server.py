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

from market_scan_mcp.common.envelope import Signal, error_signal
from market_scan_mcp.common.errors import SensorError
from market_scan_mcp.data import finmind, macro

mcp = FastMCP("market-scan-data")


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


import os as _os


def _db_path(explicit: str | None) -> str:
    return explicit or _os.getenv("MARKET_SCAN_DB", "market-scan.db")


@mcp.tool()
def ingest_shipping_index(
    name: str, date: str, value: float, source: str = "manual", db_path: str | None = None
) -> dict[str, Any]:
    """Feed one freight-index reading (e.g. SCFI for a week) into history.

    SCFI/BDI have no keyless live feed (sse.net.cn login-gated, Baltic paywalled),
    so values are ingested here — weekly manual entry, or a future paid/auth source.
    name e.g. "SCFI"; date "YYYY-MM-DD"; value the index number.
    """
    try:
        from market_scan_mcp.storage.db import MarketScanDB
        db = MarketScanDB(_db_path(db_path))
        db.upsert_index_value(name.upper(), date, float(value), source)
        n = len(db.index_series(name.upper(), lookback_days=3650))
        db.close()
    except Exception as e:  # noqa: BLE001
        return error_signal("data.shipping", "shipping_ingest", str(e), index=name)
    return Signal(
        source="data.shipping",
        signal_type="shipping_ingest",
        content={"index": name.upper(), "date": date, "value": value, "stored_points": n},
        anomaly_score=None,
    ).to_dict()


@mcp.tool()
def get_shipping_index(index: str = "SCFI", days: int = 180, db_path: str | None = None) -> dict[str, Any]:
    """Freight-index anomaly over the stored history (data-leads-price sensor).

    Computes a streak + magnitude + z-score anomaly on the index series fed via
    `ingest_shipping_index`. Returns a graceful note if no history is stored yet
    (no keyless SCFI/BDI feed — see ingest_shipping_index).
    """
    try:
        from market_scan_mcp.data.shipping import (
            EASTMONEY_INDICATORS, detect_index_anomaly, fetch_eastmoney_index,
        )
        from market_scan_mcp.storage.db import MarketScanDB
        db = MarketScanDB(_db_path(db_path))
        # Auto-scrape from East Money (free, has history) where available; persist.
        if index.upper() in EASTMONEY_INDICATORS:
            try:
                for dd, vv in fetch_eastmoney_index(index.upper()):
                    db.upsert_index_value(index.upper(), dd, vv, "eastmoney")
            except SensorError:
                pass  # fall back to whatever is already stored
        series = db.index_series(index.upper(), lookback_days=days)
        db.close()
    except Exception as e:  # noqa: BLE001
        return error_signal("data.shipping", "shipping_index", str(e), index=index)

    if not series:
        return error_signal(
            "data.shipping", "shipping_index",
            f"no data for {index.upper()} — East Money auto-scrape returned nothing and no "
            "stored history. SCFI(container) is login-gated; feed via ingest_shipping_index.",
            index=index.upper(),
        )

    result = detect_index_anomaly(series)
    result["index"] = index.upper()
    result["as_of"] = series[-1][0]
    return Signal(
        source="data.shipping",
        signal_type="shipping_index",
        content=result,
        raw_url="https://data.eastmoney.com/cjsj/hyzs_EMI00107664.html",
        anomaly_score=result.get("anomaly_score"),
    ).to_dict()


@mcp.tool()
def get_scfi_signal() -> dict[str, Any]:
    """SCFI (container freight, 長榮/陽明/萬海) direction/momentum from FREE news.

    The numeric SCFI composite is login-gated at sse.net.cn, so this derives the
    leading signal (rising/falling, consecutive-rise streak, % magnitude) from
    Google News RSS headlines — free, requests-based, stdio-safe.
    """
    try:
        from market_scan_mcp.data.shipping import fetch_scfi_news_signal
        data = fetch_scfi_news_signal()
    except SensorError as e:
        return error_signal("data.scfi", "scfi_signal", e.message)
    except Exception as e:  # noqa: BLE001
        return error_signal("data.scfi", "scfi_signal", str(e))
    return Signal(
        source="data.scfi",
        signal_type="scfi_signal",
        content=data,
        raw_url=(data["headlines"][0]["link"] if data.get("headlines") else None),
        anomaly_score=data.get("anomaly_score"),
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


@mcp.tool()
def get_history_match(query: str, n_results: int = 3) -> dict[str, Any]:
    """Retrieve the most similar historical themes (themes.json) for the Reviewer's
    歷史對應 step. Loads the bundled seed DB via the INSTALLED PACKAGE (not a CWD
    file path), so it works after a marketplace install regardless of working dir.
    Offline-capable (token-overlap fallback when Chroma isn't installed).
    """
    try:
        from market_scan_mcp.history.store import ThemeStore
        matches = [m.to_dict() for m in ThemeStore().query(query, n_results=n_results)]
    except Exception as e:  # noqa: BLE001
        return error_signal("data.history", "history_match", str(e), query=query)
    return Signal(
        source="data.history",
        signal_type="history_match",
        content={"query": query, "matches": matches},
        anomaly_score=None,
    ).to_dict()


@mcp.tool()
def get_crash_watch(days: int = 120, threshold: int = 2) -> dict[str, Any]:
    """Risk-off confluence from FRED structural-stress indicators — DOWNSIDE sensor.

    Watches the yield curve (T10Y3M), HY credit spread (BAMLH0A0HYM2) and VIX
    (VIXCLS), all keyless FRED. Fires `risk_off` only when >= `threshold` indicators
    are stressed at once (deliberately high bar to suppress false positives — e.g.
    the 2022-23 inversion that produced no recession). This is a **de-risk CAUTION
    signal, NOT a crash predictor**; `threshold` needs out-of-sample calibration.
    See docs/research/02-crash-precursors.md.
    """
    try:
        from market_scan_mcp.data.crashwatch import crash_watch_signal
        data = crash_watch_signal(days=days, threshold=threshold)
    except SensorError as e:
        return error_signal("data.crashwatch", "risk_off_confluence", e.message)
    except Exception as e:  # noqa: BLE001
        return error_signal("data.crashwatch", "risk_off_confluence", str(e))
    return Signal(
        source="data.crashwatch",
        signal_type="risk_off_confluence",
        content=data,
        raw_url="https://fred.stlouisfed.org/series/T10Y3M",
        anomaly_score=data.get("score"),
    ).to_dict()


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
