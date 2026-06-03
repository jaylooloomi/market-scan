"""TWSE OpenAPI client.

Free, no-auth JSON endpoints from the Taiwan Stock Exchange:
  - STOCK_DAY_ALL: every listed stock's latest trading-day OHLC + change
  - t187ap03_L: listed-company master data (includes 產業別 / industry)

Limit-up detection uses these because one call covers the whole market, vs
~1000 per-stock yfinance calls.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from market_scan_mcp.common.http import polite_get

STOCK_DAY_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
COMPANY_INFO = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

# Taiwan daily price limit is ±10%; treat >= 9.5% as limit-up (rounding/ticks).
LIMIT_UP_PCT = 0.095

# TWSE 產業別 code -> readable name (t187ap03_L uses numeric codes).
INDUSTRY_NAMES = {
    "01": "水泥", "02": "食品", "03": "塑膠", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙",
    "10": "鋼鐵", "11": "橡膠", "12": "汽車", "14": "建材營造",
    "15": "航運", "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨",
    "20": "其他", "21": "化學", "22": "生技醫療", "23": "油電燃氣",
    "24": "半導體", "25": "電腦及週邊設備", "26": "光電", "27": "通信網路",
    "28": "電子零組件", "29": "電子通路", "30": "資訊服務", "31": "其他電子",
    "32": "文化創意", "33": "農業科技", "34": "電子商務", "35": "綠能環保",
    "36": "數位雲端", "37": "運動休閒", "38": "居家生活",
}


def industry_name(code: str) -> str:
    """Translate a 產業別 code to a readable name, falling back to the code."""
    return INDUSTRY_NAMES.get(str(code).zfill(2), str(code))


def _to_float(x: Any) -> float | None:
    try:
        return float(str(x).replace(",", ""))
    except (ValueError, TypeError):
        return None


@lru_cache(maxsize=1)
def industry_map() -> dict[str, str]:
    """code -> 產業別. Cached for the process lifetime."""
    resp = polite_get(COMPANY_INFO)
    out: dict[str, str] = {}
    for row in resp.json():
        code = row.get("公司代號") or row.get("Code")
        ind = row.get("產業別") or row.get("Industry") or "未分類"
        if code:
            out[str(code)] = ind
    return out


def all_stock_day() -> list[dict[str, Any]]:
    """All listed stocks for the latest trading day, normalized."""
    resp = polite_get(STOCK_DAY_ALL)
    rows = []
    for r in resp.json():
        close = _to_float(r.get("ClosingPrice"))
        change = _to_float(r.get("Change"))
        if close is None or change is None:
            continue
        prev = close - change
        pct = (change / prev) if prev else None
        rows.append(
            {
                "code": r.get("Code"),
                "name": r.get("Name"),
                "close": close,
                "change": change,
                "pct_change": round(pct, 4) if pct is not None else None,
                "volume": _to_float(r.get("TradeVolume")),
            }
        )
    return rows


def limit_up_clusters(min_cluster_size: int = 2) -> dict[str, Any]:
    """Group today's limit-up stocks by industry. A cluster (>= min_cluster_size
    limit-ups in one industry) is the safety-net trigger."""
    stocks = all_stock_day()
    ind = industry_map()
    clusters: dict[str, list[dict[str, Any]]] = {}
    for s in stocks:
        if s["pct_change"] is not None and s["pct_change"] >= LIMIT_UP_PCT:
            industry = industry_name(ind.get(str(s["code"]), "未分類"))
            clusters.setdefault(industry, []).append(
                {"code": s["code"], "name": s["name"], "pct_change": s["pct_change"]}
            )
    sized = {k: v for k, v in clusters.items() if len(v) >= min_cluster_size}
    return {
        "total_limit_up": sum(len(v) for v in clusters.values()),
        "clusters": dict(sorted(sized.items(), key=lambda kv: len(kv[1]), reverse=True)),
    }
