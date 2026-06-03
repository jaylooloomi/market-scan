# Market Scan — Design Spec v0.1

**Date**: 2026-05-31
**Author**: Arthur (jaylooloomi) + Claude (Haiku 4.5)
**Status**: Draft，等用戶 review
**GitHub**: https://github.com/jaylooloomi/market-scan
**Working dir**: `D:\git\harness-run\market-scan\`

---

## 1. 專案一句話定義

> **Market Scan 是一套台股題材早期偵測系統，在事件還沒被市場廣泛察覺時，把「事件 → 受影響族群 → 歷史對應」這個推理鏈跑出來，輸出每日研究助理報告。**

---

## 2. 系統靈魂 (Core Value Proposition)

> **「找的是事件還沒發酵、有領先效果的訊號」**

任何 feature、訊號、agent 設計都必須通過這個檢驗：

> **「這個能不能幫我比市場早 N 天/週發現？」**

如果一個訊號只能事後告知（例如「漲停族群已經漲完才看到」），即使準確率高，**也不是這個系統要的東西**。

唯一例外：Price Driven 是 **safety net + 自我學習機制**，用來補強漏抓案例，不是主要訊號源。

---

## 3. 模式與範圍

| 項目 | 決策 |
|---|---|
| **使用模式** | 研究助理（每日報告，用戶自己決定要不要進場，不自動下單）|
| **市場範圍** | **台股做標的**（~1700 檔）|
| **資料源語言** | **中文（經濟日報、鉅亨、PTT）+ 國際英文（Reuters、Bloomberg、CNBC、TSMC/NVIDIA 法說）**|
| **時間範圍** | 短中期（口罩股 1-3 月）+ 長波段（航運/AI 6-24 月）皆涵蓋，Reviewer 為每個題材標記預期 lag |
| **LLM 預算** | 不限（Arthur 使用 Claude Code 訂閱），可放手用 Sonnet/Opus |

---

## 4. 系統架構（高階）

```
┌─────────────────────────────────────────────────────────┐
│  Scout 感測器層 (5 個獨立 MCP servers)                  │
│                                                          │
│  [news-mcp]  [price-mcp]  [data-mcp]  [policy-mcp]  [roadmap-mcp]
│      ↓           ↓ (SN)       ↓            ↓             ↓
└─────────────────────────────────────────────────────────┘
                     ↓ (MCP tool calls)
┌─────────────────────────────────────────────────────────┐
│  Scout Agent (Claude Haiku 4.5)                          │
│  - 每日掃 5 sensors，輸出候選主題                       │
│  - 高假陽性容忍                                          │
└─────────────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│  Reviewer Agent (Claude Sonnet 4.6 / Opus 4.7)           │
│  - 族群識別                                               │
│  - 因果樹三階展開（一階/二階/三階）                     │
│  - 歷史對應檢索 (RAG → 歷史題材庫)                       │
│  - 分級：強訊號 / 觀察清單 / 駁回                       │
│  - Safety net 觸發時，主動回溯 30-90 天找漏抓訊號       │
└─────────────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│  Report Generator → Markdown + (可選 Email/LINE 推播)   │
└─────────────────────────────────────────────────────────┘
                     ↓
        儲存層: SQLite + Vector DB (歷史庫 RAG)
        + 漏抓案例庫（Auto-learning corpus）
