# Market Scan Phase 0 — Validation Results & Go/No-Go Decision

**Date**: 2026-05-31
**Author**: Autonomous run by Claude Haiku 4.5 on Arthur's instruction
**Parent docs**: [`2026-05-31-market-scan-design.md`](2026-05-31-market-scan-design.md), [`2026-05-31-phase-0-validator-plan.md`](../plans/2026-05-31-phase-0-validator-plan.md)
**Raw output**: [`reports/2026-05-31_validator/`](../../../reports/2026-05-31_validator/)

---

## TL;DR

> # ✅ **GO** — Market Scan 的根本假設驗證通過，啟動 Phase 1
>
> **4 / 5 cases** 有至少 1 個「強領先」trigger，**5 / 5 cases** 有至少 1 個「領先」trigger（強或弱）。
> 15 個測試點中：6 強領先 / 5 弱領先 / 3 太晚 / 1 無效。

---

## 結果一覽

| Case | 訊號類型 | early trigger | mid trigger | late trigger | 是否值得做？ |
|---|---|---|---|---|---|
| 🟢 口罩/防疫股 | News | 🟢 強 | 🟢 強 | 🟡 弱 | **是** — 武漢肺炎首見當天就能進場 |
| 🟢 貨櫃航運 | Data | 🟢 強 | 🔴 太晚 | 🔴 太晚 | **是** — SCFI 數據先動是真實 edge |
| 🟢 AI 概念股 | News-Intl | 🟢 強 | 🟢 強 | 🔴 太晚 | **是** — ChatGPT 上線就是訊號 |
| 🟡 國防/俄烏 | News-Sudden | 🟡 弱 | 🟡 弱 | 🟡 弱 | **可** — 邊際 edge，題材小 |
| 🟢 矽光子/CPO | Roadmap | 🟢 強 | 🟡 弱 | ⚫ 無效 | **是** — 國際大廠路線圖是領先指標 |

---

## 5 個重要發現

### 1️⃣ 「事件還沒發酵就抓到」是真的有 edge

**口罩 early (2019/12/31 武漢通報當天)**：
- 康那香 -12.5% (事前低於大盤) → 180 天後 **+310%** (excess vs TAIEX)
- 恆大 -10.7% → 180 天後 **+906%**
- 系統在新聞主流化前 25 天就能提報，後續報酬率驚人

**AI early (2022/11/30 ChatGPT 上線當天)**：
- 緯創 +1.4% (事前持平) → 180 天後 **+132%**
- 廣達 -7.8% → +58%
- 技嘉 +29% → +59%
- 系統在 NVIDIA 財報暴擊 (2023/5/24, 通常認為的 AI 起漲日) 之前**整整 6 個月**就能提報

→ 這完全驗證了你的核心需求：「找的是事件還沒發酵、有領先效果的訊號」。

---

### 2️⃣ 「等新聞主流化才進場」幾乎都太晚

3 個 🔴 太晚的 trigger 全部是「主流媒體大幅報導日」：
- 航運 mid (2020/12 缺櫃新聞): pre 已 +70%
- 航運 late (2021/3 長賜輪): pre 已 +34%
- AI late (2023/5 NVIDIA 財報): pre 已 +43%

→ 完全證實你前面的洞察：**等新聞登上主流媒體時，股價已經先反映了**。系統的價值就在於**比新聞早**。

---

### 3️⃣ 多窗口設計拯救了「慢熱型」題材

如果只看 post30（v0.1 classifier 的錯誤），這些 case 全部會被誤判為 ⚫ 無效：

| Case | post30 (假性無效) | post180 (實際大爆發) |
|---|---|---|
| AI early (ChatGPT) | +5.9% | **+83.3%** |
| AI mid (Bing+ChatGPT) | +3.0% | **+205%** |
| 航運 early (SCFI) | -2.7% | **+112%** |
| 國防 late (全面入侵) | +3.9% | +32% (還是 WEAK) |

→ **教訓**：題材股的反應 lag 從 0 天到 6 個月都有，validator 必須看多窗口。Phase 1 的 Reviewer Agent 必須也用多窗口邏輯。

---

### 4️⃣ Roadmap-driven 題材（矽光子）edge 持續性最長

