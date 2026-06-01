# PolyDig 優化建議 —— 架構師視角

**作者視角**:資深系統架構師(Staff/Principal)
**日期**:2026-06-01 ｜ **版本**:v2(經 `architect-reviewer` agent 審查後修訂,評分 B+ → 見文末修訂紀錄)
**前提文件**:`reports/audit/architect-review.md`、本次 GDELT 真實回放發現
**定位**:談「**往哪裡優化**」(forward-looking),不是再做一次 audit。

> 一句話:**PolyDig 的瓶頸不在功能、而在「不知道自己準不準」。** 最高槓桿的架構投資是把「偵測 → 量測 → 校準」變成閉環,而不是再加感測器。

---

## 0. 優化的北極星

任何優化都要通過:**「它能不能讓系統更早、更準、且我們能證明它更準?」** —— 更早(領先天數↑)、更準(假陽性率↓)、能證明(out-of-sample 量測,不靠贏家回測)。

---

## 1. 偵測層:小樣本比率不可信 → 加「樣本信心」阻尼

**現況問題(GDELT 實證,已核對程式碼)**:
- `detect_term_spikes` 的 `score = min(1, ratio/5)`([sources.py:216](src/polydig_mcp/news/sources.py:216))。
- ⚠️ **根本問題不是「`min_recent_count=3` 門檻太低」**——那個 `rc < min_recent_count: continue`([sources.py:210](src/polydig_mcp/news/sources.py:210))是個最小量 guard,作用正常。真正的病灶是:**基線≈0 時,比率的天花板失效**(4 篇 / (0+1) = ratio 4 → 0.8)。`min_count=3` 與「小樣本比率不可信」是兩個不同概念,別混為一談。

**優化**:
```python
vol_conf = min(1.0, recent_count / FULL_CONF)   # 小樣本算出的比率不可信 → 打折
score    = min(1.0, ratio / 5.0) * vol_conf
fire     = recent_count >= ABS_FLOOR and ratio >= RATIO_MIN and score >= threshold
```
- **vol_conf 阻尼**解的是「基線近零時比率膨脹」;`ABS_FLOOR` 是額外的絕對量地板(隨來源規模校準)。
- **z-score 重用要務實**:`shipping.detect_index_anomaly`([shipping.py:179](src/polydig_mcp/data/shipping.py:179))處理的是**時間序列** `[(date,value)]`,`detect_term_spikes` 處理的是**詞頻 Counter**,輸入型別與語意不同,**不該硬抽成共用模組**。真正可重用的只是那 3 行 `mean+pstdev+z` → 抽成一個小 utility 即可,別做架構級重組。
- **驗收測試必須含負樣本**:不能只測「11/19(4 篇)不響、12/31(665 篇)響」(都是正樣本邏輯)。要再加一個反例:**某詞 baseline 也高、ratio=5 但 vol_conf 應打折到不觸發**,否則無法證明阻尼真的擋住雜訊。

---

## 2. 評測飛輪:真實新聞回放 harness(🔥 最高優先)

**這是整個專案最缺的一塊**:沒有分母 → 不知道精確率 → 所有門檻都是猜的。

**建 `polydig-replay`**:輸入歷史期間 + 事件清單;來源 GDELT;逐日餵偵測層;輸出**精確率/假陽性率/領先天數分佈/recall**。

**⚠️ 工作量誠實重估(reviewer 指出我原本低估)**:這不是「拉 API 跑迴圈」。GDELT GKG 是每 15 分鐘一個 ZIP、2017+ 體積龐大,需要一條 ETL:**下載→解壓→過濾 TW 相關→萃取詞頻→灌入 `term_history`**。而且有一個**等效性難題必須先解**:GDELT 的詞頻抽取(GKG Theme tag / 全文 / V1 Article API)與現有 jieba 管線([sources.py](src/polydig_mcp/news/sources.py) 的 `_KEEP_POS` POS 過濾)**不相容**——直接用 GKG tag 模擬 feed 詞頻,等效性存疑。

