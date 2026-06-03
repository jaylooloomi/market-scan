# price-mcp

行情 / 量能 **安全網**感測器。

> ⚠️ **角色定位**:Price 是 **safety net,不是主要訊號源**。漲停族群代表領先感測器(News/Data/Policy/Roadmap)**漏抓**了早期訊號 —— 它的價值是抓漏,不是追高。

## Tools

| Tool | 說明 | 資料源 |
|---|---|---|
| `get_quote(symbol)` | 最新報價(收盤/漲跌幅/量),接受 `2330` / `2330.TW` / `3163.TWO` | FinMind ✅ |
| `detect_limit_up_cluster(min_size)` | 當日漲停股按產業分群(≥`min_size` 檔成 cluster) | TWSE OpenAPI ✅ |
| `volume_anomaly(symbol, days)` | 最新量 vs 過去 N 日均量的爆量偵測 | FinMind ✅ |

> ⚠️ **不用 yfinance**:`get_quote`/`volume_anomaly` 走 **FinMind**(requests-based),`detect_limit_up_cluster` 走 **TWSE OpenAPI**。yfinance 依賴 curl_cffi 會弄壞 MCP stdio 傳輸,故 server 一律不用(只留在 Phase 0 CLI validator)。

## 範例

```python
from market_scan_mcp.price import server as p
p.get_quote("2330")
p.get_quote("3163.TWO")          # 上櫃用 .TWO
p.detect_limit_up_cluster(min_size=2)
p.volume_anomaly("2603", days=20)
```

## 限制(誠實聲明)

- `detect_limit_up_cluster` 用 TWSE OpenAPI 的 `STOCK_DAY_ALL`,**只有最新交易日**。歷史某日的漲停族群需逐檔查詢(Phase 5+)。
- 涵蓋**上市**(TWSE);上櫃(TPEx)漲停族群需另接 TPEx OpenAPI(TODO)。
- 漲停門檻設 ≥9.5%(台股 ±10%,留 tick/四捨五入餘裕)。
- 漏抓回溯機制(Reviewer 主動回溯 30-90 天找早期訊號)defer 到 Phase 5+。