矽光子 NVIDIA GTC 2023/03/21 提及 CPO → 18 個月後 TSMC 確認量產：
- 早期 trigger (2023/03): STRONG — 華星光 180 天 +234%
- 中期 trigger (2024/09 SEMI 聯盟): WEAK — 部分股票仍有 edge
- 晚期 trigger (2025/01 TSMC 確認): NULL — 都太晚

→ Roadmap sensor 是最有「時間優勢」的 sensor，因為大廠路線圖往往領先股價 6-12 個月。

---

### 5️⃣ 國防股的 edge 比預期小

我前面 case study 把國防股列為「強訊號」，但實際 backtest：
- 漢翔 post180 +17-37%
- 雷虎 post180 +16-30%

雖然絕對值不錯，但**沒打到 STRONG 門檻** (post180 > 80%)。國防題材是真實的小波段，不是大波段。
→ 未來系統提報國防類題材時，要降低期望，不要當成口罩/AI 那種大噴出。

---

## 對 Market Scan 系統設計的影響

### 必須做的修正

1. **Reviewer Agent 的判定邏輯**：
   - 必須用多窗口（30/90/180 天）評估
   - 不能只看「訊號出現後 1 個月」就下定論
   - 對「慢熱型」訊號（roadmap、structural）要有耐心

2. **「太晚」自動偵測**：
   - 系統提報時必須先檢查「事前 90 天該族群是否已漲 > 30% (vs TAIEX)」
   - 是 → 警示用戶「此訊號可能已被市場提前反映」

3. **訊號類型分級的預期報酬**：
   - News (口罩、AI): 預期高（80%+ in 180 days）
   - Data (航運): 預期高
   - Roadmap (矽光子): 預期高，但有 6 個月 lag
   - News-Sudden (國防): 預期中（15-50% in 180 days）

### Phase 0 已建立的資產

✅ **5 筆結構化歷史題材資料** (在 `summary.json`) → Reviewer 歷史庫的第一批種子
✅ **可重複跑的 validator CLI** → 之後可以加新題材到 `cases.json` 持續驗證
✅ **明確的閾值定義** → Reviewer 判定可以直接套用同樣的 thresholds

---

## 注意事項與限制

1. **代表股是手選的** — 我選的是因果樹「一階受益股」，沒考慮其他可能更好的股票。Phase 1 的 Reviewer 必須自己推理出代表股。
2. **Trigger 日期是「事後標記」** — 我們知道 2019/12/31 是武漢肺炎的關鍵日。Phase 1 的 Scout 要在當天就能從**全部新聞中**找出這條，難度高很多。
3. **TAIEX 對照不完美** — 沒有 beta 調整、沒有風險調整。但對 Phase 0「是否有 edge」的判定夠用。
4. **這次用 yfinance 不是 FinMind** — 因為 FinMind 需要 API key。Phase 1 加上 FinMind 後可以拿到更細的資料（chip data、外資進出）。
5. **15 個樣本還是小** — 跑得通 ≠ 普適。Phase 4 之後應該擴展到 20-30 個歷史題材重新驗證。

---

## 推薦下一步

### 立即 (Phase 1 - 2 週)
1. **建 `news-mcp`**：先做最簡單但最關鍵的 sensor (RSS + Google Trends)
2. **建 `data-mcp`**：包 FinMind API + SCFI/BDI 公開資料
3. **重用 validator 的歷史庫**：把 5 個 case 的數據導入 Reviewer 的歷史對應 DB

### 中期 (Phase 2 - 2 週)
4. **建 Scout Agent**：用 Haiku 4.5 跑「對 5 個案例的歷史新聞 dry-run」，看能否還原出我們手選的 trigger 日期
5. **建 Reviewer Agent**：用我們驗證過的多窗口分類邏輯做為 Reviewer 的判定 prompt

### 後續驗證 (Phase 4)
6. **擴展到 20 個題材**：把 case study 報告中其他 15 個題材也跑一次 validator
7. **重新校準閾值**：用 20 個樣本重算 STRONG/WEAK 邊界

---

## 結論

> Market Scan 不是空想。在 15 個歷史測試點中，**11 個 (73%)** 有明確的領先 edge，其中 **6 個 (40%)** 是強領先。
> 系統的核心假設「**事件發酵前能被偵測、且後續股價有顯著 alpha**」在實證上**成立**。
>
> 可以放心啟動 Phase 1，把 5 sensors 蓋起來。
