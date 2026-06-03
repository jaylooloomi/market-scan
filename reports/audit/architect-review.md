# Market Scan — 架構師審查報告（Architect Review）

**審查日期**：2026-06-01
**審查範圍**：整個 repo 逐檔閱讀（54 個 Python 檔 / 4,645 行 + 全部 docs、configs、themes.json、cases.json、tests）
**方法**：逐行靜態閱讀 + 對可疑處實際執行驗證（見 §3 標註「✅ 已驗證」者）
**對象 commit**：`1d122ce`（main，working tree clean）
**Iteration**：1（Ralph loop — 後續迭代會加深驗證與細節）

---

## 0. 總評（TL;DR）

| 維度 | 評分 | 一句話 |
|---|---|---|
| 設計判斷力 / 產品紀律 | **A** | Phase 0「先驗證根本假設再蓋系統」是少見的成熟工程判斷 |
| 程式碼品質（可讀性、註解、命名） | **A-** | 註解講「為什麼」、bilingual、honest stub，水準明顯高於一般 side project |
| 架構分層與抽象 | **B+** | envelope contract + sensor/reviewer 分層乾淨；但「5 個獨立 server」的隔離只在 MCP 模式為真 |
| 正確性 / 韌性 | **B** | graceful failure 做得好；但有數個已驗證的真實 bug（見 §3） |
| 工程基礎建設（測試 / CI / 套件） | **C** | 測試是 ad-hoc 腳本、**無 CI**、**實跑 3/9 失敗（已驗證）**、`requirements.txt` 是壞的 |
| 可觀測性 / 維運 | **C+** | 大量 `except: pass` 靜默吞錯，只有 scheduler 有 logging |

**結論**：這是一個**設計遠超過其工程基礎建設**的專案。核心抽象（signal envelope、sensor 啞化、reviewer 因果樹、honest stub）品質很高，作者的取捨幾乎每一個都寫下了理由。但「測試聲稱全過、實際上沒過」「`requirements.txt` 裝不起來」「相似度可超過合約上限 1.0」這類問題，暴露出**沒有 CI gate、發布前沒做 clean-room 安裝驗證**。在上 marketplace 公開前，這些是 P0。

---

## 1. 真正做得好的地方（先講優點，這些別動）

1. **Signal envelope 是單一事實來源**（[envelope.py](src/market_scan_mcp/common/envelope.py)）。所有 sensor 回傳同一個 `{timestamp, source, signal_type, content, raw_url, anomaly_score}`，並用 `error_signal()` 把錯誤當資料回傳而非拋例外。這個 contract 是整個系統的脊椎，設計得很對。
2. **「Sensor 啞、Reviewer 智」的分層**貫徹得很徹底。sensor 只做異常偵測 + 抓資料，語意推理全留給 Reviewer。這讓 sensor 可獨立測試、可被任何 agent 重用。
3. **Honest stub 紀律**。`fetch_ptt`、`get_dram_price`、`fetch_corp_roadmap`、policy 的 HTML 來源——全部回 `not_implemented` 的結構化訊號 + TODO，**從不假裝有資料**。這在金融工具裡是稀缺的誠實。
4. **Graceful degradation 無所不在**：缺 FinMind token → `missing_token` 訊號；chroma 裝不起來 → token-overlap fallback（[store.py](src/market_scan_mcp/history/store.py)）；feed 掛掉 → per-feed 錯誤、其餘照回。系統很難被單一外部失敗打死。
5. **Windows / MCP stdio 的硬傷被記錄且被處理**：yfinance→curl_cffi 會弄壞 stdio transport 這條教訓，在 [io.py](src/market_scan_mcp/common/io.py)、[macro.py](src/market_scan_mcp/data/macro.py)、HANDOFF 三處都有交代，並真的改用 requests-based 來源。
6. **Secrets 衛生**：token 一律走 `.env`、`get_settings()` 集中讀取、Telegram 不 log credentials、`.db` 與 `.env` gitignored。
7. **多窗口 classifier 的演進**（[classifier.py](src/market_scan_validator/classifier.py) 的 v0.1→v0.2 註解）顯示作者從資料中學到「只看 post30 會誤殺慢熱題材」並修正——這是真的在做科學，不是拍腦袋。

---

## 2. 分層架構評估

