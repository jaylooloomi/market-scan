# Market Scan

> **EN** — Leading-edge **scanner** for the Taiwan stock market: surface emerging themes **before** the market reacts, and flag market-wide **crash risk**.
> **中** — 台股**領先掃描器**:在市場反應**之前**發現正在成形的題材,並對大盤**崩盤風險**示警。

A research assistant, **not** an auto-trader. · 研究助理,**不下單、非投資建議**。

![License](https://img.shields.io/badge/license-MIT-green)

**[English](#english) · [繁體中文](#繁體中文)**

---

## English

**Market Scan** scans signal sources for anomalies, reasons out a causal propagation tree of
beneficiary Taiwan stocks, retrieves historical analogues, and writes a daily Chinese-language
research report — surfacing themes while the event is still early. A built-in **crash-watch**
flags market-wide risk-off conditions from leading macro signals (yield curve · credit spread · VIX).

### North star
> **Find signals where the event hasn't yet played out and still has leading power.**

Every feature must pass one test: *"Does this help the user discover it N days/weeks before the
market?"* A signal that only fires after a sector has already rallied — however accurate — is
**not** what this is for. (Price is the sole exception: a deliberate safety net for what the
leading sensors missed.)

### Architecture
```
 news   data   price (safety net)   policy   roadmap   +  crash-watch   ← MCP sensor tools
   \      \          |                 /        /              │  (yield curve · credit spread · VIX)
        (sensors do anomaly detection only — no semantics)
                              │
       Scout (Claude Haiku) — flags anomalies, high false-positive tolerance
                              │
       Reviewer (Claude Sonnet) — cluster ID → causal tree (tier 1/2/3) →
                              historical RAG → grade: strong / watchlist / reject
                              │
       Daily report (中文) — graded themes + a market-risk (crash-watch) banner
```

### Install

**A. From the Claude Code marketplace (recommended)**
```text
/plugin marketplace add jaylooloomi/market-scan
/plugin install market-scan@market-scan
/reload-plugins
```
This installs the skill, the `/dig` command, the Scout/Reviewer agents, and the MCP sensor servers.

**Prerequisite — `uv`:** the sensors run as Python MCP servers via `uvx`, so you need
[`uv`](https://docs.astral.sh/uv/) on your PATH (one self-contained binary). On first launch
`uvx` builds Market Scan + deps into a cached env — **no manual `pip`, no PyPI account needed**.
No `uv`? After installing, run **`/market-scan-setup`** — it checks for `uv`, installs it (with
your OK) and pre-warms the sensors. Manual install: macOS/Linux
`curl -LsSf https://astral.sh/uv/install.sh | sh` · Windows
`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`, then
**restart Claude Code** (MCP servers read `PATH` at startup).

**FinMind token optional:** FRED / TWSE / RSS / **crash-watch** work with zero config; only the
FinMind-backed tools (institutional flow · quotes · volume) need a token.

**B. Local / development**
```bash
pip install -e ".[schedule,dev]"   # core + apscheduler + pytest
pip install -e ".[agents]"         # + anthropic + chromadb (vector RAG, LLM reviewer)
```
Create `.env` (gitignored) for the FinMind token (free, 600 req/hr — register at finmindtrade.com):
```
FINMIND_TOKEN=your_token_here
```

### Use it
**Natural language (plugin):**
> "What's up today?" · "Research silicon photonics" · "Check crash risk" · `/dig today` · `/dig research <theme>`

**Headless (cron / CI):**
```bash
market-scan-daily --mode dry            # heuristic reviewer, offline-friendly demo
market-scan-daily --mode llm            # LLM reviewer (needs ANTHROPIC_API_KEY)
market-scan-daily --persist ./vector_db # enable Chroma vector RAG
# → writes reports/YYYY-MM-DD.md (with a market-risk banner)
```

### Sensors
| Sensor | What it watches | Backend |
|---|---|---|
| **news** | headline-volume anomalies · Google Trends spikes | RSS · pytrends |
| **data** | institutional flow · commodities/shipping/SCFI · US sectors · **crash-watch** | FinMind · FRED · East Money |
| **price** *(safety net)* | limit-up clusters · volume anomalies · quotes | FinMind · TWSE OpenAPI |
| **policy** | government policy / subsidy announcements | gov RSS |
| **roadmap** | earnings-call / roadmap signals | text analysis |

All sensors return a uniform envelope `{timestamp, source, signal_type, content, raw_url, anomaly_score}`
and **fail gracefully** — a dead feed or missing token returns a structured error, never a crash.

### Validation
- **Phase 0 backtest** — `market-scan-validator --config cases.json`: 15 historical test points,
  4/5 cases strong-leading → **GO** (concept proof).
- **Replay harness** (`reviewer/replay.py`) — real GDELT news replay for out-of-sample lead-time.
- **Net-alpha** (`market_scan_validator/net_alpha.py`) — converts gross backtest returns into
  realistic net numbers (cost · limit-up · exit rules · theme-aware hold).

### Honest limitations
- **Live detection is the open bet:** Phase 0 proves leading signals *exist* on hindsight-selected
  tickers/dates; picking the right sector in real time, with no future info, is unproven
  (see `reports/audit/` for the architect + VC analysis).
- **No yfinance in the MCP servers** — it pulls in `curl_cffi`, which corrupts the MCP stdio
  transport; servers use requests-based sources. yfinance stays in the Phase 0 CLI only.
- **Some sources are best-effort:** SCFI/BDI via East Money + Google News RSS; DRAM spot, PTT/Dcard,
  some gov HTML, earnings transcripts remain honest stubs.
- **Crash-watch is a de-risk caution signal, not a crash predictor** — see `docs/research/`.

### Tech stack
Python 3.11+ · MCP (FastMCP) · Anthropic Claude SDK · FinMind / FRED / TWSE OpenAPI · Chroma · SQLite.
Distributed as a Claude Code plugin; sensors launched via `uvx`. Python package: `market_scan_mcp`.

---

## 繁體中文

**Market Scan** 掃描多個訊號源的異常,推理出受惠台股的**因果傳導樹**,檢索**歷史對應**案例,
並產生每日中文研究報告 —— 在事件還**早期**時就把題材浮出來。內建 **crash-watch**,從領先總經
訊號(殖利率曲線 · 信用利差 · VIX)對大盤 **risk-off / 崩盤風險**示警。

### 系統靈魂(North Star)
> **找的是「事件還沒發酵、仍有領先效果」的訊號。**

每個功能都要通過一個測試:*「這能不能幫使用者比市場早 N 天/週發現?」* 一個只在族群漲完後才觸發的
訊號 —— 再準也**不是**這系統要的。(Price 是唯一例外:刻意當 safety net,補抓領先感測器漏掉的。)

### 架構
```
 news   data   price(safety net)   policy   roadmap   +  crash-watch   ← MCP 感測器工具
   \      \          |                /        /             │  (殖利率曲線 · 信用利差 · VIX)
            (感測器只做異常偵測 —— 不做語意判斷)
                              │
       Scout(Claude Haiku)—— 標記異常,高假陽性容忍
                              │
       Reviewer(Claude Sonnet)—— 族群識別 → 因果樹(一/二/三階)→
                              歷史對應 RAG → 分級:強訊號 / 觀察 / 駁回
                              │
       每日中文報告 —— 分級題材 + 今日大盤風險(crash-watch)橫幅
```

### 安裝

**A. 從 Claude Code marketplace(推薦)**
```text
/plugin marketplace add jaylooloomi/market-scan
/plugin install market-scan@market-scan
/reload-plugins
```
這會裝上 skill、`/dig` 指令、Scout/Reviewer agents,以及 5 個 MCP 感測器 server。

**前置需求 — `uv`:** 感測器是透過 `uvx` 啟動的 Python MCP server,所以你的 PATH 上要有
[`uv`](https://docs.astral.sh/uv/)(單一執行檔)。第一次啟動時 `uvx` 會把 Market Scan + 依賴
build 進快取環境 —— **不用手動 `pip`、不用 PyPI 帳號**。
沒有 `uv`?裝完 plugin 後跑 **`/market-scan-setup`** —— 它會檢查 `uv`、徵得你同意後安裝、並預熱
感測器。手動安裝:macOS/Linux `curl -LsSf https://astral.sh/uv/install.sh | sh`;Windows
`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`,然後
**重啟 Claude Code**(MCP server 在啟動時才讀 PATH)。

**FinMind token 可選:** FRED / TWSE / RSS / **crash-watch** 免設定就能用;只有 FinMind 那幾個
工具(法人進出 · 報價 · 量能)需要 token。

**B. 本地 / 開發**
```bash
pip install -e ".[schedule,dev]"   # 核心 + apscheduler + pytest
pip install -e ".[agents]"         # + anthropic + chromadb(向量 RAG、LLM reviewer)
```
在專案根目錄建 `.env`(已 gitignore)放 FinMind token(免費,600 次/小時,到 finmindtrade.com 註冊):
```
FINMIND_TOKEN=你的token
```

### 使用
**自然語言(plugin):**
> 「今天有什麼?」 · 「幫我研究 矽光子」 · 「看一下大盤崩盤風險」 · `/dig today` · `/dig research <主題>`

**Headless(排程 / CI):**
```bash
market-scan-daily --mode dry            # 啟發式 reviewer,離線可跑的 demo
market-scan-daily --mode llm            # LLM reviewer(需 ANTHROPIC_API_KEY)
market-scan-daily --persist ./vector_db # 啟用 Chroma 向量 RAG
# → 產生 reports/YYYY-MM-DD.md(開頭含今日大盤風險橫幅)
```

### 感測器
| 感測器 | 看什麼 | 來源 |
|---|---|---|
| **news** | 新聞量能異常 · Google Trends 爆量 | RSS · pytrends |
| **data** | 法人進出 · 原物料/航運/SCFI · 美股族群 · **crash-watch** | FinMind · FRED · 東方財富 |
| **price** *(safety net)* | 漲停群聚 · 量能異常 · 報價 | FinMind · TWSE OpenAPI |
| **policy** | 政府政策/補助公告 | 政府 RSS |
| **roadmap** | 法說會/路線圖訊號 | 文字分析 |

所有感測器都回傳統一信封 `{timestamp, source, signal_type, content, raw_url, anomaly_score}`,
並**優雅降級** —— 來源掛掉或缺 token 時回結構化錯誤,絕不讓整條流程崩潰。

### 驗證
- **Phase 0 回測** —— `market-scan-validator --config cases.json`:15 個歷史測試點,
  4/5 案例有強領先訊號 → **GO**(概念驗證)。
- **Replay harness**(`reviewer/replay.py`)—— 真實 GDELT 新聞重播,算樣本外的領先天數。
- **Net-alpha**(`market_scan_validator/net_alpha.py`)—— 把毛回測報酬轉成貼近現實的淨值
  (成本 · 漲停 · 出場規則 · 題材化持有)。

### 誠實限制
- **即時偵測仍是未證實的賭注:** Phase 0 只證明「在後見之明挑的標的/日期上,領先訊號存在」;
  在當下沒有未來資訊時即時挑對族群,尚未驗證(架構師 + VC 分析見 `reports/audit/`)。
- **MCP server 不用 yfinance** —— 它會拉進 `curl_cffi`,弄壞 MCP stdio 傳輸;改用 requests 系來源。
  yfinance 只留在 Phase 0 CLI。
- **部分來源是 best-effort:** SCFI/BDI 走東方財富 + Google News RSS;DRAM 現貨、PTT/Dcard、
  部分政府 HTML、法說逐字稿仍是誠實 stub。
- **Crash-watch 是「降風險的警示訊號」,不是崩盤預測器** —— 見 `docs/research/`。

### 技術棧
Python 3.11+ · MCP(FastMCP)· Anthropic Claude SDK · FinMind / FRED / TWSE OpenAPI · Chroma · SQLite。
以 Claude Code plugin 形式發布;感測器經 `uvx` 啟動。Python 套件:`market_scan_mcp`。

---

## License · 授權
MIT — see [LICENSE](LICENSE).
