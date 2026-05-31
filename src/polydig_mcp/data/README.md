# data-mcp

公開財經數據感測器。FinMind(台股籌碼/法人/財報)+ 商品期貨 + 運價指數。

## Tools

| Tool | 說明 | 資料源 |
|---|---|---|
| `list_datasets()` | 列出 FinMind 別名、商品、運價 proxy | — |
| `get_finmind(dataset, data_id, start_date, end_date, limit)` | 通用 FinMind 查詢 | FinMind API ✅ |
| `get_institutional_flow(stock_id, days)` | 三大法人買賣超 + net-buy 異常分數 | FinMind ✅ |
| `get_commodity_price(commodity, days)` | 商品價 + 期間變化 | FRED CSV(免 key)✅ |
| `get_shipping_index(index, days)` | 運價指數 | **not_implemented**(無免費 SCFI/BDI feed)❌ |
| `get_dram_price()` | DRAM 現貨 | **STUB**(TrendForce 付費)❌ |

FinMind dataset 別名:`price` / `institutional` / `margin` / `shareholding` / `financials` / `per`。
商品(FRED series):crude/wti, brent, natgas, copper(月), gold, aluminum(月)。

> ⚠️ **為何不用 yfinance**:yfinance 依賴 curl_cffi,會污染 MCP 的 stdio 傳輸(Windows 上 `BrokenResourceError`)。所以 MCP server 一律用 requests-based 來源(FinMind / FRED / TWSE OpenAPI)。yfinance 只留在 Phase 0 的 CLI validator(無 stdio 限制)。

## 設定

需要 FinMind token(免費註冊,600 req/hr):

```
# .env (gitignored)
FINMIND_TOKEN=your_token_here
```

沒 token 時 FinMind 工具回 `missing_token` 的 graceful error,不會 crash。

## 範例

```python
from polydig_mcp.data import server as d
d.get_finmind("price", "2330", "2024-01-01", "2024-03-01")
d.get_institutional_flow("2603", days=20)
d.get_commodity_price("copper", days=90)
d.get_shipping_index("BDI", days=60)
```

## 限制(誠實聲明)

- **SCFI/BDI**:無免費 feed(上海航交所/波羅的海皆付費),`get_shipping_index` 回 `not_implemented`。Phase 4 評估爬 sse.net.cn 週報。
- **DRAM 現貨**:TrendForce/DRAMeXchange 付費,目前 stub。Phase 4 評估公開新聞稿或記憶體廠 IR。
- **尿素/化肥**:無免費 feed,`get_commodity_price` 會回 unknown_commodity。Phase 4 評估 World Bank Pink Sheet。
- 銅/鋁是 FRED **月頻**資料(daily 免費 feed 有限);原油/Brent/天然氣是 daily。
- FinMind 免費版 600 req/hr,setup 階段抓全市場需 cache + 分批(Phase 3)。
