# PolyDig

> 台股題材早期偵測系統 — 在事件還沒發酵時抓到

![Status](https://img.shields.io/badge/status-Phase%200%20planning-yellow)

## 一句話

PolyDig 從 5 個訊號源（**News / Price / Data / Policy / Roadmap**）偵測新興題材，用 LLM 推理因果樹 + 找歷史對應，每日產出研究助理報告，給個人投資人做台股題材研究。

## 系統靈魂

> **「找的是事件還沒發酵、有領先效果的訊號」**

如果系統提報的時候股票已經漲了一波，這個系統就毫無價值。

## Documents

- 📘 [Design spec (v0.1)](docs/superpowers/specs/2026-05-31-polydig-design.md)
- 📊 [Case study: 5 themes deep-dive](docs/research/01-theme-case-studies.md)

## Architecture

```
[News] [Price-safety-net] [Data] [Policy] [Roadmap]    ← 5 MCP servers
                  ↓ (MCP tool calls)
    Scout Agent (Haiku 4.5)
                  ↓
    Reviewer Agent (Sonnet 4.6 / Opus 4.7)
       - 族群識別
       - 因果樹三階展開
       - 歷史對應檢索 (RAG)
                  ↓
       Daily report (markdown + push)
```

## Phases

| # | Phase | Status |
|---|---|---|
| 0 | Leading Edge Validator (POC, 驗證根本假設) | 🚧 Planning |
| 1 | MCP foundation (news, price, data) | ⏳ |
| 2 | Scout + Reviewer agents | ⏳ |
| 3 | Report generator | ⏳ |
| 4 | Complete sensors + Price safety net + 漏抓回溯 | ⏳ |

## Tech stack

- Python 3.11+
- Anthropic Claude SDK (Haiku 4.5 / Sonnet 4.6)
- MCP (Model Context Protocol)
- [FinMind](https://finmindtrade.com/) — 台股資料
- SQLite + Chroma (vector DB for 歷史庫 RAG)
