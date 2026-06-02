---
description: PolyDig 台股題材掃描 / 主題研究。用法:/dig today(今日掃描) 或 /dig research <主題>(深入研究某主題)。
argument-hint: "[today | research <主題>]"
---

執行 PolyDig 題材偵測。引數:`$ARGUMENTS`

- 若引數為空或 `today`:執行**每日掃描**。先呼叫 polydig-scout subagent 取得候選,再對每個候選呼叫 polydig-reviewer subagent 做因果樹 + 歷史對應 + 分級,最後彙整成中文 markdown 報告(🟢 強訊號 / 🟡 觀察清單 / ⚪ 駁回 / ⚠️ 漏抓案例)。

- 若引數為 `research <主題>`:對指定主題用 polydig-reviewer 直接做族群識別 + 因果樹三階展開 + 歷史對應(用 `mcp__polydig-data__get_history_match`)+ 分級,並可呼叫 data/price MCP 補當前數據。

提醒:系統靈魂是「找還沒發酵、有領先效果的訊號」。研究助理輸出,非投資建議。