**里程碑(取代「投入:中」這種模糊估計)**:
| 階段 | 內容 | 估時 |
|---|---|---|
| 0 | **決定詞頻抽取策略 + 驗證與 jieba 管線的等效性** | 2-3 天(最關鍵,決定整體工期) |
| 1 | GDELT ETL(下載/解壓/過濾/萃取) | 3-5 天 |
| 2 | 逐日回放迴圈(含解錨的跨週基線,見 §3) | 2-3 天 |
| 3 | 精確率/領先天數統計 + 接入 CI regression | 2 天 |

**為什麼仍是 P0**:它同時 (a) 校準門檻、(b) 驗證核心 bet、(c) 變成 regression 防止偵測公式偷偷變爛——一個工具解三個問題,值得這個工期。

---

## 3. 即時偵測管線:基線的三個真實缺陷

**現況(已核對)**:
1. **opt-in**:跨週基線只在傳入 `db_path` 時才走([pipeline.py:26,106](src/polydig_mcp/reviewer/pipeline.py:26))——一般執行根本沒有基線,先講清楚這個前提。
2. **錨定 wall-clock**:`term_baseline` 用 `date.today()` 算視窗([db.py:193](src/polydig_mcp/storage/db.py:193)、[server.py:155](src/polydig_mcp/news/server.py:155)),**無法回測歷史日期**(這也是 §2 必須自建 replay 的原因)。
3. **🔴 同日重跑污染基線**(reviewer 抓到、我原本漏掉):`detect_news_anomaly` 先讀 baseline、再 `upsert_term_count(today,…)`([server.py:159](src/polydig_mcp/news/server.py:159))。若同日觸發兩次(scheduler 當機重跑),第二次的 baseline 已含今日資料 → 分母被污染。

**優化(一個改動解 2+3)**:`term_baseline(term, source, as_of=...)` 接受 `as_of`,語意改成「`as_of` 之前的 21 天」,**天然隔離讀寫**,既可回測、同日重跑也不污染。這是 P1 裡最低風險、最高收益的改動。

**另一個已知偏差**:feed entry 沒有發佈時間(`_dt is None`)時,現有碼把它**分進 recent**([sources.py:205](src/polydig_mcp/news/sources.py:205))→ 品質差的 feed 會系統性高估 recent_count,應改為「無時間 → 保守分入 older 或丟棄」。

---

## 4. Reviewer / RAG:從 token 重疊走向真推理

**現況(已核對)**:
- fallback RAG 是 CJK bigram token 重疊;對全新事件靠歷史題材字面重疊,有循環嫌疑(`mask_2020` 字面含「武漢肺炎」)。
- **hold-one-out 其實已實作**(`_MaskedStore`,[backtest.py:101](src/polydig_mcp/reviewer/backtest.py:101))——我原本說「缺非循環評測」不精確。**真正缺的是:負樣本(沒成題材的事件)+ out-of-sample 真實日期**。

**優化**:
1. **負樣本評測**:補「看似題材卻沒漲」的反例,算真實 precision/recall(與 §2 harness 共用)。
2. **真 embedding fallback**:補輕量 sentence-embedding(離線可跑),語意檢索勝過 bigram。
3. **資料飛輪(注意 schema 落差)**:把通過的 verdict + 漏抓案例回灌成新題材種子。但 `insert_verdict` 存的 verdict schema 與 `themes.json` 的 theme schema **不同**([reviewer/schema.py](src/polydig_mcp/reviewer/schema.py) vs themes.json),需要一層 **schema mapping**(causal_tree→tier 結構、補 historical_analogue),這段工作別低估。

---

## 5. 韌性與規模

