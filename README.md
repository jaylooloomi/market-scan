# PolyDig

> Leading-edge theme detection for the Taiwan stock market — catch emerging themes **before** the market reacts.

![Phase 0](https://img.shields.io/badge/Phase%200-%E2%9C%85%20GO-brightgreen)
![Phases 1-4](https://img.shields.io/badge/Phases%201--4-built-blue)
![License](https://img.shields.io/badge/license-MIT-green)

PolyDig is a **research assistant** (not an auto-trader) that scans five signal sources,
reasons out a causal propagation tree of beneficiary Taiwan stocks, retrieves historical
analogues, and produces a daily Chinese-language research report — surfacing themes while
the event is still early.

繁體中文說明見 [`docs/zh-tw.md`](docs/zh-tw.md)。

## North star

> **Find signals where the event hasn't yet played out and still has leading power.**

Every feature must pass one test: *"Does this help the user discover it N days/weeks before
the market?"* A signal that only fires after a sector has already rallied — however accurate —
is **not** what this system is for. (Price is the sole exception: a deliberate safety net for
catching what the leading sensors missed.)

## Architecture

```
 news-mcp   data-mcp   price-mcp(safety net)   policy-mcp   roadmap-mcp     ← 5 MCP sensor servers
      \         \            |                   /            /
            (MCP tool calls — sensors do anomaly detection only, no semantics)
                                  │
                  Scout agent (Claude Haiku) — flags anomalies, high false-positive tolerance
                                  │
                  Reviewer agent (Claude Sonnet) — 族群識別 → causal tree (tier 1/2/3) →
                                  historical RAG (Chroma) → grade: strong / watchlist / reject
                                  │
                  Daily markdown report (中文)  ·  shown inline in Claude Code
```

## Install

### A. From the Claude Code marketplace (for users — recommended)

```text
/plugin marketplace add jaylooloomi/polydig
/plugin install polydig@polydig
/reload-plugins
```

Installs the `polydig-daily` skill, the `/dig` command, the Scout/Reviewer agents,
and the 5 MCP sensor servers. **Requirement:** the sensors run as Python MCP servers
via `uvx`, so you need [`uv`](https://docs.astral.sh/uv/) on your PATH (one
self-contained binary). On first use, `uvx` builds PolyDig + deps into a cached
ephemeral env — **no manual `pip`, no PyPI account needed**.

- **No `uv`?** Easiest: after installing the plugin, run **`/polydig-setup`** — it
  checks for `uv`, installs it (with your OK), and pre-warms the sensors. Or install manually:
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - then **restart Claude Code** (MCP servers read `PATH` at startup, so a freshly-installed
    `uv` is only picked up after a restart).
  - Or skip `uv` entirely: use local dev (B) and point `.mcp.json` at `python -m polydig_mcp.<x>.server`.
- **FinMind token optional:** FRED / TWSE / RSS / **crash-watch** sensors work with
  zero config; only the FinMind-backed tools (法人進出/報價/量能) need a token.

### B. Local / development

```bash
pip install -e ".[schedule,dev]"   # core + apscheduler + pytest
pip install -e ".[agents]"         # + anthropic + chromadb (vector RAG, LLM reviewer)
```

Create `.env` (gitignored) for the FinMind token (free, 600 req/hr — register at finmindtrade.com):

```
FINMIND_TOKEN=your_token_here
```

Without a token the FinMind-backed tools return a graceful `missing_token` signal; the
RSS / FRED / TWSE / crash-watch sensors still work.

## Use it (two ways)

**A. As a Claude Code plugin** — natural language:
> 「今天有什麼?」 · 「幫我研究 矽光子」 · 「scan 一下台股」 · `/dig today` · `/dig research <theme>`

The `polydig-daily` skill orchestrates the `polydig-scout` and `polydig-reviewer` subagents,
which call the MCP servers registered in [`.mcp.json`](.mcp.json).

**B. Headless (cron / CI):**
```bash
polydig-daily --mode dry                  # heuristic reviewer, offline-friendly demo
polydig-daily --mode llm                  # LLM reviewer (needs ANTHROPIC_API_KEY)
polydig-daily --persist ./vector_db       # enable Chroma vector RAG
# → writes reports/YYYY-MM-DD.md
```

## Sensors

| Server | Tools | Backend | Status |
|---|---|---|---|
| **news-mcp** | `fetch_news`, `detect_news_anomaly`, `google_trends_check`, `fetch_ptt`(stub) | RSS + pytrends | ✅ |
| **data-mcp** | `get_finmind`, `get_institutional_flow`, `get_commodity_price`, `get_shipping_index`, `get_dram_price`(stub) | FinMind + FRED | ✅ / partial |
| **price-mcp** | `get_quote`, `detect_limit_up_cluster`, `volume_anomaly` | FinMind + TWSE OpenAPI | ✅ |
| **policy-mcp** | `list_policy_sources`, `fetch_policy_announcements` | gov RSS (feasibility-gated) | partial |
| **roadmap-mcp** | `list_tracked_companies`, `parse_earnings_call`, `fetch_corp_roadmap`(stub) | text analysis | partial |

All sensors return a uniform envelope `{timestamp, source, signal_type, content, raw_url, anomaly_score}`
and **fail gracefully** (dead feed / missing token → structured error, never a crash).

## Phase 0 validator (concept proof)

```bash
polydig-validator --config cases.json --output reports/$(date +%Y-%m-%d)_validator
```
15 historical test points → 6 STRONG / 5 WEAK / 3 TOO_LATE / 1 NULL, 4/5 cases STRONG → **GO**.
See [the GO report](docs/superpowers/specs/2026-05-31-phase-0-results.md).

## Honest limitations

- **Phase 0 scope**: proves leading signals *exist* given hindsight-selected tickers/dates. Live
  detection (identifying the beneficiary sector in real time, no future info) is the Phase 2 bet.
- **Reviewer LLM reasoning** runs through Claude (Claude Code subagent, or `--mode llm` with an API
  key). The headless `--mode dry` uses a heuristic stand-in — enough to exercise the pipeline, not
  a substitute for the LLM's causal reasoning.
- **No yfinance in the MCP servers**: yfinance pulls in `curl_cffi`, which corrupts the MCP stdio
  transport on Windows. Servers use requests-based sources (FinMind / FRED / TWSE). yfinance stays
  in the Phase 0 CLI validator only.
- **SCFI/BDI, DRAM spot, PTT/Dcard, gov HTML, earnings transcripts**: no free/stable feed — these are
  stubbed with honest TODOs (see each server's README).

## Tech stack

Python 3.11+ · MCP (`mcp` FastMCP) · Anthropic Claude SDK · FinMind / FRED / TWSE OpenAPI · Chroma (vector RAG) · SQLite.

## License

MIT — see [LICENSE](LICENSE).
