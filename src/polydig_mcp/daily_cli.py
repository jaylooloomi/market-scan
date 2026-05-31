"""`polydig-daily` — run one daily cycle headlessly and write a markdown report.

Used for OS cron / scheduled runs outside an interactive Claude Code session.
Inside Claude Code, the polydig-daily skill drives the same flow via subagents.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from polydig_mcp.history.store import ThemeStore
from polydig_mcp.reporting.generator import write_report
from polydig_mcp.reviewer.pipeline import run_daily


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="PolyDig daily research report")
    p.add_argument("--mode", choices=["dry", "llm"], default="dry",
                   help="dry = heuristic reviewer (offline); llm = Anthropic SDK (needs ANTHROPIC_API_KEY)")
    p.add_argument("--output", default="reports", help="output directory")
    p.add_argument("--persist", default=None, help="Chroma persist dir (enables vector RAG)")
    args = p.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    store = ThemeStore(persist_dir=args.persist)
    print(f"PolyDig daily run — RAG mode: {store.mode}, reviewer: {args.mode}", file=sys.stderr)

    result = run_daily(store=store, reviewer_mode=args.mode)
    path = write_report(result["report_md"], output_dir=args.output, report_date=date.today())

    print(f"candidates: {len(result['candidates'])}, verdicts: {len(result['verdicts'])}", file=sys.stderr)
    print(f"report written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