| 層 | 檔案 | 評估 |
|---|---|---|
| **Common 基礎** | `common/{envelope,errors,http,settings,io}.py` | 乾淨。`polite_get` 有 timeout/retry/UA。**但 feedparser 的抓取繞過了它**（見 §3-M4）。 |
| **News sensor** | `news/{server,sources}.py` | 最複雜也最關鍵。jieba POS 過濾 + userdict 注入 domain 詞、cross-week SQLite baseline 是亮點。詞頻 spike 是 within-window heuristic（誠實標註）。 |
| **Data sensor** | `data/{server,finmind,macro,shipping}.py` | FRED keyless CSV + East Money 免費 JSON + Google News RSS 派生 SCFI 方向——在「沒有免費 API」的現實下，用新聞派生方向/動能是聰明的折衷。 |
| **Price sensor（safety net）** | `price/{server,twse}.py` | TWSE OpenAPI 一次抓全市場（vs 1700 次 per-stock 呼叫）是對的取捨。漲停族群分群邏輯清楚。 |
| **Policy / Roadmap sensor** | `policy/server.py`, `roadmap/server.py` | 大多是 feasibility-gated stub，但 `parse_earnings_call` 的關鍵詞抽取是真的可測。 |
| **Reviewer 引擎** | `reviewer/{engine,pipeline,schema,scout,prompt,backfill,backtest}.py` | 設計與 spec §6.3 對齊。dry/llm 雙模、heuristic 借用 top precedent 的樹。**backtest 的 recall 指標偏寬鬆**（見 §3-M2）。 |
| **History RAG** | `history/{store,themes.json}` | Chroma + token-overlap fallback 同介面，設計好。**fallback 相似度可 >1.0**（§3-P3）。 |
| **Storage** | `storage/db.py` | stdlib sqlite3、無 ORM、schema 清楚。**`term_history` 缺 UNIQUE 約束導致「upsert」其實在累積重複列**（§3-M3）。 |
| **Reporting** | `reporting/{generator,telegram}.py` | markdown 產生器條列清楚、Telegram 切塊 + 純文字避免 400。可用。 |
| **Scheduler** | `scheduler.py` | APScheduler、06:00 Asia/Taipei、optional dep 缺失時優雅退出。唯一有 logging 的模組。 |
| **Phase 0 Validator** | `market_scan_validator/*` | 與線上系統解耦（用 yfinance），方法論清楚（excess return vs TAIEX、多窗口）。對齊邏輯 fragile 但能用。 |

**架構縫隙（非 bug，但要知道）**：spec 說「5 個獨立 MCP server」，在 MCP 模式下（`.mcp.json` 各自起 process）確實獨立。但 headless pipeline 的 `collect_signals()`（[pipeline.py:19](src/market_scan_mcp/reviewer/pipeline.py:19)）是把五個 server module **import 進同一個 Python process** 直接呼叫 tool function。所以「進程隔離 / 單一 sensor crash 不影響其他」這個保證**只在 MCP 模式成立**，headless 模式下是靠每個 `try/except` 包住。兩條路徑的失敗模式不同，測試時要分開涵蓋。

---

## 3. 已驗證的問題清單（依嚴重度排序）

> 標 ✅ 者為我實際執行 / 重現過；其餘為靜態閱讀判定。

### P0 — 上 marketplace 前必修

**P0-1　測試套件 3/9 真實失敗（HANDOFF 宣稱「全部通過」）；且無 CI　✅ 已逐一實跑驗證**

實跑全 9 個測試（已 `pip install -e .` + 安裝輕量 deps），結果 **6 PASS / 3 FAIL**，3 個失敗全是**離線邏輯失敗（與網路/deps 無關）**：

| 測試 | 結果 | 失敗根因（已驗證） |
|---|---|---|
| test_storage / test_backfill / test_backtest_recall / test_shipping_anomaly / test_scheduler / test_mcp_integration | ✅ PASS | mcp_integration、scheduler 需先 `pip install -e .` + 裝 deps 才會綠 |
| **test_cross_market** | ❌ FAIL | `phlx_semi` 已從 `US_TW_MAPPING` 移除→0 候選；且斷言參照不存在的 key |
| **test_pipeline_dry** | ❌ FAIL | 斷言 `"因果樹" in report_md`，但 generator 從不輸出此字串 |
| **test_demo_offline** | ❌ FAIL | 同上 `"因果樹"` 斷言 |

