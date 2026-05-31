"""Generate Markdown + JSON output from validator runs."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from polydig_validator.classifier import Verdict
from polydig_validator.excess_return import WindowReturns


@dataclass
class TickerResult:
    symbol: str
    name: str
    window: WindowReturns
    verdict: Verdict


@dataclass
class TriggerResult:
    label: str  # "early" | "mid" | "late"
    date: date
    description: str
    per_ticker: list[TickerResult]
    aggregate_window: WindowReturns
    aggregate_verdict: Verdict


@dataclass
class CaseResult:
    case_id: str
    case_name: str
    trigger_type: str
    triggers: list[TriggerResult]


@dataclass
class ValidatorRun:
    run_date: date
    cases: list[CaseResult]
    config_path: str
    errors: list[str] = field(default_factory=list)


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:+.1f}%"


def _per_ticker_md(tr: list[TickerResult]) -> str:
    lines = ["| Ticker | 名稱 | 事前 (T-90→T-1, excess) | 事後 30D | 事後 90D | 事後 180D | 判定 |",
             "|---|---|---|---|---|---|---|"]
    for t in tr:
        w = t.window
        lines.append(
            f"| {t.symbol} | {t.name} | {_fmt_pct(w.pre_excess)} | "
            f"{_fmt_pct(w.post_excess.get(30))} | "
            f"{_fmt_pct(w.post_excess.get(90))} | "
            f"{_fmt_pct(w.post_excess.get(180))} | {t.verdict.value} |"
        )
    return "\n".join(lines)


def _trigger_section_md(tr: TriggerResult) -> str:
    agg = tr.aggregate_window
    md = [
        f"#### {tr.label} — {tr.date.isoformat()}",
        f"> {tr.description}",
        "",
        f"**族群平均判定**: **{tr.aggregate_verdict.value}**",
        "",
        f"- 事前 (T-90→T-1, excess vs TAIEX): **{_fmt_pct(agg.pre_excess)}**",
        f"- 事後 7 天: {_fmt_pct(agg.post_excess.get(7))}",
        f"- 事後 30 天: **{_fmt_pct(agg.post_excess.get(30))}**",
        f"- 事後 90 天: {_fmt_pct(agg.post_excess.get(90))}",
        f"- 事後 180 天: {_fmt_pct(agg.post_excess.get(180))}",
        "",
        "**個股明細：**",
        "",
        _per_ticker_md(tr.per_ticker),
        "",
    ]
    return "\n".join(md)


def _case_section_md(case: CaseResult) -> str:
    md = [
        f"## {case.case_name} (`{case.case_id}`)",
        f"**訊號類型**: {case.trigger_type}",
        "",
    ]
    for tr in case.triggers:
        md.append(_trigger_section_md(tr))
    return "\n".join(md)


def render_case_markdown(case: CaseResult) -> str:
    return _case_section_md(case)


def render_summary_markdown(run: ValidatorRun) -> str:
    # Tally verdicts at trigger level
    all_verdicts = [
        tr.aggregate_verdict
        for case in run.cases
        for tr in case.triggers
    ]
    tally = Counter(v.value for v in all_verdicts)

    strong_count = tally.get(Verdict.STRONG.value, 0)
    weak_count = tally.get(Verdict.WEAK.value, 0)
    total = len(all_verdicts)
    leading_count = strong_count + weak_count

    # Go/no-go: ≥4 of the 5 cases need at least one trigger as STRONG
    cases_with_strong: list[str] = []
    cases_with_leading: list[str] = []
    for case in run.cases:
        verdicts = [tr.aggregate_verdict for tr in case.triggers]
        if Verdict.STRONG in verdicts:
            cases_with_strong.append(case.case_id)
        if Verdict.STRONG in verdicts or Verdict.WEAK in verdicts:
            cases_with_leading.append(case.case_id)

    decision = (
        "✅ **GO** — concept validated, proceed to Phase 1"
        if len(cases_with_strong) >= 4
        else (
            "⚠️ **CONDITIONAL** — partial validation, review per-case findings"
            if len(cases_with_leading) >= 3
            else "❌ **NO-GO** — root assumption appears unsupported, rethink before Phase 1"
        )
    )

    md = [
        "# PolyDig Phase 0 — Leading Edge Validator Summary",
        "",
        f"**Run date**: {run.run_date.isoformat()}",
        f"**Config**: `{run.config_path}`",
        f"**Cases**: {len(run.cases)} themes × 3 triggers = **{total} test points**",
        "",
        "## Go/No-Go Decision",
        "",
        f"### {decision}",
        "",
        f"- Cases with at least one 🟢 STRONG trigger: **{len(cases_with_strong)}/5** ({', '.join(cases_with_strong) or 'none'})",
        f"- Cases with at least one leading (🟢 or 🟡) trigger: **{len(cases_with_leading)}/5** ({', '.join(cases_with_leading) or 'none'})",
        "",
        "## Verdict Distribution (15 trigger-level aggregates)",
        "",
        "| Verdict | Count | % |",
        "|---|---|---|",
        f"| 🟢 強領先 | {strong_count} | {strong_count*100//total if total else 0}% |",
        f"| 🟡 弱領先 | {weak_count} | {weak_count*100//total if total else 0}% |",
        f"| 🔴 太晚 | {tally.get(Verdict.TOO_LATE.value, 0)} | {tally.get(Verdict.TOO_LATE.value, 0)*100//total if total else 0}% |",
        f"| ⚫ 無效 | {tally.get(Verdict.NULL.value, 0)} | {tally.get(Verdict.NULL.value, 0)*100//total if total else 0}% |",
        f"| ⚠️ 無法判定 | {tally.get(Verdict.UNKNOWN.value, 0)} | {tally.get(Verdict.UNKNOWN.value, 0)*100//total if total else 0}% |",
        "",
        "## Per-Case Summary",
        "",
        "| Case | 訊號類型 | early | mid | late |",
        "|---|---|---|---|---|",
    ]
    for case in run.cases:
        verdicts_by_label = {tr.label: tr.aggregate_verdict.value for tr in case.triggers}
        md.append(
            f"| {case.case_name} | {case.trigger_type} | "
            f"{verdicts_by_label.get('early', 'N/A')} | "
            f"{verdicts_by_label.get('mid', 'N/A')} | "
            f"{verdicts_by_label.get('late', 'N/A')} |"
        )

    md += [
        "",
        "## Interpretation Guide",
        "",
        "- **強領先 (🟢)**：事前 < +10% excess AND **任一事後窗口爆發** (post30>+30% OR post90>+50% OR post180>+80%)",
        "- **弱領先 (🟡)**：事前 < +30% AND **任一事後窗口有明顯漲幅** (post30>+10% OR post90>+20% OR post180>+15%)",
        "- **太晚 (🔴)**：事前已 > +30% excess → 訊號出現時市場已先漲，進場太晚",
        "- **無效 (⚫)**：所有窗口都沒打到弱領先門檻，或事後 180 天 < +10% → 題材沒成立",
        "- 所有「事前/事後」都是**相對於 TAIEX 同期漲跌**的 excess return",
        "- **多窗口設計理由**：許多題材是慢熱型 (AI、矽光子)，T+30 還沒啟動但 T+180 大爆發。只看 T+30 會誤判系統價值。",
        "",
        "## Files in this run",
        "",
    ]
    for case in run.cases:
        md.append(f"- [{case.case_name}](./{case.case_id}.md) — full per-ticker breakdown")

    if run.errors:
        md += ["", "## Errors / Warnings", ""]
        for e in run.errors:
            md.append(f"- {e}")

    return "\n".join(md)


def _window_to_dict(w: WindowReturns) -> dict:
    return {
        "trigger_date": w.trigger_date.isoformat(),
        "pre_days": w.pre_days,
        "post_days": list(w.post_days),
        "anchor_t_minus_1": w.anchor_t_minus_1.isoformat() if w.anchor_t_minus_1 else None,
        "anchor_t_minus_pre": w.anchor_t_minus_pre.isoformat() if w.anchor_t_minus_pre else None,
        "anchor_t_plus_post": {
            str(k): (v.isoformat() if v else None)
            for k, v in w.anchor_t_plus_post.items()
        },
        "stock_pre_return": w.stock_pre_return,
        "baseline_pre_return": w.baseline_pre_return,
        "pre_excess": w.pre_excess,
        "stock_post_returns": {str(k): v for k, v in w.stock_post_returns.items()},
        "baseline_post_returns": {str(k): v for k, v in w.baseline_post_returns.items()},
        "post_excess": {str(k): v for k, v in w.post_excess.items()},
        "error": w.error,
    }


def render_json(run: ValidatorRun) -> dict:
    return {
        "run_date": run.run_date.isoformat(),
        "config_path": run.config_path,
        "cases": [
            {
                "id": case.case_id,
                "name": case.case_name,
                "trigger_type": case.trigger_type,
                "triggers": [
                    {
                        "label": tr.label,
                        "date": tr.date.isoformat(),
                        "description": tr.description,
                        "aggregate_verdict": tr.aggregate_verdict.value,
                        "aggregate_window": _window_to_dict(tr.aggregate_window),
                        "per_ticker": [
                            {
                                "symbol": t.symbol,
                                "name": t.name,
                                "verdict": t.verdict.value,
                                "window": _window_to_dict(t.window),
                            }
                            for t in tr.per_ticker
                        ],
                    }
                    for tr in case.triggers
                ],
            }
            for case in run.cases
        ],
        "errors": run.errors,
    }


def write_outputs(run: ValidatorRun, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    # summary
    summary_md = render_summary_markdown(run)
    summary_md_path = output_dir / "summary.md"
    summary_md_path.write_text(summary_md, encoding="utf-8")

    summary_json = render_json(run)
    summary_json_path = output_dir / "summary.json"
    summary_json_path.write_text(
        json.dumps(summary_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # per-case
    case_paths: list[Path] = []
    for case in run.cases:
        case_md = render_case_markdown(case)
        case_path = output_dir / f"{case.case_id}.md"
        case_path.write_text(case_md, encoding="utf-8")
        case_paths.append(case_path)

    return {
        "summary_md": summary_md_path,
        "summary_json": summary_json_path,
        "case_md": case_paths,
    }
