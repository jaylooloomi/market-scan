# PolyDig — 繁體中文說明

> 台股題材**早期**偵測 —— 在事件還沒發酵時抓到。

PolyDig 是**研究助理**(不自動下單)。掃描 5 個訊號源,推理「事件 → 受益族群」的因果樹,找歷史對應,每日產出中文研究報告,讓你比市場早 N 天/週發現題材。

## 系統靈魂
> **找的是事件還沒發酵、有領先效果的訊號。**

若提報時股票已漲一波,這系統就沒價值。Price 是唯一例外 —— safety net,補抓漏掉的領先訊號。

## 安裝
```bash
pip install -e .                 # 核心(感測器 + headless pipeline)
pip install -e ".[agents]"       # 加 anthropic + chromadb(向量 RAG + LLM Reviewer)
```
建立 `.env`(已 gitignore)放 FinMind token(免費,600 req/hr)+(選用)Telegram 推播:
```
FINMIND_TOKEN=你的_token
TELEGRAM_BOT_TOKEN=你的_bot_token     # 向 @BotFather 申請
TELEGRAM_CHAT_ID=你的_chat_id          # 你的 Telegram user id;需先對 bot 按 /start
```
沒 token 時 FinMind 工具回 graceful error,RSS / FRED / TWSE 感測器照常運作。

**Telegram 推播**:設好上面兩個 Telegram 變數後,`polydig-daily --telegram` 會把報告推到 Telegram;或用模組推任意文字:`python -m polydig_mcp.reporting.telegram <檔案>`。每日 routine 已設定成推送 Claude 整理過的乾淨摘要。

## 用法

**A. 當 Claude Code plugin —— 純自然語言:**
「今天有什麼?」、「幫我研究 矽光子」、「scan 一下台股」,或 `/dig today`、`/dig research <主題>`。

**B. Headless(排程 / CI):**
```bash
polydig-daily --mode dry      # 啟發式 Reviewer,離線可跑(demo)
polydig-daily --mode llm      # LLM Reviewer(需 ANTHROPIC_API_KEY)
polydig-daily --persist ./vector_db   # 啟用 Chroma 向量 RAG
# → 產出 reports/YYYY-MM-DD.md
```

## 五個感測器
- **news-mcp**:中文/英文 RSS + Google Trends(+ PTT stub)
- **data-mcp**:FinMind(籌碼/法人/財報)+ FRED 商品價
- **price-mcp**(safety net):FinMind 報價 + TWSE 漲停族群偵測
- **policy-mcp**:政府公告(RSS 可行者,其餘待爬蟲)
- **roadmap-mcp**:法說會關鍵詞抽取(逐字稿來源待補)

## 誠實的限制
- Phase 0 只驗證「已知標的/日期下領先訊號**存在**」;即時辨識族群是 Phase 2 的賭注。
- `--mode dry` 是啟發式替身,不等於 LLM 的因果推理;真實推理走 Claude(plugin subagent 或 `--mode llm`)。
- MCP server 不用 yfinance(curl_cffi 會弄壞 Windows stdio 傳輸),改用 FinMind / FRED / TWSE。
- SCFI/BDI、DRAM 現貨、PTT、政府 HTML、法說逐字稿:無免費穩定來源,以 stub + TODO 誠實標示。

## 疑難排解
| 症狀 | 處理 |
|---|---|
| FinMind 工具回 `missing_token` | 在 `.env` 設 `FINMIND_TOKEN` |
| `get_shipping_index` 回 not_implemented | 預期行為(無免費 SCFI/BDI feed) |
| Windows console 中文亂碼 | 顯示問題;資料本身是 UTF-8,設 `PYTHONIOENCODING=utf-8` |
| Chroma 首次慢 | 下載 ~79MB embedding 模型;不裝 chromadb 則自動用 token-overlap fallback |
| MCP server `BrokenResourceError` | 確認 server 程式沒引入 yfinance/curl_cffi(改用 requests-based 來源) |
