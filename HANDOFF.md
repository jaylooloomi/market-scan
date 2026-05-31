# PolyDig — Agent Handoff Document

**Last updated**: 2026-05-31
**Project status**: Phase 0 完成 (✅ GO) / Phase 1 待動工
**For**: Any Claude (or other) agent picking up this project

---

## 🚀 If you're a new agent reading this — start here

**Quick boot sequence (read in order)：**

1. This file (`HANDOFF.md`) — full context + decisions + next steps
2. [`docs/superpowers/specs/2026-05-31-polydig-design.md`](docs/superpowers/specs/2026-05-31-polydig-design.md) — design spec v0.1 (含 8 個 Phase 0 細部決策、5 sensor 架構、Reviewer 因果樹規格)
3. [`docs/superpowers/specs/2026-05-31-phase-0-results.md`](docs/superpowers/specs/2026-05-31-phase-0-results.md) — Phase 0 GO 決策、5 個經驗教訓
4. [`docs/research/01-theme-case-studies.md`](docs/research/01-theme-case-studies.md) — 5 案例考古（口罩/航運/AI/國防/矽光子）
5. [`reports/2026-05-31_validator/summary.md`](reports/2026-05-31_validator/summary.md) — Phase 0 驗證實證

讀完上面 5 個檔案，你就有完整 context。

**Then continue with：** Phase 1 §"Next Session Scope" 的具體 task list。

---

## 🎯 系統靈魂（不能違背的 north star）

> **「找的是事件還沒發酵、有領先效果的訊號」**

任何 feature / 訊號 / agent 設計都要通過：「**這個能不能幫使用者比市場早 N 天/週發現？**」

如果一個訊號只能事後告知（族群已漲完才推），就算準確率高也**不是這個系統要的東西**。

**唯一例外**：Price-driven sensor 是 safety net + 未來自我學習用，不是主要訊號源。

---

## 📋 專案基本資訊

| 項目 | 值 |
|---|---|
| 專案名稱 | **PolyDig** |
| GitHub | https://github.com/jaylooloomi/polydig |
| Working dir | `D:\git\harness-run\polydig\` (Windows / git-bash 環境) |
| Owner | Arthur (jaylooloomi, arthurwang@think4u-tech.com) |
| License | MIT |
| 發布計畫 | 上 Claude Code marketplace 公開 |
| Repo state | 3 commits on main, all pushed |

---

## 🧠 系統架構（一張圖）

```
[News-MCP] [Price-MCP (safety net)] [Data-MCP] [Policy-MCP] [Roadmap-MCP]
              ↓ (MCP tool calls)
  ┌────────────────────────────────────────────────┐
  │ Scout Agent (Claude Haiku 4.5)                  │
  │ - 每日 06:00 掃所有 sensors                     │
  │ - 高假陽性容忍                                   │
  │ - 輸出候選主題 5-15 個                          │
  └────────────────────────────────────────────────┘
              ↓
  ┌────────────────────────────────────────────────┐
  │ Reviewer Agent (Claude Sonnet 4.6)               │
  │ - 族群識別                                       │
  │ - 因果樹三階展開 (一階/二階/三階受益股 + lag)   │
  │ - 歷史對應 RAG (Chroma 向量檢索)                 │
  │ - **多窗口判定** (post30/90/180 任一爆發即通過) │
  │ - 分級：強訊號 / 觀察清單 / 駁回                │
  └────────────────────────────────────────────────┘
              ↓
  Markdown daily report → 用戶在 Claude Code 內看 (Plugin 模式)
