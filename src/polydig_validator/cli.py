"""CLI entry point for PolyDig Phase 0 Leading Edge Validator."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

from polydig_validator.classifier import Thresholds, Verdict, classify
from polydig_validator.data_fetcher import DataFetcher
from polydig_validator.excess_return import (
    average_window_returns,
    compute_window_returns,
)
from polydig_validator.report import (
    CaseResult,
    TickerResult,
    TriggerResult,
    ValidatorRun,
    _fmt_pct,
    write_outputs,
)


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_validator(config_path: Path, output_dir: Path) -> ValidatorRun:
    cfg = load_config(config_path)

    sl = cfg["thresholds"]["strong_leading"]
    wl = cfg["thresholds"]["weak_leading"]
    thresholds = Thresholds(
        strong_pre_max=sl["pre_max_excess"],
        strong_post30_min=sl["post30_min_excess"],
        strong_post90_min=sl.get("post90_min_excess", 0.50),
        strong_post180_min=sl.get("post180_min_excess", 0.80),
        weak_pre_max=wl["pre_max_excess"],
        weak_post30_min=wl["post30_min_excess"],
        weak_post90_min=wl.get("post90_min_excess", 0.20),
        weak_post180_min=wl.get("post180_min_excess", 0.15),
        too_late_pre=cfg["thresholds"]["too_late_pre_excess"],
        null_post180_max=cfg["thresholds"].get(
            "null_post180_max_excess",
            cfg["thresholds"].get("null_post90_excess", 0.10),
        ),
    )
    pre_days = cfg["windows"]["pre_days"]
    post_days = cfg["windows"]["post_days"]
    baseline_symbol = cfg["baseline"]["symbol"]

    fetcher = DataFetcher()
    run = ValidatorRun(
        run_date=date.today(),
        cases=[],
        config_path=str(config_path),
    )

    print(f"Loading {len(cfg['cases'])} cases…", file=sys.stderr)

    for case_cfg in cfg["cases"]:
        case_id = case_cfg["id"]
        print(f"\n=== Case: {case_id} ({case_cfg['name']}) ===", file=sys.stderr)

        triggers: list[TriggerResult] = []
        for trig in case_cfg["triggers"]:
            trig_date = _parse_date(trig["date"])
            print(f"  Trigger {trig['label']} @ {trig_date}", file=sys.stderr)

            # Fetch baseline once per trigger (with buffer)
            try:
                baseline = fetcher.fetch_window(
                    baseline_symbol, trig_date, pre_days, max(post_days)
                )
            except Exception as e:
                print(f"    ❌ baseline fetch failed: {e}", file=sys.stderr)
                run.errors.append(
                    f"{case_id}/{trig['label']}: baseline fetch failed: {e}"
                )
                continue

            per_ticker: list[TickerResult] = []
            for tk in case_cfg["tickers"]:
                try:
                    stock = fetcher.fetch_window(
                        tk["symbol"], trig_date, pre_days, max(post_days)
                    )
                except Exception as e:
                    print(f"    ⚠️ {tk['symbol']} fetch failed: {e}", file=sys.stderr)
                    run.errors.append(
                        f"{case_id}/{trig['label']}/{tk['symbol']}: fetch failed: {e}"
                    )
                    continue

                wr = compute_window_returns(
                    stock=stock,
                    baseline=baseline,
                    trigger_date=trig_date,
                    pre_days=pre_days,
                    post_days=post_days,
                )
                verdict = classify(wr, thresholds)
                per_ticker.append(
                    TickerResult(
                        symbol=tk["symbol"],
                        name=tk["name"],
                        window=wr,
                        verdict=verdict,
                    )
                )
                # _fmt_pct handles None correctly (the old `x and f"" or "N/A"`
                # idiom wrongly printed "N/A" when excess was exactly 0.0).
                print(
                    f"    {tk['symbol']} ({tk['name']}): "
                    f"pre={_fmt_pct(wr.pre_excess)} "
                    f"post30={_fmt_pct(wr.post_excess.get(30))} "
                    f"→ {verdict.value}",
                    file=sys.stderr,
                )

            if not per_ticker:
                run.errors.append(
                    f"{case_id}/{trig['label']}: no per-ticker results"
                )
                continue

            # Aggregate across tickers
            agg_window = average_window_returns([t.window for t in per_ticker])
            agg_verdict = classify(agg_window, thresholds)

            triggers.append(
                TriggerResult(
                    label=trig["label"],
                    date=trig_date,
                    description=trig["description"],
                    per_ticker=per_ticker,
                    aggregate_window=agg_window,
                    aggregate_verdict=agg_verdict,
                )
            )
            print(
                f"  → aggregate verdict: {agg_verdict.value}", file=sys.stderr
            )

        run.cases.append(
            CaseResult(
                case_id=case_id,
                case_name=case_cfg["name"],
                trigger_type=case_cfg["trigger_type"],
                triggers=triggers,
            )
        )

    print("\n=== Writing outputs ===", file=sys.stderr)
    out = write_outputs(run, output_dir)
    print(f"  summary.md  → {out['summary_md']}", file=sys.stderr)
    print(f"  summary.json → {out['summary_json']}", file=sys.stderr)
    for p in out["case_md"]:
        print(f"  {p.name} → {p}", file=sys.stderr)

    return run


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="PolyDig Phase 0 — Leading Edge Validator")
    p.add_argument(
        "--config",
        type=Path,
        default=Path("cases.json"),
        help="Path to cases.json config (default: ./cases.json)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: reports/YYYY-MM-DD_validator/)",
    )
    args = p.parse_args(argv)

    if args.output is None:
        today = date.today().isoformat()
        args.output = Path("reports") / f"{today}_validator"

    # Reconfigure stdout to UTF-8 so unicode/emoji prints don't crash on cp950 (Windows)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    run = run_validator(args.config, args.output)

    # Concise stdout summary
    n_cases = len(run.cases)
    n_triggers = sum(len(c.triggers) for c in run.cases)
    strong = sum(
        1
        for c in run.cases
        for t in c.triggers
        if t.aggregate_verdict == Verdict.STRONG
    )
    weak = sum(
        1
        for c in run.cases
        for t in c.triggers
        if t.aggregate_verdict == Verdict.WEAK
    )
    print(f"\nCompleted: {n_cases} cases, {n_triggers} triggers, {strong} STRONG, {weak} WEAK")
    print(f"  Summary: {args.output / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