- **(a) test_cross_market**：[test_cross_market.py:41-48](tests/test_cross_market.py:41) 用 `make_us_signal("phlx_semi", 0.12)`，但 `phlx_semi` 已從 [macro.py:89 `US_TW_MAPPING`](src/market_scan_mcp/data/macro.py:89) 移除（PHLX/SOX 無 keyless FRED feed，semis 改走 `nasdaq`）→ `tw_theme_families` 為空 → 0 候選 → `assert len(cands) >= 1` 失敗。第 47 行 `assert c["us_sector"] == "phlx_semi"` 又參照了 scout 根本不產生的 key（scout 產生 `tw_family`/`us_moves`，[scout.py:55](src/market_scan_mcp/reviewer/scout.py:55)）。
- **(b) test_pipeline_dry + test_demo_offline**：兩者都斷言 `"因果樹" in report_md`，但我 grep 確認**「因果樹」字串在 [generator.py](src/market_scan_mcp/reporting/generator.py) 完全不存在**（報告用的標題是「受益股(條列)」）。→ 這兩個測試**從沒對現行 generator 通過過**——代表 generator 的 section 標題改過、測試沒連動更新、且之後沒人完整跑過測試。
- **(c) mcp_integration 的「假失敗」教訓**：未 `pip install -e .` 時，MCP stdio client 不會傳遞 `PYTHONPATH`，5 個 server 子進程全 import 失敗回 `Connection closed`。裝好後全綠。這也提醒：[.mcp.json](.mcp.json) 用 `"command": "python"`（裸 python），**強依賴使用者已把套件裝進該 python 的 site-packages**——marketplace 安裝指引要講清楚。
- **影響**：HANDOFF.md「全部通過測試」與事實不符。代表沒有 CI gate，且修改 `US_TW_MAPPING`／generator 標題時沒連動測試。
- **建議**：修這 3 個測試（cross_market 改用 nasdaq/sp500 + 對齊 key；兩個 `"因果樹"` 斷言改成 generator 真的會輸出的字串如「受益股」）；**加 GitHub Actions：`pip install -e ".[agents,schedule]"` + 跑全套**。

**P0-2　`requirements.txt` 是壞的，clean-room 裝不起來　✅ 已驗證**
- [requirements.txt](requirements.txt) 只有 `pandas / yfinance / requests`（Phase 0 的 deps），缺了 `mcp, feedparser, pytrends, python-dotenv, beautifulsoup4, lxml, jieba`——這些都在 [pyproject.toml:11-22](pyproject.toml:11)。
- 我在本機驗證：`import feedparser` → `ModuleNotFoundError`（套件未隨環境安裝）。任何人 `pip install -r requirements.txt` 後跑 news/policy server 會直接 `ImportError`。
- **建議**：刪掉 `requirements.txt`，統一用 `pip install -e .`；或讓它 `-e .` / 與 pyproject 同步。README 已寫 `pip install -e .`，但 `requirements.txt` 存在會誤導人。

**P0-3　fallback 相似度可超過合約上限 1.0　✅ 已驗證**
- [store.py:125](src/market_scan_mcp/history/store.py:125) `score = overlap / (len(q | d) ** 0.5)`。當 query 與 doc 高度重疊、union 小時，分子可大於 `sqrt(union)`，score 可 >1.0。
- **實測**：用一個*寫實*的航運 query（`航運 貨櫃 運價 SCFI BDI 長榮 陽明 萬海 散裝`）跑 `_fallback_query`，`shipping_2020` 得分 **1.083**（degenerate 情況 query==theme_doc 高達 8.832）。→ 一個正常的航運候選會得到 `confidence = 1.08`，報告會印「信心 1.08」。
- `Match.score` 文件寫「0..1」、[schema.py:132](src/market_scan_mcp/reviewer/schema.py:132) `confidence` 規定 `maximum: 1`，而 heuristic verdict 直接把 `confidence = round(top["similarity"], 3)`（[engine.py:98](src/market_scan_mcp/reviewer/engine.py:98)）。→ 報告可能出現「信心 1.3」這種違反 schema 的值。
- **建議**：fallback 分數最後 `min(1.0, ...)`；或改用標準 cosine / Jaccard。

### P1 — 影響正確性或可信度