```

---

## ✅ 已完成 (Phase 0)

| Item | Status | Path |
|---|---|---|
| Brainstorming + 設計定案 | ✅ | (10 個 question 全部 confirmed) |
| 設計 spec v0.1 | ✅ | `docs/superpowers/specs/2026-05-31-polydig-design.md` |
| Case study 5 個題材 | ✅ | `docs/research/01-theme-case-studies.md` |
| Phase 0 Leading Edge Validator (CLI) | ✅ | `src/polydig_validator/` |
| Phase 0 跑通 15 個測試點 | ✅ | `reports/2026-05-31_validator/` |
| Phase 0 GO 決策報告 | ✅ | `docs/superpowers/specs/2026-05-31-phase-0-results.md` |
| Phase 0 plan | ✅ | `docs/superpowers/plans/2026-05-31-phase-0-validator-plan.md` |
| Repo + git push | ✅ | https://github.com/jaylooloomi/polydig |
| FinMind token | ✅ | `.env` (gitignored, NEVER commit) |

**Phase 0 結果摘要**：15 個測試點 = 6 STRONG / 5 WEAK / 3 TOO_LATE / 1 NULL。**4/5 cases 有強領先訊號 → ✅ GO**。

---

## 🗂 所有已確認的設計決策

新 agent **不需要再問 Arthur 這些**：

### 整體
| # | 項目 | 決定 |
|---|---|---|
| G1 | 系統靈魂 | 「事件還沒發酵就抓到」是 north star |
| G2 | 模式 | 研究助理 (mode A) — daily 報告，**不自動下單** |
| G3 | 市場 | **台股做標的** (~1700 上市+上櫃)，**中英文新聞**皆用 |
| G4 | LLM 預算 | **不限制**（Arthur 用 Claude Code 訂閱 max plan）|
| G5 | 開發語言 | Python 3.11+ |

### 架構
| # | 項目 | 決定 |
|---|---|---|
| A1 | 訊號層 | **5 sensors** (News + Price + Data + Policy + Roadmap)，每個獨立 MCP server |
| A2 | Price 角色 | **Safety net**，不是平行觸發 (族群漲停潮代表「漏抓」) |
| A3 | Scout | Claude Haiku 4.5，高假陽性，每日 06:00 跑一次 |
| A4 | Reviewer | Claude Sonnet 4.6，必輸出**因果樹一/二/三階**，每階含台股 ticker + lag |
| A5 | 推理引擎 | **多窗口評估** (post30/90/180 任一爆發即通過) — 教訓: 只看 post30 會誤殺慢熱題材 |
| A6 | 歷史對應 | RAG (Chroma)；強歷史→強訊號，弱但邏輯成立→觀察清單，都弱→駁回 |
| A7 | 觀察清單 | 對新型題材 (沒歷史對應) 允許「強邏輯通過」(e.g. ChatGPT 沒對應) |
| A8 | Framework | 🚨 **Claude Code plugin** (NOT standalone service)；包成 `.claude-plugin/` 結構 |
| A9 | 主要互動 | **純自然語言** (用戶說「今天有什麼?」「研究 X 主題」)，**不用 slash commands** 為主入口 |
| A10 | 輸出語言 | 中文為主 |
| A11 | 發布 | 上 Claude Code marketplace 公開，**MIT license** |

### Phase 1 (MCP foundation)
| # | 項目 | 決定 |
|---|---|---|
| P1.1 | news-mcp 來源 | **全部 4 種**：中文 RSS + 國際英文 + Google Trends + PTT/Dcard |
| P1.2 | FinMind | ✅ 已有 token (在 `.env`，免費版 600 req/hr) |
| P1.3 | data-mcp 範圍 | 全部 4 類：運價 + 金屬/原物料 + 半導體 + 能源 + 化肥(尿素) |
| P1.4 | **本次 session 範圍** | **Phase 1 部分**：news + data + price 3 個 sensors 深做。policy + roadmap 下 session |

### Phase 2 (Agents)
| # | 項目 | 決定 |
|---|---|---|
| P2.1 | Reviewer 模型 | Sonnet 4.6 |
| P2.2 | 歷史庫擴展 | Phase 2 動工時同步補到 **20 個**題材 |

### Phase 4 (補完)
| # | 項目 | 決定 |
|---|---|---|
| P4.1 | policy-mcp 來源 | Arthur 委託 agent 研究「哪些爬得到」(4 候選: 金管會 / 衛福部 / 行政院 / 立法院) |
| P4.2 | roadmap-mcp 來源 | 確定要 Apple/MS/Google + TSMC/NVIDIA/AMD/Intel；agent 建議完整 list |
| P4.3 | Price safety net | **只做偵測**（哪族群漲停），漏抓回溯 defer 到 Phase 5+ |
| P4.4 | 預設股票池 | **台股全市場** (~1700) |

### Phase 5 (Launch)
| # | 項目 | 決定 |
|---|---|---|
| P5.1 | License | MIT |
| P5.2 | Plugin 名稱 | `PolyDig` (純英文) |
| P5.3 | Web Dashboard | **不做**（plugin 即介面）|
| P5.4 | Email/LINE 推播 | **不做**（自然語言即時對話即可）|

### 已確認**不做**的事
- ❌ 自動下單 / 連券商 API
- ❌ 美股 / 港股 / 加密貨幣
- ❌ Polymarket-style 投注機制
- ❌ vectorbt / autotrade **整合** (PolyDig 只提報，Arthur 自行 backtest)
- ❌ **個人化** (關注清單/排除股/自訂主題) — v1 不做
- ❌ Web Dashboard
- ❌ Email / LINE 推播

---

## 🛠 技術棧 + 慣例

| 層 | 技術 | 備註 |
|---|---|---|
| 語言 | Python 3.11+ | 已在 Win10 / Python 3.14.2 / pip 25.3 可跑 |
| Package mgmt | `pyproject.toml` + `pip install -e .` | hatchling backend |
| LLM | Anthropic Python SDK + Claude Haiku 4.5 / Sonnet 4.6 | Arthur 用 Claude Code 訂閱 |
| MCP | `mcp` Python package | 每個 sensor 獨立 MCP server，stdio transport (default) |
| 股價 | yfinance (主) + FinMind (補：籌碼/三大法人/財報) | yfinance 已驗證，FinMind token 在 `.env` |
| 儲存 | SQLite + Chroma (向量檢索) | Phase 2 動工 |
| 排程 | 視 plugin 慣例而定 (Claude Code cron-like trigger 或 OS cron) | Phase 3 確認 |
| Encoding | UTF-8 (Windows console cp950 需 reconfigure，看 `cli.py:main`) | 已處理 |
| Git | commit message 用 `--author="Arthur (jaylooloomi) <arthurwang@think4u-tech.com>"` + Co-Authored-By trailer | 不修改 git config |

### 命名慣例
- Python module: `snake_case`
- 檔案/資料夾: `kebab-case` (例: `news-mcp/`)
- 中文文件用繁中
- README 英文 (marketplace 受眾)
- 程式碼註解英文

### 目錄結構（目前 + 規劃）

```
polydig/
├── HANDOFF.md                          # 你正在讀的這個
├── README.md                            # 英文，給 marketplace 受眾
├── .gitignore
├── .env                                 # gitignored - 絕對不能 commit
├── pyproject.toml
├── requirements.txt
├── cases.json                           # Phase 0 validator config (15 test points)
│
├── src/
│   └── polydig_validator/               # Phase 0 - 已完成
│       ├── __init__.py
│       ├── data_fetcher.py
│       ├── excess_return.py
│       ├── classifier.py
│       ├── report.py
│       └── cli.py
│
│   # === Phase 1 待建 ===
│   ├── news_mcp/                        # MCP server: 新聞
│   ├── data_mcp/                        # MCP server: 公開數據
│   └── price_mcp/                       # MCP server: 行情
│
│   # === Phase 4 待建 ===
│   ├── policy_mcp/                      # MCP server: 政策
│   └── roadmap_mcp/                     # MCP server: 法說會/路線圖
│
├── reports/
│   └── 2026-05-31_validator/            # Phase 0 跑出來的 GO 證據
│
├── docs/
│   ├── superpowers/
│   │   ├── specs/
│   │   │   ├── 2026-05-31-polydig-design.md           # 主設計 spec v0.1
│   │   │   └── 2026-05-31-phase-0-results.md          # Phase 0 GO 決策
│   │   └── plans/
│   │       └── 2026-05-31-phase-0-validator-plan.md
│   └── research/
│       └── 01-theme-case-studies.md     # 5 案例考古
│
└── (Phase 3 後) .claude-plugin/
    ├── plugin.json                      # Plugin manifest
    └── ...
