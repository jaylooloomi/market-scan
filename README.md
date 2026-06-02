# Market Scan

> Leading-edge **scanner** for the Taiwan stock market — surface emerging themes **before**
> the market reacts, and flag market-wide **crash risk**. A research assistant, not an auto-trader.

![License](https://img.shields.io/badge/license-MIT-green)

繁體中文說明見 [`docs/zh-tw.md`](docs/zh-tw.md)。

**Market Scan** scans signal sources for anomalies, reasons out a causal propagation tree of
beneficiary Taiwan stocks, retrieves historical analogues, and writes a daily Chinese-language
research report — surfacing themes while the event is still early. A built-in **crash-watch**
flags market-wide risk-off conditions from leading macro signals (yield curve · credit spread · VIX).

## North star

> **Find signals where the event hasn't yet played out and still has leading power.**

Every feature must pass one test: *"Does this help the user discover it N days/weeks before the
market?"* A signal that only fires after a sector has already rallied — however accurate — is
**not** what this is for. (Price is the sole exception: a deliberate safety net for what the
leading sensors missed.)

## Architecture

```
 news   data   price (safety net)   policy   roadmap   +  crash-watch   ← MCP sensor tools
   \      \          |                 /        /              │  (yield curve · credit spread · VIX)
        (sensors do anomaly detection only — no semantics)
                              │
       Scout (Claude Haiku) — flags anomalies, high false-positive tolerance
                              │
       Reviewer (Claude Sonnet) — 族群識別 → causal tree (tier 1/2/3) →
                              historical RAG → grade: 強訊號 / 觀察 / 駁回
                              │
       Daily 中文 report — graded themes + a 今日大盤風險 (crash-watch) banner
```

## Install

### A. From the Claude Code marketplace (recommended)

```text
/plugin marketplace add jaylooloomi/market-scan
/plugin install market-scan@market-scan
/reload-plugins
```

This installs the skill, the `/dig` command, the Scout/Reviewer agents, and the MCP sensor servers.

**Prerequisite — `uv`:** the sensors run as Python MCP servers via `uvx`, so you need
[`uv`](https://docs.astral.sh/uv/) on your PATH (one self-contained binary). On first launch
`uvx` builds Market Scan + deps into a cached env — **no manual `pip`, no PyPI account needed**.

- **No `uv`?** After installing, run **`/polydig-setup`** — it checks for `uv`, installs it
  (with your OK) and pre-warms the sensors. Or install manually:
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - then **restart Claude Code** (MCP servers read `PATH` at startup).
- **FinMind token optional:** FRED / TWSE / RSS / **crash-watch** work with zero config; only the
  FinMind-backed tools (法人進出 · 報價 · 量能) need a token.

### B. Local / development

```bash
pip install -e ".[schedule,dev]"   # core + apscheduler + pytest
pip install -e ".[agents]"         # + anthropic + chromadb (vector RAG, LLM reviewer)
```

Create `.env` (gitignored) for the FinMind token (free, 600 req/hr — register at finmindtrade.com):

```
FINMIND_TOKEN=your_token_here
```

## Use it

**Natural language (plugin):**
> 「今天有什麼?」 · 「幫我研究 矽光子」 · 「看一下大盤崩盤風險」 · `/dig today` · `/dig research <theme>`

**Headless (cron / CI):**
```bash
polydig-daily --mode dry            # heuristic reviewer, offline-friendly demo
polydig-daily --mode llm            # LLM reviewer (needs ANTHROPIC_API_KEY)
polydig-daily --persist ./vector_db # enable Chroma vector RAG
# → writes reports/YYYY-MM-DD.md (with a 今日大盤風險 banner)
```

## Sensors

| Sensor | What it watches | Backend |
|---|---|---|
| **news** | headline-volume anomalies · Google Trends spikes | RSS · pytrends |
| **data** | 法人進出 · 原物料/航運/SCFI · 美股族群 · **crash-watch** | FinMind · FRED · East Money |
| **price** *(safety net)* | 漲停群聚 · 量能異常 · 報價 | FinMind · TWSE OpenAPI |
| **policy** | 政府政策/補助公告 | gov RSS |
| **roadmap** | 法說會/路線圖訊號 | text analysis |

All sensors return a uniform envelope `{timestamp, source, signal_type, content, raw_url, anomaly_score}`
and **fail gracefully** — a dead feed or missing token returns a structured error, never a crash.

## Validation

- **Phase 0 backtest** — `polydig-validator --config cases.json`: 15 historical test points,
  4/5 cases strong-leading → **GO** (concept proof).
- **Replay harness** (`reviewer/replay.py`) — real GDELT news replay for out-of-sample lead-time.
- **Net-alpha** (`polydig_validator/net_alpha.py`) — converts gross backtest returns into realistic
  net numbers (cost · limit-up · exit rules · theme-aware hold).

## Honest limitations

- **Live detection is the open bet:** Phase 0 proves leading signals *exist* on hindsight-selected
  tickers/dates; picking the right sector in real time, with no future info, is unproven. See
  `reports/audit/` for the architect + VC analysis.
- **No yfinance in the MCP servers** — it pulls in `curl_cffi`, which corrupts the MCP stdio
  transport; servers use requests-based sources. yfinance stays in the Phase 0 CLI only.
- **Some sources are best-effort:** SCFI/BDI via East Money + Google News RSS; DRAM spot, PTT/Dcard,
  some gov HTML, earnings transcripts remain honest stubs.
- **Crash-watch is a de-risk caution signal, not a crash predictor** — see `docs/research/`.

## Tech stack

Python 3.11+ · MCP (FastMCP) · Anthropic Claude SDK · FinMind / FRED / TWSE OpenAPI · Chroma · SQLite.
Distributed as a Claude Code plugin; sensors launched via `uvx`. (Internal Python package: `polydig`.)

## License

MIT — see [LICENSE](LICENSE).
