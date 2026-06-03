# Market Scan — 全專案審查（架構師 + VC 雙視角）

**日期**：2026-06-01 ｜ **commit**：`1d122ce` ｜ **範圍**：54 個 Python 檔 / 4,645 行 + 全部 docs/configs/data/tests 逐檔閱讀

## 兩份報告

| 報告 | 內容 |
|---|---|
| [architect-review.md](reports/audit/architect-review.md) | 架構師視角：分層評估、**已驗證的 bug 清單（P0–P2）**、跨領域問題（含安全性）、改善路線圖 |
| [vc-analysis.md](reports/audit/vc-analysis.md) | 創投視角：核心賭注與證據、護城河、商業模式、競品、TAM、**投顧法風險**、可投資里程碑 |
| [action-plan.md](reports/audit/action-plan.md) | **整合行動計畫**：把上面兩份的建議合併成一條「週一/本週/本月」時間軸 + 決策閘門 |

## 最重要的 5 個發現（懶人包）

1. **🔴 測試套件 3/9 真實失敗、且無 CI**（架構 P0-1，✅ 全套實跑）：實跑 9 個測試 = **6 PASS / 3 FAIL**，3 個失敗全是離線邏輯（與網路/deps 無關）：`test_cross_market`（`phlx_semi` 已從 `US_TW_MAPPING` 移除）、`test_pipeline_dry` + `test_demo_offline`（都斷言 `"因果樹"`，但 generator 從不輸出此字串）。HANDOFF 宣稱「全部通過測試」與事實不符。
2. **🔴 `requirements.txt` 裝不起來**（架構 P0-2，✅ 已驗證）：只列 3 個 dep，缺 mcp/feedparser/jieba… 等 7 個。clean-room 安裝會 ImportError。
3. **🟠 核心賭注未驗證**（VC §2）：Phase 0 的 GO 建立在「後見之明手選的標的+日期」上，證明的是「市場存在」，不是「能穩定抓到」。即時偵測 = 未解風險。
4. **🟠 護城河目前是空的**（VC §3）：MIT 開源（程式無護城河）+ 22 個可重建的題材。唯一會複利的是「線上前瞻語料」，但 DB 還沒開始累積。
5. **🟠 投顧法風險 + 無商業模式**（VC §4、§6）：對公眾薦股在台灣受《證投信顧法》規管；商業化前需法遵釐清。

**最高槓桿、近乎免費的下一步**：`market-scan-daily --db ./market-scan.db` 每天跑，累積 out-of-sample 前瞻紀錄，6–12 個月後量 spec §10 的線上指標。這同時解鎖「核心賭注驗證」與「護城河計時器」。

---

## 🔧 修復實作（branch: `fix/audit-findings`，未 commit，`pytest` 13/13 綠）

應使用者「尚未完成項目幫我全部完成並完整測試過都要正確」指示，已在分支實作並驗證：

| 項目 | 狀態 | 驗證 |
|---|---|---|
| P0-1 修 3 個失敗測試 + 加 `.github/workflows/ci.yml` | ✅ | 全套 **9 PASS / 0 FAIL** |
| P0-2 修 `requirements.txt`（補齊 10 個核心 dep） | ✅ | 所有 module import OK |
| P0-3 相似度 `min(1.0)` | ✅ | 寫實 query 實測 score=1.0 |
| M1 `term_history` UNIQUE | ✅ | 兩次 upsert→1 列、baseline=最新值 |
| M3 時間戳 aware + 移除 `utcnow()` | ✅ | import 通過 |
| M4 feedparser 走 `polite_get`（3 處） | ✅ | 5/6 feed OK |
| M2 backtest 去恆真（移除 keyword_hit、docstring 誠實化） | ✅ | recall 仍 3/5、測試綠 |
| D1 price/README yfinance→FinMind · D2 jieba · D3 stale 路徑 | ✅ | — |
| H1 validator 顯示 bug(pre_excess=0.0→N/A) 用 `_fmt_pct` 修 | ✅ | `_fmt_pct(0.0)`='+0.0%' |
| H3 pipeline 靜默 `except:pass`→logging | ✅ | logger 注入、suite 綠 |
| H4 LLM 輸出輕量 schema 驗證(壞→fallback heuristic,無新 dep) | ✅ | 好 dict 過 / 3 種壞 dict 正確 raise |
| H5 db docstring 去除過度 thread-safe 宣稱 · H6 版本改由 metadata 單一來源 | ✅ | `__version__` 解析 OK |
| **測試改寫成 pytest**（含新 test_metrics）+ CI 改用 `pytest` | ✅ | — |
| **NEW**：補先前無測試的純邏輯模組（envelope/errors/settings、telegram、finmind 缺 token 路徑、prompt builders）→ `test_common`、`test_telegram`、`test_finmind_prompt` | ✅ | `python -m pytest` → **13 passed** |
| **NEW bug**：補上漏註冊的 `market-scan-daily` script entry（docs 全程叫它,但 pyproject 沒註冊→指令根本不存在）+ 加 `market-scan-metrics` | ✅ | `market-scan-daily --help` 可執行 |
| **NEW**：建 spec §10 量測工具 `reviewer/metrics.py`（signal_volume 立即可用；hit_rate 接 FinMind 價格源 `--prices finmind`）+ `test_metrics.py` | ✅ | `market-scan-metrics` 輸出 dashboard、graceful |
| **驗證（都要正確）**：`market-scan-daily --demo` 端到端產出正確報告（強訊號/因果樹/研究報告皆在）；policy `mohw` RSS 實測**真的可用**（text/xml,20 則）→ 更新「待驗證」註記 | ✅ | demo 2740 字報告、mohw bozo=False |
| **BONUS**：發現並修好真實掛掉的 RSS（自由財經 feed 改 `news.ltn.com.tw/rss/business.xml`） | ✅ | 實測 6/6 feeds OK |

