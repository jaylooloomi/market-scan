# PolyDig Phase 0 — Implementation Plan

**Date**: 2026-05-31
**Parent spec**: [`docs/superpowers/specs/2026-05-31-polydig-design.md`](../specs/2026-05-31-polydig-design.md)
**Owner**: Autonomous build (Claude Haiku 4.5) on Arthur's instruction
**Status**: Building

## Goal
Implement and run the Leading Edge Validator on 15 test points (5 cases × 3 trigger dates each), produce a go/no-go decision report for the entire PolyDig concept.

## Build Steps

1. **Project scaffold** — `pyproject.toml`, `requirements.txt`, `src/polydig_validator/` package layout
2. **Config file** — `cases.json` with 5 cases × 3 triggers × representative tickers, plus thresholds and windows
3. **Data fetcher** — `data_fetcher.py` wraps yfinance, fetches OHLC for Taiwan stocks (.TW/.TWO) and TAIEX (^TWII), with trading-day alignment helpers
4. **Excess return calc** — `excess_return.py` computes per-stock returns relative to TAIEX baseline over T-90→T-1 (pre) and T-1→T+7/30/90/180 (post) windows. Handles holiday/missing-data fallbacks via nearest-trading-day search
5. **Classifier** — `classifier.py` applies thresholds (configurable via JSON) to produce a Verdict enum: 強領先 / 弱領先 / 太晚 / 無效 / 無法判定
6. **Report generator** — `report.py` renders Markdown summary + per-case detail + structured JSON. Computes go/no-go decision based on number of cases with ≥1 STRONG trigger
7. **CLI** — `cli.py` ties everything together; argparse with `--config` and `--output` flags
8. **Install + run** — `pip install yfinance` + execute on all 15 test points; expect ~30-60 sec runtime (network bound)
9. **Verify outputs** — read `summary.md`, sanity-check per-case results, look for fetch errors
10. **Commit + push** — all source + reports to GitHub

## Deviation from Spec
- Spec §7.5 says "FinMind 主 + yfinance 備援"; for Phase 0 I'm using **yfinance only** (no API key required, gets us running immediately). FinMind integration can be added in Phase 1 when we need detailed Taiwan-specific data (chip data, fund flows) that yfinance lacks. Daily OHLC is the only thing Phase 0 needs and yfinance has it.

## Go/No-Go Decision Logic
- ≥ 4 of 5 cases have ≥ 1 STRONG-rated trigger → **GO** (concept validated)
- ≥ 3 of 5 with at least leading (STRONG or WEAK) → **CONDITIONAL** (partial)
- Otherwise → **NO-GO** (rethink before Phase 1)