| 項目 | 現況(已核對) | 優化 |
|---|---|---|
| **來源健康** | 自由財經 feed 曾整個掛掉(回 HTML)沒人發現,只降級不告警 | 「來源健康檢查」CI job(network-gated)+ feed 失效告警 |
| **觀測性** | `except: pass` 其實只 ~7 處(多為 jieba userdict 合理降級);`pipeline.py` 已有 `log.warning`。真問題是**sensor 層失敗只轉成 error signal、沒有 WARNING log** | 補 sensor 層結構化告警,而非泛稱「大量吞錯」 |
| **限流/快取** | FinMind 600 req/hr;news 每次重抓全 feed | HTTP 快取(ETag/304)、FinMind 批次 + 本地 cache |
| **兩條路徑** | MCP 模式下**每個 server 是 `.mcp.json` 定義的獨立 subprocess**(這才是「多進程隔離」來源);headless 是單進程 import | 統一成「sensor 函式庫 + 薄 MCP 包裝」,兩路徑共用核心、各有整合測試 |
| **LLM 成本** | plugin 模式由用戶訂閱吸收(COGS≈0);headless `--mode llm` 無上限 | 加 token 預算 + 同候選快取(需先量化現有 prompt/歷史注入大小,才知道省多少) |

---

## 6. 優先序 Roadmap

| 優先 | 項目 | 依賴 | 為何 |
|---|---|---|---|
| **P0** | §2 replay harness(先解詞頻等效性) | — | 解鎖門檻校準 + 核心 bet 驗證 |
| **P0** | §1 vol_conf 阻尼 + 地板(附**含負樣本**測試) | 參數待 §2 校準 | 止血假陽性 |
| P1 | §3 `term_baseline` 加 `as_of`(解回測+同日污染) | — | 低風險高收益 |
| P1 | §4.3 verdict 回灌(含 schema mapping) | §2 暖機需先有 harness | 唯一會複利的護城河 |
| P2 | §5 來源健康 CI + sensor 告警 | — | 維運/可信度 |
| P2 | §4.2 embedding fallback | — | RAG 品質 |

> ⚠️ **依賴提醒**:§3 的「冷啟動暖機」需要 §2 的 replay 先能跑(灌入歷史詞頻),所以 P1 暖機其實依賴 P0 harness,排程時別當成獨立項。

---

## 7. 結論

> **別再加感測器,先建量測。** 架構已夠用來「產生訊號」,缺的是「知道訊號準不準」的閉環。先做 replay harness(P0,但要先解 GDELT↔jieba 等效性、誠實估 ~2 週工期),它會把後面每個優化從「我覺得」變成「資料說」;偵測公式止血(vol_conf,且要用負樣本驗收)是同一件事的另一面。

---

## 修訂紀錄(v2,經 architect-reviewer 審查)

| review 指出 | 本版如何處理 |
|---|---|
| 🔴 `min_recent_count=3` 是 guard 非 floor,病灶是基線≈0(混淆概念) | §1 重寫,釐清 vol_conf 解的是小樣本不可信 |
| 🔴 漏掉「同日重跑污染基線」bug | §3 新增,並提出 `as_of` 一併解決讀寫隔離 |
| 🔴 z-score「抽成模組」忽略 time-series vs Counter 型別不同 | §1 改為「抽 3 行小 utility」,不做模組重組 |
| 🟡 replay harness 工作量低估、且有 GDELT↔jieba 等效性難題 | §2 加里程碑表 + 等效性前置任務(~2 週) |
| 🟡 hold-one-out 已存在 | §4 改為「真正缺的是負樣本 + out-of-sample」 |
| 🟡 「大量 except:pass」誇大;兩路徑拓樸不精確 | §5 修正措辭(~7 處、subprocess 來源) |
| ➕ `--db` 是 opt-in、`_dt is None` 偏差、verdict↔themes schema 落差、暖機依賴 harness | §3/§4/§6 補上 |
| 驗收測試只有正樣本 | §1 要求加負樣本反例測試 |