```

---

## 🎬 NEXT SESSION SCOPE — Phase 1 (news + data + price MCPs)

### Goal
建 3 個獨立 MCP server，可被 Claude Code 透過 `.mcp.json` 註冊，每個 server 透過 MCP tools 暴露 sensor 能力。

### 完成定義 (Definition of Done)
- [ ] 3 個 MCP server 各自能用 `mcp inspector` 獨立測試
- [ ] news-mcp: 至少能抓 1 個中文 RSS + 1 個國際英文 RSS + Google Trends 查詢一個關鍵字 + (PTT 可 stub)
- [ ] data-mcp: FinMind 包好 (用 `.env` 的 token) + SCFI/BDI 公開抓取 + LME 銅價 + 1 個半導體報價來源 + 至少 1 個原物料 (尿素或其他化肥)
- [ ] price-mcp: TWSE 行情 + 漲停族群偵測 (`detect_limit_up_cluster` tool)
- [ ] 每個 server 有 README 講解 tool 列表 + 範例呼叫
- [ ] `.mcp.json` 配置範例
- [ ] integration test: 用 Anthropic SDK 直接呼叫一個 MCP tool 確認 end-to-end 通

### 推薦工作順序

1. **news-mcp 先做** (最關鍵、最複雜)
   - 中文 RSS：經濟日報 / 鉅亨 / 自由財經 (parse RSS XML)
   - 國際英文：Reuters / Bloomberg / CNBC (RSS 或 web scrape)
   - Google Trends：`pytrends` 套件 (no auth needed)
   - PTT/Dcard：先 stub，標 TODO 未來補爬蟲
   - MCP tools: `fetch_news(source, since, query)`, `detect_news_anomaly(window_days, threshold)`, `google_trends_check(keyword, region='TW')`

2. **data-mcp 次做** (FinMind token 已備)
   - FinMind wrapper：日 K / 三大法人 / 籌碼 / 財報簡表
   - SCFI: 上海航運交易所公開 (爬網頁)
   - LME: 倫敦金屬交易所公開
   - 半導體: TrendForce 公開 (爬 / RSS)
   - 原物料: USDA / WorldBank Commodity API (尿素等)
   - MCP tools: `get_shipping_index`, `get_commodity_price`, `get_dram_price`, `get_finmind(dataset, ...)`

3. **price-mcp 最後做** (相對單純)
   - yfinance 包好成 MCP tool
   - 漲停族群偵測：用 yfinance / TWSE 抓當日漲停股，按產業分群
   - MCP tools: `get_quote(symbol)`, `detect_limit_up_cluster(date)`, `volume_anomaly(symbol)`

### 關鍵設計 contract（不能違背）

1. **每個 MCP server 必須回標準格式**：
   ```python
   {
     "timestamp": "ISO-8601",
     "source": "news.economic-daily",
     "signal_type": "news_anomaly",
     "content": {...},
     "raw_url": "https://...",
     "anomaly_score": 0.0-1.0  # 或 null 若不適用
   }
   ```
2. **不要在 sensor 層做語意推理**（那是 Reviewer Agent 的事）— sensor 只負責「異常偵測 + 數據抓取」
3. **graceful failure**：缺 token / 斷網 / API 變動 → 回 structured error 不要 crash
4. **gitignore secrets**：任何 token / 密碼一律進 `.env`，**絕對不能**在 code 或 README 出現
5. **編碼**：所有 source files UTF-8，Windows console 若要 print emoji 用 `sys.stdout.reconfigure(encoding="utf-8")`

### Phase 1 不需要做的事（明確排除避免 scope creep）
- ❌ Scout / Reviewer agent（Phase 2）
- ❌ 報告生成 / 排程（Phase 3）
- ❌ Plugin 包裝 (`.claude-plugin/`)（Phase 3）
- ❌ policy-mcp / roadmap-mcp（Phase 4）
- ❌ 漏抓回溯機制（Phase 5+）
- ❌ vectorbt 整合 / 個人化功能 / Dashboard

---

## 🔮 後續 Phase 概覽（供新 agent 規劃用）

### Phase 2: Agents (2 週)
- Scout Agent (Haiku 4.5)：消費 5 sensors 的 MCP tools，輸出候選主題
- Reviewer Agent (Sonnet 4.6)：對候選做族群識別 + 因果樹 + 歷史對應 RAG + 分級
- 同步補歷史庫到 20 個題材 (見 case study 報告為主要素材)

### Phase 3: Plugin 包裝 + UX (1 週)
- 包成 `.claude-plugin/` 結構
- 主要 skill (自然語言觸發)
- 報告生成 (markdown)
- 排程 (daily 06:00)

### Phase 4: 補完 (2 週)
- policy-mcp (先做 4 個來源可行性研究，然後實作)
- roadmap-mcp (TSMC/NVIDIA/AMD/Intel + Apple/MS/Google + agent 補完建議清單)
- Price safety net 偵測（**不做回溯**，那 defer 到 Phase 5+）

### Phase 5: Marketplace launch + iteration
- README 英文 (marketplace 主訴)
- docs/zh-tw.md 補繁中
- Demo mode (沒 FinMind token 也能 try)
- Graceful failure 處理
- Marketplace submission

---

## 📦 Memory / Context Files（如果你跑在 Arthur 的本機）

如果你跑在 `D:\git\harness-run` 或同一台 Windows 機器：

- 我的 project memory: `C:\Users\User\.claude\projects\D--git-harness-run\memory\project_stock-signal-system.md`
- 我的 user/feedback memories: 同資料夾下其他 `.md` 檔
- 特別重要：`feedback_validate-premise-before-architecting.md` (Arthur 教我的「驗證根本假設再架構」教訓)

如果你**不在**同一機器：不需要這些，這份 `HANDOFF.md` 已涵蓋所有 actionable 資訊。

---

## 🤝 與 Arthur 互動的偏好（從前面對話總結）

- **講中文** (繁中為主)
- 報告/設計用 markdown 表格，scannable
- 不喜歡 ceremony / 廢話，直接給選項或結論
- 要求**老實**：發現 bug / 不確定 / 沒做就直說，不要遮掩
- 接受**承認失敗**：Arthur 教過「validate premise before architecting」的教訓
- 不要每件事都問 — 給選項 + 推薦 + 預設值，他改你才改
- **不要 git commit / push 沒授權的東西** — `.env` 絕對不能 commit
- LLM 預算不是問題 (Claude Code max plan)

---

## ⚠️ Known Risks / Open Items（新 agent 要注意）

1. **PTT 爬蟲**：18 禁門 + 反爬蟲，先 stub
2. **TrendForce 報價**：可能需要付費訂閱，先看公開頁面
3. **MOPS 法說會逐字稿** (Phase 4)：PDF 格式不一，parser 要 robust
4. **政府公告爬蟲** (Phase 4)：HTML 變動風險，需要 retry + diff
5. **FinMind 600 req/hr 限制**：setup 階段（一次抓全市場）可能不夠，可能要 cache / 分批
6. **yfinance 對某些上櫃股**：用 `.TWO` suffix，不是 `.TW` (e.g. 3163.TWO 不是 3163.TW)
7. **Windows console encoding (cp950)**：emoji print 會 crash，已有解法在 `cli.py`

---

## 🏁 啟動 Phase 1 — 給新 agent 的一句指令範例

> 「Read `polydig/HANDOFF.md`, then proceed with Phase 1 Next Session Scope. Start with news-mcp. Don't ask Arthur — all decisions are in the handoff doc. If you hit something truly ambiguous that isn't covered, then ask.」

或更短：

> 「Continue PolyDig per HANDOFF.md. Start with news-mcp.」

---

**End of handoff. Good luck.**

— 前任 agent (Claude Haiku 4.5, 2026-05-31)
