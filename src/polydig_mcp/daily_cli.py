"""`polydig-daily` — run one daily cycle headlessly and write a markdown report.

Used for OS cron / scheduled runs outside an interactive Claude Code session.
Inside Claude Code, the polydig-daily skill drives the same flow via subagents.

Flags:
    --demo      Offline demo mode — uses canned sample signals (no network, no token).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from polydig_mcp.history.store import ThemeStore
from polydig_mcp.reporting.generator import write_report
from polydig_mcp.reviewer.pipeline import run_daily


def demo_signals():
    """Canned sample signals derived from the Phase 0 case-study themes.

    Covers three trigger types so the demo report contains multi-grade verdicts:
    - AI news_anomaly (→ watchlist/strong)
    - shipping data anomaly (→ watchlist/strong)
    - price limit-up cluster / safety-net (→ always becomes a candidate)
    """
    return [
        # AI first wave — news anomaly
        {
            "source": "news.anomaly",
            "signal_type": "news_anomaly",
            "content": {
                "term": "AI伺服器",
                "keywords": ["ChatGPT", "NVIDIA", "AI伺服器", "人工智慧", "算力"],
                "recent_count": 12,
                "prior_count": 1,
                "note": "Demo: AI news surge (Phase 0 case ai_first_wave_2023)",
            },
            "anomaly_score": 0.90,
            "timestamp": "2023-01-01T06:00:00+00:00",
        },
        # Shipping data anomaly
        {
            "source": "data.shipping",
            "signal_type": "shipping_index",
            "content": {
                "proxy_for": "BDI",
                "pct_change": 0.48,
                "note": "Demo: 運價 貨櫃 航運三雄 SCFI BDI surge (Phase 0 case shipping_2020)",
            },
            "anomaly_score": 0.82,
            "timestamp": "2020-06-15T06:00:00+00:00",
        },
        # Silicon photonics roadmap
        {
            "source": "roadmap.event",
            "signal_type": "roadmap_announcement",
            "content": {
                "keyword": "矽光子",
                "event": "Demo: NVIDIA GTC CPO 路線圖 矽光子 CPO TSMC量產 光模組",
                "source_url": None,
            },
            "anomaly_score": 0.76,
            "timestamp": "2023-03-21T06:00:00+00:00",
        },
        # Price safety-net cluster
        {
            "source": "price.cluster",
            "signal_type": "limit_up_cluster",
            "content": {
                "total_limit_up": 15,
                "clusters": {
                    "半導體": [
                        {"code": "3661", "name": "世芯-KY"},
                        {"code": "2330", "name": "台積電"},
                        {"code": "3443", "name": "創意"},
                    ]
                },
            },
            "anomaly_score": 0.70,
            "timestamp": "2023-01-01T06:00:00+00:00",
        },
    ]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="PolyDig daily research report")
    p.add_argument("--mode", choices=["dry", "llm"], default="dry",
                   help="dry = heuristic reviewer (offline); llm = Anthropic SDK (needs ANTHROPIC_API_KEY)")
    p.add_argument("--output", default="reports", help="output directory")
    p.add_argument("--persist", default=None, help="Chroma persist dir (enables vector RAG)")
    p.add_argument("--demo", action="store_true",
                   help="Offline demo: uses canned signals — no network, no FinMind token needed")
    p.add_argument("--db", default=None, help="SQLite db path (enables signal/verdict persistence)")
    args = p.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    store = ThemeStore(persist_dir=args.persist)
    provider = demo_signals if args.demo else None

    mode_label = "DEMO (canned signals)" if args.demo else f"live, reviewer={args.mode}"
    print(f"PolyDig daily run — RAG mode: {store.mode}, {mode_label}", file=sys.stderr)

    result = run_daily(
        store=store,
        reviewer_mode=args.mode,
        signal_provider=provider,
        db_path=args.db,
    )
    path = write_report(result["report_md"], output_dir=args.output, report_date=date.today())

    # Delivery: also write a stable reports/latest.md so a scheduled routine
    # always has one predictable path to surface, regardless of date.
    from pathlib import Path
    latest = Path(args.output) / "latest.md"
    latest.write_text(result["report_md"], encoding="utf-8")

    print(f"candidates: {len(result['candidates'])}, verdicts: {len(result['verdicts'])}", file=sys.stderr)
    print(f"report written: {path}")
    print(f"latest: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
