---
name: polydig-daily
description: PolyDig 台股題材早期偵測。當使用者問「今天有什麼?」「最近有什麼熱門族群?」「幫我掃一下台股」「scan 一下」「研究 X 主題」「最近有什麼還沒發酵的題材」等,啟動每日掃描或主題研究。輸出中文研究報告。
---

# PolyDig — 台股題材早期偵測

**系統靈魂**:找的是**事件還沒發酵、有領先效果**的訊號。不是追已經漲完的族群。

這是**研究助理**,輸出研究報告,**不下單、非投資建議**。

## 何時用
使用者用自然語言要求掃描台股題材、盤點熱門族群、研究特定主題,或產生每日早報。

## 流程

### A. 每日掃描(「今天有什麼?」)
1. 用 **polydig-scout** subagent 掃描感測器(news/data/price MCP),取得候選主題。
2. 對每個候選,用 **polydig-reviewer** subagent 做族群識別 + 因果樹 + 歷史對應 + 分級。
3. 用報告產生器彙整成中文 markdown:
   ```bash
   python -c "from polydig_mcp.reviewer.pipeline import run_daily; from polydig_mcp.reporting.generator import write_report; r=run_daily(); print(write_report(r['report_md']))"
   ```
   或直接呈現 Reviewer 的 verdict。
4. 報告分四區:🟢 今日強訊號 / 🟡 觀察清單 / ⚪ 駁回但有趣 / ⚠️ 漏抓案例(若 price safety-net 觸發)。

### B. 主題研究(「幫我研究 矽光子」)
1. 用 polydig-reviewer 直接對指定主題做因果樹 + 歷史對應。
2. 可呼叫 `mcp__polydig-data__*` / `mcp__polydig-price__*` 補當前數據。
3. 讀 `src/polydig_mcp/history/themes.json` 找歷史對應。

## 原則
- 每日強訊號控制在 0-5 個(雜訊控制)。
- 對新型題材(無歷史對應)用強邏輯通過為觀察清單,不要直接駁回。
- 因果樹務必展開到三階以上。
- 缺 token / 感測器失敗時,告知使用者哪個來源離線,不要假裝有資料。

## 設定
需要 `.env` 內 `FINMIND_TOKEN`(data-mcp 用)。缺少時 FinMind 工具回 graceful error,其餘感測器照常。