**M1（資料正確性）　`term_history` 缺 UNIQUE，"upsert" 實際在累積重複列　✅ 已驗證**
- DDL（[db.py:58-64](src/market_scan_mcp/storage/db.py:58)）的 `term_history` 沒有 `UNIQUE(date,term,source)`；但 [upsert_term_count](src/market_scan_mcp/storage/db.py:176) 用 `INSERT OR REPLACE`。沒有衝突目標 → `OR REPLACE` 退化成純 `INSERT`，同一 (date,term) 每次跑都新增一列。
- **實測**：對同一 `(2026-06-01, AI伺服器, news.anomaly)` 連呼叫 `upsert_term_count` 兩次（count 5、9）→ `term_history` 出現 **2 列**，`term_baseline` 變成兩列平均 **7.0**（本應是最新值 9）。對照 `index_history`（有 `UNIQUE(name,date)`，[db.py:89](src/market_scan_mcp/storage/db.py:89)）同樣操作只留 **1 列**——證明 term_history 的 "upsert" 是壞的。
- **影響**：跨週 baseline（`term_baseline` 取窗內 `sum/len`）會被重複列稀釋/膨脹，且表會無限長大。目前因為每天 date 不同、影響有限，但這是 latent bug，一旦同日多次跑就失真。
- **建議**：補 `UNIQUE(date,term,source)` 並加 index。

**M2（評測可信度）　backtest 的 recall 指標衡量不到它宣稱的東西　✅ 已實證**
- 被斷言的指標其實是 **3/5**（不是我 iter-1 誤寫的 5/5；`test_backtest_recall` 斷言 `>=3`，剛好踩在門檻）。
- **實證拆解**（跑 `run_recall_suite` + 直接探測 `_theme_keyword_hit`）：
  - 判定式為 `recalled = (grade != "reject") AND (keyword_hit OR tier1_overlap)`。
  - **criterion (a) `keyword_hit` 恆為 True**：5 個候選的 `theme_hint` 全部**就是主題名本身**（合成訊號 `term = theme["name"]`，[backtest.py:63](src/market_scan_mcp/reviewer/backtest.py:63)），拿主題名去比對含主題名的 theme document 必中。控制組驗證：hint=`'矽光子'`→True，但 hint=`'口罩 防疫 疫苗'`→False、隨機詞→False。→ 這個 criterion 是**死重，零鑑別力**。
  - 因此 3/5 **完全由 RAG sim≥0.2 的 gate（grade≠reject）決定**，且**靠的是匹配到「別的」主題**：ai→`ai_main_2024`、defense→`energy_2022`、mask→`stay_at_home_2020`。被遮的正確主題從來不需要被找到（設計上也找不到）。
  - **較誠實的 `recall_at_k` = 5/5，但那是循環的**：query 由主題自己的名稱/關鍵詞組成、而 store 裡就有該主題 → 必然 rank 1（等於「文件用自己的關鍵詞檢索自己」）。
- **影響**：spec §10 宣稱「dry run 在歷史 case 還原出當時應推薦的題材」——但目前**兩個指標都量不到「還原正確題材/族群」**：一個靠恆真 criterion + sibling 匹配，一個是自我檢索。系統的真實檢索鑑別力仍**未知**。
- **建議**：(1) 移除恆真的 `keyword_hit`；(2) query 改用「trigger 事件描述」而非主題名；(3) 成功判定改成「找到正確**族群/tickers**」並引入**負樣本**（看似題材但沒漲者），算真實 precision/recall。

**M3（一致性）　時間戳格式不一致 + 用了 deprecated API　✅ 已驗證**
- envelope 用 timezone-aware `datetime.now(timezone.utc).isoformat()`（正確），但 [db.py:128](src/market_scan_mcp/storage/db.py:128) 的 fallback 用 `datetime.utcnow().isoformat()`。
- **實測**（Python 3.12.10、`-W all`）：(a) `utcnow()` **確實噴 DeprecationWarning**；(b) 兩者格式不同——fallback `'2026-06-01T03:57:46.914000'`（**naive、無 `+00:00`**）vs envelope `'...+00:00'`（aware）；(c) 同一秒字串比較 `aware '...+00:00' < naive '...123456'` 為 **True**（`+`=0x2B < `.`=0x2E），所以 `query_signals` 的 `timestamp >= since` 過濾**排序依格式而異**。
- **建議**：fallback 也用 `datetime.now(timezone.utc).isoformat()`。

