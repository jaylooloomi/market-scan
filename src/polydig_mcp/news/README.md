# news-mcp

新聞異常 + 趨勢感測器。偵測「哪個詞在新聞裡突然變熱」與搜尋熱度,**不做語意判讀**(那是 Reviewer agent 的事)。

## Tools

| Tool | 說明 |
|---|---|
| `list_sources()` | 列出可讀的 RSS 來源 |
| `fetch_news(source, since_days, query, limit)` | 抓近期新聞;`source` 可填 feed id / 語言(`zh`/`en`)/ 類別(`finance`/`technology`),`None`=全部 |
| `detect_news_anomaly(window_days, threshold, source, max_terms)` | 偵測近期 vs 前期的詞頻 spike,回傳異常訊號(含 `anomaly_score`) |
| `google_trends_check(keyword, region, timeframe)` | 查 Google 搜尋熱度趨勢(pytrends,無官方 API,會被 429 限流 → graceful error) |
| `fetch_ptt(board, pages)` | **STUB** — PTT/Dcard 反爬,Phase 5+ 再做 |

## 來源(RSS)

中文:經濟日報、自由財經、中央社財經 / 英文:CNBC Top、CNBC Technology、MarketWatch。
任一 feed 掛掉只會回該 feed 的 error signal,其餘照常返回(graceful failure)。

## 範例

```python
from polydig_mcp.news import server as s

s.fetch_news(source="zh", since_days=2.0, query="矽光子", limit=20)
s.detect_news_anomaly(window_days=1.0, threshold=0.3)
s.google_trends_check("CPO", region="TW", timeframe="now 7-d")
```

## 限制(誠實聲明)

- `detect_news_anomaly` 比較的是 **feed 當前可取得視窗內**的近期 vs 前期詞頻。真正跨週/跨月的時間基線需要 Phase 3 的歷史儲存層。
- 中文斷詞用 2-4 字 CJK chunk 的粗略法,非真正分詞;感測器刻意保持「笨」,語意交給 Reviewer。
- Google Trends 限流頻繁,生產環境需 cache + 退避。
