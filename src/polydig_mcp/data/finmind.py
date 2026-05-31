"""FinMind REST API wrapper.

FinMind exposes Taiwan market data (prices, institutional flows, margin, chips,
financials) at https://api.finmindtrade.com/api/v4/data. Free tier = 600 req/hr;
token lives in .env (FINMIND_TOKEN), never in code.
"""
from __future__ import annotations

from typing import Any

from polydig_mcp.common.errors import SensorError
from polydig_mcp.common.http import polite_get
from polydig_mcp.common.settings import get_settings

API_URL = "https://api.finmindtrade.com/api/v4/data"

# Common datasets surfaced as friendly names (full list: finmindtrade.com docs).
DATASETS = {
    "price": "TaiwanStockPrice",
    "institutional": "TaiwanStockInstitutionalInvestorsBuySell",
    "margin": "TaiwanStockMarginPurchaseShortSale",
    "shareholding": "TaiwanStockShareholding",
    "financials": "TaiwanStockFinancialStatements",
    "per": "TaiwanStockPER",
}


def query(
    dataset: str,
    data_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Raw FinMind query. `dataset` may be a friendly alias or a raw dataset id.

    Raises SensorError on missing token / API failure.
    """
    settings = get_settings()
    if not settings.has_finmind:
        raise SensorError(
            "missing_token",
            "FINMIND_TOKEN not set in .env — FinMind data unavailable (see README setup)",
        )

    params: dict[str, str] = {"dataset": DATASETS.get(dataset, dataset)}
    if data_id:
        params["data_id"] = data_id
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    params["token"] = settings.finmind_token  # type: ignore[assignment]

    resp = polite_get(API_URL, params=params)
    payload = resp.json()
    if payload.get("msg") != "success":
        raise SensorError("api_error", f"FinMind: {payload.get('msg', 'unknown error')}")
    return payload.get("data", [])