**M4（韌性）　feedparser 抓取繞過 `polite_get`，沒有 timeout　✅ 已驗證**
- [sources.py:146](src/market_scan_mcp/news/sources.py:146)、[policy/server.py:87](src/market_scan_mcp/policy/server.py:87)、[shipping.py:96](src/market_scan_mcp/data/shipping.py:96) 都直接 `feedparser.parse(url)`，由 feedparser 自己抓 HTTP——**完全沒用到你精心做的 `common/http`（timeout/retry/UA）**。
- **實測**：`socket.getdefaulttimeout()` = **None**（無全域 timeout＝可永久阻塞）；`feedparser.parse` 簽名**無 `timeout` 參數**；對照 `polite_get` 有 `timeout`（15s）。→ 掛住的 feed server 會讓 news/policy/scfi 感測器**無限期卡死**（requests-based 的感測器則不會）。
- **建議**：用 `polite_get(url).content` 抓回 bytes 再餵 `feedparser.parse(bytes)`，統一走有 timeout 的路徑。

### P2 — 衛生 / 維運

| # | 問題 | 位置 |
|---|---|---|
| H1 | 顯示 bug：`pre_excess` 恰為 `0.0`（falsy）時，`x and f"..." or 'N/A'` 會印 `N/A` 而非 `+0.0%` | [validator/cli.py:117](src/market_scan_validator/cli.py:117) |
| H2 | `quiet_stdout` 定義了但全專案未使用（docstring 自承）——dead code | [io.py:19](src/market_scan_mcp/common/io.py:19) |
| H3 | 大量 `except Exception: pass`（storage wiring、cross-week、backfill）靜默吞錯，debug 困難；除 scheduler 外無 logging | [pipeline.py:146-180](src/market_scan_mcp/reviewer/pipeline.py:146) |
| H4 | LLM 輸出用 `find("{")/rfind("}")` + `json.loads` 解析，未對既有 `REVIEW_JSON_SCHEMA` 做 validation | [engine.py:135](src/market_scan_mcp/reviewer/engine.py:135) |
| H5 | `MarketScanDB` docstring 自稱 thread-safe，但實為「假設單寫入者」；措辭過度承諾 | [db.py:95](src/market_scan_mcp/storage/db.py:95) |
| H6 | `__init__.py` 版本 `0.1.0` 與 pyproject 各自寫死，未來易不同步 | [\_\_init\_\_.py:8](src/market_scan_mcp/__init__.py:8) |

**文件 vs 程式碼漂移（✅ 已逐檔比對 docs 與 src）**

| # | 漂移 | 嚴重度 |
|---|---|---|
| D1 | **price/README.md 稱 `get_quote`/`volume_anomaly` 用 yfinance ✅，但程式碼用 FinMind**（[price/server.py:31](src/market_scan_mcp/price/server.py:31) `finmind.query`，模組 docstring 明寫「NOT yfinance」）。這**自打嘴巴**——專案招牌紀律就是「server 不用 yfinance」，公開文件卻寫反 | 中（對外事實錯誤） |
| D2 | news/README.md 稱斷詞是「2-4字 CJK chunk 粗略法,非真正分詞」，但程式已升級成 **jieba POS**（chunk 只是 fallback，[sources.py:119](src/market_scan_mcp/news/sources.py:119)）→ 文件**低估**現有能力、過時 | 低 |
| D3 | routine-setup.md 寫死舊路徑 `D:\git\harness-run\market-scan` 與作者本機 `C:\Python314\python.exe`（[routine-setup.md:10](docs/routine-setup.md:10)）；scheduling.md 同樣機器特定 → 公開 marketplace 文件不該含作者私有路徑 | 低 |
| D4 | news/README.md 的 `detect_news_anomaly` 簽名漏了 `db_path` 參數（跨週基線） | 微 |
| D5 | zh-tw.md「每日 routine 已設定成推送…」暗示有隨附設定，實為作者自身 setup | 微 |

> 補充正面：data / policy / price 三個 README 的「誠實限制」段落與程式碼高度一致（East Money BDI、SCFI ingest-only、TWSE 只有最新交易日、漲停 ≥9.5%、上櫃 TODO），honest-stub 紀律在文件層也守住了——漂移集中在「能力描述過時」而非「假裝有功能」。

---

## 4. 跨領域問題（Cross-cutting）