```

---

## 5. 5 種觸發路徑（Trigger Flow）

| 觸發類型 | 路徑 | 範例案例 |
|---|---|---|
| **News** | News → 族群識別 → 歷史對應 | 口罩 (武漢肺炎)、國防 (俄烏)、AI (ChatGPT) |
| **Data** | Data 異常 → 族群 → 找對應 News → 歷史 | 航運 (SCFI 領先)、銅 (LME 銅價) |
| **Policy** | Policy 公告 → 族群 → 歷史 | 高端 EUA、川普關稅、太空法 |
| **Roadmap** | 大廠路線圖/法說會 → 族群 → 歷史 | 矽光子 (TSMC COUPE)、HBM4、800G→1.6T |
| **Price** (safety net) | 族群漲停潮 → 找漏抓的領先訊號（回溯 30-90 天）→ 加入漏抓案例庫 | 系統的自我修正機制 |

**重要設計原則：**

- **歷史對應是 optional**：強邏輯推論成立即可通過為「觀察清單」（對 ChatGPT、矽光子這類新型題材）
- **Price Driven 不是平行觸發**，是 fallback + 學習機制
- **Reviewer 必須輸出因果樹**到三階以上，不是只給一階受益股

---

## 6. 主要 Component 詳細設計

### 6.1 MCP Sensors（5 個獨立 server）

每個 sensor 是獨立 MCP server，於 `.mcp.json` 註冊，可被 Scout Agent 透過 MCP tool 呼叫。

| Sensor | 主要功能 / Tools | 資料源 |
|---|---|---|
| **news-mcp** | `fetch_news`, `detect_news_anomaly`, `google_trends_check` | 經濟日報 RSS、鉅亨 RSS、Reuters、Bloomberg、Google Trends API、PTT 股板（爬蟲）|
| **price-mcp** | `get_quote`, `detect_limit_up_cluster`, `volume_anomaly` | TWSE API、yfinance |
| **data-mcp** | `get_shipping_index`, `get_commodity_price`, `get_dram_price` | FinMind API（75+ 台股資料集）、SCFI 公開、LME 公開、TrendForce 報價 |
| **policy-mcp** | `fetch_policy_announcements` | 金管會、衛福部、健保署、行政院、立法院公報（**獨立爬蟲，不會在新聞 RSS**）|
| **roadmap-mcp** | `fetch_corp_roadmap`, `parse_earnings_call` | MOPS 公開資訊觀測站、NVIDIA/AMD/TSMC 法說會逐字稿 |

**設計原則：**
- 每個 sensor 自帶排程（不同更新頻率）
- 輸出統一格式：`{timestamp, source, signal_type, content, raw_url, anomaly_score}`
- 可獨立用 `mcp inspector` 測試

### 6.2 Scout Agent

| 屬性 | 規格 |
|---|---|
| **模型** | Claude Haiku 4.5 (便宜、夠用) |
| **觸發** | Cron 每日 06:00 + 即時觸發（重大事件） |
| **輸入** | 5 sensors 的 raw signals |
| **處理** | 異常偵測（頻率突起、跨 sensor 關聯）|
| **輸出** | 候選主題列表（每日 5-15 個，高假陽性容忍）|
| **不做** | 不做歷史對應、不做因果樹、不做最終判斷（這些是 Reviewer 的工作）|

### 6.3 Reviewer Agent

| 屬性 | 規格 |
|---|---|
| **模型** | Claude Sonnet 4.6（或 Opus 4.7，視推理品質決定） |
| **輸入** | Scout 輸出的候選主題 |
| **處理流程** | (1) 族群識別 → (2) 因果樹三階展開 → (3) 歷史對應檢索 (RAG) → (4) 分級 |
| **輸出 schema** | 結構化 JSON：候選主題、因果樹 (一/二/三階受益股 + lag)、歷史對應 (有/弱/無)、訊號等級 (強/觀察/駁回)、信心分數、推理過程 |
| **Safety net 模式** | Price sensor 觸發時，額外執行「漏抓回溯」任務 |

#### 因果樹 output schema 範例
```json
{
  "theme": "宅經濟 (COVID 引發)",
  "trigger": "2020/1/24 政府禁口罩出口",
  "causal_tree": {
    "tier_1": [
      {"ticker": "9919", "name": "康那香", "lag_days": 7},
      {"ticker": "1325", "name": "恆大", "lag_days": 7}
    ],
    "tier_2": [
      {"ticker": "3037", "name": "欣興 (筆電爆量→ABF載板)", "lag_days": 90}
    ],
    "tier_3": [
      {"ticker": "6435", "name": "大中 (半導體缺貨→MOSFET)", "lag_days": 180}
    ]
  },
  "historical_match": [{"event": "SARS 2003", "similarity": 0.85, "outcome": "+200% in 3 months"}],
  "signal_grade": "strong",
  "confidence": 0.92,
  "reasoning": "..."
}
```

### 6.4 Historical Theme Database

- **儲存**：SQLite（結構化）+ Vector DB (Chroma 或 sqlite-vss，做語意檢索)
- **種子資料**：case study 整理的 20 個題材（口罩、航運、AI、矽光子...），每筆包含：
  - 題材名、trigger 事件、日期、訊號類型 (5 種)
  - 受益族群（一/二/三階）+ 各階反應 lag
  - 最終漲幅、持續時間
  - Reviewer 當時若要審核會通過/駁回的判定
- **使用方式**：Reviewer 透過 RAG 檢索與當前事件「語意相似」的歷史題材

### 6.5 漏抓回溯機制（Auto-learning）

當 Price sensor 觸發（族群漲停潮）：
1. Reviewer 收到「這個族群已經被市場注意到」訊號
2. **回溯**：拉取 30-90 天前的 News/Data/Policy/Roadmap 訊號
3. 用 LLM 推理：「是否有跡可循？我們為什麼漏掉？」
4. 若找到漏抓訊號 → 加入「**漏抓案例庫**」+ 提報 Scout 調整偵測規則
5. 若找不到 → 該族群可能是純散戶炒作，標記「無基本面支撐」

### 6.6 Report Generator

- **格式**：Markdown
- **輸出位置**：本地檔案（`reports/YYYY-MM-DD.md`）
- **內容**：
  - 今日強訊號（Reviewer 通過）
  - 觀察清單（弱訊號但邏輯成立）
  - 駁回但有趣（FYI）
  - 漏抓案例（如有 Price safety net 觸發）
- **可選擴充**：Email 寄送、LINE 推播（後續 Phase）

---

## 7. Phase 0：Leading Edge Validator（**必做首要任務**）

### 7.1 為什麼這是 Phase 0
驗證 Market Scan 的根本假設：**「訊號出現時，股價真的還沒漲」**。

如果這個假設不成立（事件出現時股票已經漲了一波），整個 Market Scan 沒價值。

→ **先驗證、再投入時間蓋系統**

### 7.2 規格

**輸入**：題材清單，每筆包含
- 題材名稱（例如「口罩股」）
- 候選 trigger 事件 + 日期（例如「2019/12/31 武漢通報不明肺炎」）
- 代表台股 tickers（例如 9919, 1325, 6504）

**處理**：
1. 用 FinMind 拉取 trigger 日期 ±180 天的股價（個股 + 大盤）
2. 計算「事前已反映」：T-90 → T-1 漲跌幅（剔除大盤同期效應）
3. 計算「事後空間」：T-1 → T+7 / T+30 / T+90 / T+180 漲跌幅
4. 分類：

| 分類 | 條件 |
|---|---|
| 🟢 **強領先** | T-90→T-1 < +10%（相對大盤）且 T-1→T+30 > +30% |
| 🟡 **弱領先** | T-90→T-1 < +30% 且 T-1→T+30 > +15% |
| 🔴 **太晚** | T-90→T-1 > +30%（市場已反應）|
| ⚫ **無效** | T-1→T+90 < +10%（題材沒成立）|

**輸出**：每個題材一份結構化報告 + 整體統計

### 7.3 驗收標準
跑 case study 5 個題材：
- ✅ ≥ 4 個是「強領先」 → 概念驗證通過，啟動 Phase 1
- ⚠️ 2-3 個強領先 → 重新思考訊號類型，部分題材可能不適用
- ❌ ≤ 1 個強領先 → **停止專案**，根本假設不成立

### 7.4 副產品
跑完同時建立 5 筆結構化「歷史題材」資料 → Reviewer 歷史庫的種子。

### 7.5 細部決策（2026-05-31 透過 8 問釐清）

| # | 決策項目 | 結果 |
|---|---|---|
| 1 | Cases | 口罩(2020) / 航運(2020-21) / AI(2023) / 國防(2022) / 矽光子(2024-25)，共 5 個 |
| 2 | Trigger 日期 | 每個 case 跑 3 個 trigger 日期（早 / 中 / 晚）= **15 個測試點** |
| 3 | 代表股選法 | 從 case study 因果樹一階受益股**手選 3-5 檔** per case |
| 4 | 大盤對照 | **TAIEX 加權指數**（個股漲幅 − TAIEX 同期漲幅）|
| 5 | 股價資料源 | **FinMind 為主 + yfinance 備援** |
| 6 | 輸出格式 | **Markdown 報告 + JSON 結構化資料** |
| 7 | 包裝方式 | **JSON config + CLI 工具**（cases.json 配置驅動，未來加題材只改 JSON）|
| 8 | Git 設定 | **立即 git init + push** 到 [market-scan repo](https://github.com/jaylooloomi/market-scan) |

#### 15 個測試點對照表（5 cases × 3 trigger dates）

| Case | 早期 trigger | 中期 trigger | 晚期 trigger |
|---|---|---|---|
| **口罩** (News) | 2019/12/31 武漢通報不明肺炎 | 2020/1/20 鍾南山證實人傳人 | 2020/1/24 政府禁口罩出口 |
| **航運** (Data) | 2020/6 SCFI 指數起漲 | 2020/12 中國缺櫃新聞首見 | 2021/3/23 長賜輪卡蘇伊士 |
| **AI** (News/Intl) | 2022/11/30 ChatGPT 上線 | 2023/2 微軟整合 Bing+ChatGPT | 2023/5/24 NVIDIA Q1 財報暴擊 |
| **國防** (News) | 2021/11 俄烏邊境部隊集結 | 2022/2/21 普丁承認頓巴斯 | 2022/2/24 全面入侵 |
| **矽光子** (Roadmap) | 2023 NVIDIA 提及 CPO 路線圖 | 2024/9 SEMI 矽光子聯盟成立 | 2025/Q1 TSMC 確認 2026 量產 |

#### 代表股清單（一階受益股，手選）

| Case | 代表股 |
|---|---|
| 口罩 | 9919 康那香、1325 恆大、6504 南六 |
| 航運 | 2603 長榮、2609 陽明、2615 萬海 |
| AI | 3231 緯創、2382 廣達、2376 技嘉 |
| 國防 | 2634 漢翔、8033 雷虎 |
| 矽光子 | 3163 波若威、4979 華星光、4977 眾達-KY |

#### 計算方法（核心公式）

```
事前漲幅 (excess) = (個股 T-1 收盤 / 個股 T-90 收盤) - (TAIEX T-1 / TAIEX T-90)
事後漲幅 (excess) = (個股 T+30 收盤 / 個股 T-1 收盤) - (TAIEX T+30 / TAIEX T-1)
                  (同樣計算 T+7, T+90, T+180)