**無法由我完成（需時間/資料/創辦人決策）**：
- 三 方法論：**量測工具已建好**（`metrics.py`：signal_volume 立即可用、hit_rate 可注入價格源、皆有測試）；但**指標的「值」仍需 ≥1 季線上 `--db` 資料累積**（無法快轉時間）+ 負樣本人工策展
- 四 商業/策略：投顧法法遵、wedge 選擇、定價、TAM 查證
- 刻意保留：H2 `quiet_stdout`（io.py 已註明是「未來 stdout-noisy 函式庫的工具」,屬刻意保留的工具而非死碼,故不刪）

---

## 審查進度 / 迭代記錄（Ralph loop）

### Iteration 1（2026-06-01）— done
- ✅ 逐檔讀完全部 src（54 檔）、tests（9 檔）、docs、themes.json、cases.json、configs
- ✅ 實跑重現 P0-1（test_cross_market 失敗）、P0-2（feedparser 未安裝）
- ✅ 產出 architect-review.md + vc-analysis.md

### Iteration 2（2026-06-01）— done（全面實證）
- ✅ **實跑全 9 個測試**：6 PASS / 3 FAIL（cross_market、pipeline_dry、demo_offline），全為離線邏輯失敗
- ✅ 發現並驗證**新 bug**：generator 從不輸出 `"因果樹"`，但 2 個測試斷言它 → grep 確認字串不存在
- ✅ **實證 P0-3**：寫實航運 query → `shipping_2020` 相似度 **1.083 > 1.0**
- ✅ **實證 M1**：同 key 兩次 `upsert_term_count` → term_history 出現 **2 列**（index_history 對照只 1 列）
- ✅ 釐清 mcp_integration「假失敗」：未 `pip install -e .` 時 MCP stdio 不傳 PYTHONPATH → 裝好後全綠
- 仍為靜態判定：M2 backtest 恆真、M3 時間戳、M4 feedparser 無 timeout

### Iteration 3（2026-06-01）— done（評測可信度 + 競品）
- ✅ **實證 M2**：`keyword_hit` criterion 恆為 True（候選 hint 全是主題名本身；控制組驗證）；asserted recall 實為 **3/5**（非 iter-1 誤寫的 5/5），且 3/5 完全由 RAG sim≥0.2 gate 決定、靠匹配**別的**主題；`recall_at_k`=5/5 是循環自我檢索。→ 兩指標都量不到 spec §10 宣稱的「還原正確題材」。已改寫 architect-review M2。
- ✅ **競品定性對照表**：加入 vc-analysis §5（MacroMicro/CMoney/XQ/Fugle/投顧/通用LLM），點出 Market Scan 的四合一白地與「通用 LLM 是最大替代威脅」。

### Iteration 4（2026-06-01）— done（docs 一致性 + TAM；達成 100% 檔案覆蓋）
- ✅ 讀完最後 8 個未讀文件（docs/{routine-setup,scheduling,zh-tw}、4 個 sensor README、phase-0 plan）→ **repo 100% 逐檔覆蓋**
- ✅ 發現 doc/code 漂移 D1–D5；最重要 **D1：price/README 說用 yfinance，程式碼實際用 FinMind**（自打「server 不用 yfinance」的招牌紀律）。已加入 architect-review §3。
- ✅ **TAM/SAM 量級試算**：bottom-up 漏斗 → 現有通路可觸及 **~3k–36k**（hobbyist-scale，非 venture-scale）；加入 vc-analysis §1.1
- 正面記錄：data/policy/price README 的「誠實限制」段與程式碼高度一致

### Iteration 5（2026-06-01）— done（收尾：所有發現實證完畢）
- ✅ **實證 M3**：`utcnow()` 確實噴 DeprecationWarning；fallback 產生 naive `'…914000'`（無 `+00:00`）vs envelope aware；同秒字串比較 `aware < naive`=True → `timestamp >= since` 排序依格式而異
- ✅ **實證 M4**：`socket.getdefaulttimeout()=None`、`feedparser.parse` 無 `timeout` 參數、`polite_get` 有（15s）→ 掛住的 feed 會讓感測器無限期卡死
- ✅ **里程碑：repo 100% 逐檔覆蓋 + 100% 發現實證完畢**（P0-1/2/3、M1/M2/M3/M4、D1 全部 ✅）

### Iteration 6（2026-06-01）— done（補上安全性維度）
- ✅ **安全性掃描**：參數化 SQL（無 injection）、無 eval/exec/subprocess/pickle/shell、無 SSRF 面、secrets 走 .env → **實質乾淨**；唯一 micro-nit 是 shipping.py 的 `__import__("re")` 風格。加入 architect-review §4-7。
- 至此架構審查的**所有標準維度皆覆蓋**：設計、分層、正確性 bug、文件漂移、CI/測試/deps/可觀測性/來源脆弱性、安全性。

### 狀態：審查完成 ✅（維度齊全 + 發現 100% 實證 + 檔案 100% 覆蓋）
「分析 + 改善建議」已實質結束。**再迭代只剩「動手修 bug／改寫測試／補 CI」——屬於實作而非審查，超出原始提問範圍。**
建議 `/ralph-loop:cancel-ralph` 結束。若要把發現變成 PR，請另開明確的「修復」任務。