1. **測試體系**：9 個測試都是 `def main(): ... assert ...; raise SystemExit(main())` 的獨立腳本，不是 pytest 可收集的格式，沒有 fixture、沒有 `conftest.py`、沒有一鍵跑全套的 runner。`sys.path.insert(0, "src")` 散落各檔。→ 改成 pytest + `pytest.ini`/`pyproject` 的 `[tool.pytest]`，CI 一行 `pytest` 跑完。
2. **CI/CD 完全缺席**。沒有 `.github/workflows`。對一個要上公開 marketplace 的 plugin，最起碼要有「push → 裝得起來 + 測試全綠 + lint」的 gate。P0-1/P0-2 正是因為沒有它才會發生。
3. **套件/依賴一致性**：`requirements.txt` vs `pyproject.toml` 不一致（P0-2）。`agents`、`schedule` 是 optional deps，但測試（如 backtest）其實只依賴 core——這點是好的，可離線跑。
4. **可觀測性**：daily run 在排程下若 storage/backfill 失敗，使用者只會看到報告少了一塊，沒有任何 log 線索。建議引入結構化 logging（至少 sensor 失敗、persist 失敗要 WARN）。
5. **型別/Lint**：程式碼有用 `from __future__ import annotations` 與型別註記，品質不錯，但沒有 `ruff`/`mypy` 設定檔，`# noqa: BLE001` 是手寫的——代表曾經跑過 linter 但沒有固化進 repo。
6. **資料來源脆弱性集中管理**：RSS/HTML/JSON 來源散在各 sensor，East Money / Google News RSS / TWSE OpenAPI 任一改版都會壞。建議建一個「來源健康檢查」測試（network-gated，CI 可選跑），及早發現 feed 失效。
7. **安全性：實質乾淨（✅ 已掃）**。逐項檢查：(a) **無 SQL injection**——`storage/db.py` 全程參數化（`?` placeholder），`f"SELECT … {where}"` 只內插**寫死的子句片段**（`"source = ?"` 等），不含使用者資料；(b) **無程式執行原語**——全 repo 無 `eval`/`exec`/`os.system`/`subprocess`/`pickle`/`shell=True`/`yaml.load`/`input()`；(c) **無 SSRF 面**——feed URL 來自固定 registry，使用者的 `source` 參數是 dict 查表、非被抓取的 URL；(d) secrets 走 `.env`、不 log。**唯一 micro-nit**：[shipping.py:79](src/market_scan_mcp/data/shipping.py:79) 用 `__import__("re")` 風格怪異（直接 `import re` 即可），無害。→ 對一個研究工具而言，攻擊面小且處理得當。

---

## 5. 改善路線圖（按投入產出比排序）

**立刻（半天內，全是低風險高回報）**
1. 修 `test_cross_market.py`（P0-1）、刪/修 `requirements.txt`（P0-2）、`min(1.0, …)` 夾住相似度（P0-3）。
2. 加 `.github/workflows/ci.yml`：`pip install -e ".[agents,schedule]"` + `pytest`。先把 9 個腳本包成 pytest test（最小改動：每個檔加 `def test_x(): assert main() == 0`）。

**短期（1-2 天）**
3. 補 `term_history` 的 UNIQUE 約束 + migration（M1）。
4. feedparser 改走 `polite_get`（M4）；統一時間戳（M3）。
5. backtest 改成非恆真的 recall 指標（M2）——這關係到你對外宣稱的「能還原歷史對應」可不可信。

**中期（架構層級）**
6. 引入 logging（H3）＋ 對 LLM 輸出做 jsonschema validation（H4）。
7. 把「headless in-process pipeline」與「MCP 多進程」兩條路徑的差異寫進 docs，並各自有整合測試。
8. 建立「資料來源健康檢查」CI job（network-gated）。

**長期（這其實是 VC 報告的重點，見 vc-analysis.md）**
9. 真正缺的不是程式碼，而是**線上前瞻性（forward）紀錄**：把 daily run 用 `--db` 持續跑、累積 `verdicts` / `missed_catch`，才能驗證 spec §10 的線上指標（領先天數、月命中率）。目前 GO 全部建立在後見之明的歷史回測上。

---

## 6. 一句話結論

> **程式碼與設計是「資深工程師的 side project」等級——抽象乾淨、誠實、會從資料學習；但工程基礎建設（CI、測試實跑、套件安裝）是「還沒準備好公開」等級。** 先用半天把 §5 立刻項修掉、補上 CI，這個專案的可信度會立刻跳一級。真正的長期風險不在技術債，而在「核心賭注（即時偵測）尚未被線上驗證」——那屬於產品/投資層面，見 [vc-analysis.md](reports/audit/vc-analysis.md)。