分類：
  🟢 強領先: 事前 < +10% 且 事後30 > +30%
  🟡 弱領先: 事前 < +30% 且 事後30 > +15%
  🔴 太晚:   事前 > +30%
  ⚫ 無效:   事後90 < +10%
```

#### CLI 規格（草稿）

```bash
# 跑單一 case
$ market-scan-validator --case mask --triggers early,mid,late

# 跑全部 cases
$ market-scan-validator --config cases.json --output reports/

# 輸出
reports/2026-05-31_validator/
├── summary.md        # 整體摘要 + go/no-go 決策
├── summary.json      # 結構化資料
├── mask.md           # 各 case 詳細報告
├── mask.json
├── shipping.md
└── ...
```

---

## 8. 開發階段 (Phases)

| Phase | 內容 | 預估時間 | 主要產出 |
|---|---|---|---|
| **Phase 0** | Leading Edge Validator + 5 case 驗證 | 1 週 | go/no-go 決策 + 5 筆種子歷史庫 |
| **Phase 1** | MCP 基礎建設（news-mcp、data-mcp、price-mcp） | 2 週 | 3 個可運作的 MCP server |
| **Phase 2** | Scout Agent + Reviewer Agent | 2 週 | 端對端 dry run 跑通歷史 case |
| **Phase 3** | Report Generator + 排程 | 1 週 | 每日自動產 markdown 報告 |
| **Phase 4** | 補完 policy-mcp、roadmap-mcp + Price safety net + 漏抓回溯機制 | 2 週 | 完整系統 |
| **Phase 5（可選）** | Email/LINE 推播、Web Dashboard、歷史庫擴充到 20 個題材 | 持續 | 可用性升級 |

**總計**：MVP（Phase 0-3）約 6 週，完整系統（Phase 0-4）約 8 週。

---

## 9. 技術棧

| 層 | 技術選擇 | 理由 |
|---|---|---|
| 語言 | Python 3.11+ | Arthur 既有專案棧、vectorbt / autotrade 都是 Python |
| LLM SDK | Anthropic Python SDK | 直接呼叫 Claude API |
| Agent 框架 | Claude Agent SDK 或 raw Anthropic SDK | TBD（Claude Agent SDK 提供 multi-agent orchestration） |
| MCP | `mcp` Python package (官方) | 標準協議 |
| 台股資料 | FinMind | 開源、75+ 資料集、有 llms.txt |
| 股價技術 | yfinance（備援）| 廣度補強 |
| 儲存 | SQLite + Chroma (vector) | 輕量、單機可跑 |
| 排程 | APScheduler 或 cron | 簡單可靠 |
| 通知（後續）| Email (smtplib) / LINE Notify | 標準工具 |

---

## 10. 成功指標

| 指標類型 | 指標 | 達標標準 |
|---|---|---|
| **Phase 0 概念驗證** | 5 個 case study 強領先比例 | ≥ 4/5 |
| **Phase 1-3 開發** | 端對端 dry run 在歷史 case 還原出當時應推薦的題材 | ≥ 3/5 |
| **Phase 4 上線** | 月命中率：每月推薦中，之後 90 天漲 ≥ 20% 的題材比例 | ≥ 30% |
| **領先性** | 平均「Reviewer 報告日 → 該族群明顯啟動日」的天數 | ≥ 14 天 |
| **雜訊控制** | 每日強訊號數量 | 0-5 個（不超過 5）|

---

## 11. 已知風險與緩解

| 風險 | 緩解 |
|---|---|
| **FinMind 資料覆蓋不足**（特定指數、即時報價） | Phase 1 先測試覆蓋率；若不足補 yfinance / 自寫 TWSE 爬蟲 |
| **LLM 因果樹推理品質不足** | Phase 2 對比 Sonnet 4.6 vs Opus 4.7，挑品質 OK 的最便宜版本 |
| **歷史對應對新型題材無用**（如 ChatGPT、矽光子） | Reviewer 設計已允許「無歷史但強邏輯 → 觀察清單」 |
| **漏抓回溯找不到訊號** | 也算學習素材：標記「該族群可能無基本面」|
| **新聞爬蟲被擋 IP** | 加 retry、proxy、用 RSS 為主、商業爬蟲為輔 |
| **Reviewer 過度保守** | Phase 2 用歷史 case 校準閾值，加觀察清單機制做緩衝 |
| **第一版做太大** | 嚴格遵守 Phase 順序，先 Phase 0 再決定要不要繼續 |

---

## 12. 待用戶確認的開放問題

1. **報告交付方式**：第一版只產 Markdown 本地檔案？還是同時要 Email？（Phase 3 決定）
2. **漏抓案例庫的 storage**：要不要做 Web UI 來瀏覽？還是純檔案就好？
3. **Phase 0 5 個 case 確認**：口罩 / 航運 / AI / 國防 / 矽光子，這 5 個就是 Phase 0 的測試集？要加減？
4. **歷史庫種子**：除了 case study 5 個，要不要 Phase 0 結束後**手動再補 5-10 個**到 Reviewer 歷史庫？
5. **Git 與 GitHub**：Phase 0 開始時要不要 `git init` + push 到 [market-scan repo](https://github.com/jaylooloomi/market-scan)？

---

## 13. 引用 / 參考

- 案例研究：[`docs/research/01-theme-case-studies.md`](../research/01-theme-case-studies.md)
- 學術參考：
  - REST: Relational Event-driven Stock Trend Forecasting ([arxiv 2102.07372](https://arxiv.org/pdf/2102.07372))
  - StockMem: Event-Reflection Memory Framework ([arxiv 2512.02720](https://arxiv.org/pdf/2512.02720))
- 開源參考：
  - [FinMind](https://finmindtrade.com/) — 台股資料 API
  - [FinPilot](https://github.com/hu0937/FinPilot) — 台股 + Claude 整合範例
  - [TradingAgents](https://github.com/tauricresearch/tradingagents) — 多 agent 架構
- Anthropic：
  - [Claude for Financial Services](https://www.anthropic.com/news/claude-for-financial-services)
  - [anthropics/financial-services](https://github.com/anthropics/financial-services) — agent template 範例
