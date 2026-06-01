"""Headless Reviewer runner.

Ties the history RAG to an LLM call. Two modes:
  - "llm": call the Anthropic SDK (needs ANTHROPIC_API_KEY) — for testing /
    cron use outside Claude Code.
  - "dry": no LLM; return the retrieved precedents + a heuristic grade so the
    pipeline is exercisable offline and in CI.

In the Claude Code plugin (Phase 3) the Reviewer runs as a subagent, so this
engine is mainly for headless/testing parity.
"""
from __future__ import annotations

import json
import os
from typing import Any

from polydig_mcp.history.store import ThemeStore
from polydig_mcp.reviewer.prompt import (
    REVIEWER_SYSTEM,
    build_reviewer_user_prompt,
)
from polydig_mcp.reviewer.schema import (
    CausalTree,
    HistoricalMatch,
    ReviewVerdict,
    SignalGrade,
    TreeMember,
)

REVIEWER_MODEL = "claude-sonnet-4-6"


def _extract_sources(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull source + clickable URL from the candidate's raw signals.

    News carries the article link directly (raw_url). FRED-backed signals
    (commodity/shipping/us_sector) get a constructed FRED series page; the
    limit-up cluster links the TWSE daily report. Honest: if there's no URL,
    we keep url=None so the report shows the source name, not a fake link.
    """
    out: list[dict[str, Any]] = []
    for sig in candidate.get("raw_signals", []):
        content = sig.get("content", {})
        src = sig.get("source", "?")
        stype = sig.get("signal_type", "?")
        # News anomalies carry up to 3 article links — surface them all.
        article_urls = content.get("article_urls") or []
        if article_urls:
            for u in article_urls:
                out.append({"source": src, "signal_type": stype, "url": u})
            continue
        url = sig.get("raw_url")
        if not url:
            fred = content.get("fred_series")
            if fred:
                url = f"https://fred.stlouisfed.org/series/{fred}"
            elif stype == "limit_up_cluster":
                url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        out.append({"source": src, "signal_type": stype, "url": url})
    return out


def _heuristic_verdict(candidate: dict[str, Any], matches: list[dict[str, Any]]) -> ReviewVerdict:
    """Offline grade: borrow the top precedent's tree + verdict. Honest stand-in
    for the LLM's causal reasoning — good enough to exercise the pipeline."""
    top = matches[0] if matches else None
    grade = SignalGrade.REJECT
    tree = CausalTree()
    hist: list[HistoricalMatch] = []
    reasoning = "dry-run: no LLM. "

    if top:
        sim = top["similarity"]
        ct = top.get("causal_tree", {})
        tree = CausalTree(
            tier_1=[TreeMember(**{**m, "role": m.get("role", "")}) for m in ct.get("tier_1", [])],
            tier_2=[TreeMember(**{**m, "role": m.get("role", "")}) for m in ct.get("tier_2", [])],
            tier_3=[TreeMember(**{**m, "role": m.get("role", "")}) for m in ct.get("tier_3", [])],
            tier_4=[TreeMember(**{**m, "role": m.get("role", "")}) for m in ct.get("tier_4", [])],
        )
        hist = [HistoricalMatch(top["id"], top["name"], sim, top.get("outcome") or "")]
        if sim >= 0.5:
            grade = SignalGrade(top["reviewer_verdict"]) if top["reviewer_verdict"] != "reject" else SignalGrade.WATCHLIST
            reasoning += f"strong precedent '{top['name']}' (sim={sim})."
        elif sim >= 0.2:
            grade = SignalGrade.WATCHLIST
            reasoning += f"weak precedent '{top['name']}' (sim={sim}) → watchlist."
        else:
            reasoning += "no meaningful precedent."

    return ReviewVerdict(
        theme=candidate.get("theme_hint", candidate.get("theme", "?")),
        trigger=candidate.get("trigger_summary", candidate.get("trigger", "?")),
        causal_tree=tree,
        historical_match=hist,
        signal_grade=grade,
        confidence=round(top["similarity"], 3) if top else 0.0,
        reasoning=reasoning,
        expected_lead_days=None,
        sources=_extract_sources(candidate),
    )


def review(candidate: dict[str, Any], store: ThemeStore, mode: str = "dry") -> dict[str, Any]:
    """Run the Reviewer over one candidate theme. Returns a verdict dict."""
    query_text = f"{candidate.get('theme_hint','')} {candidate.get('trigger_summary','')}"
    matches = [m.to_dict() for m in store.query(query_text, n_results=3)]

    if mode == "llm" and os.getenv("ANTHROPIC_API_KEY"):
        try:
            return _llm_review(candidate, matches)
        except Exception as e:  # noqa: BLE001
            # fall back to heuristic, but record that the LLM path failed
            v = _heuristic_verdict(candidate, matches)
            d = v.to_dict()
            d["reasoning"] = f"[LLM failed: {e}] " + d["reasoning"]
            return d

    return _heuristic_verdict(candidate, matches).to_dict()


def _llm_review(candidate: dict[str, Any], matches: list[dict[str, Any]]) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=REVIEWER_MODEL,
        max_tokens=2000,
        system=REVIEWER_SYSTEM,
        messages=[{"role": "user", "content": build_reviewer_user_prompt(candidate, matches)}],
    )
    text = msg.content[0].text
    # The model is asked to emit a single JSON object.
    start, end = text.find("{"), text.rfind("}")
    obj = json.loads(text[start : end + 1])
    _validate_verdict(obj)  # raises on schema violation -> review() falls back to heuristic
    return obj


def _validate_verdict(obj: Any) -> None:
    """Light schema check on the LLM's JSON output (dependency-free).

    Raises ValueError on violation; review()'s try/except then falls back to the
    heuristic verdict (with the error recorded in reasoning). Keeps a malformed or
    hallucinated LLM response from silently entering the report.
    """
    if not isinstance(obj, dict):
        raise ValueError("LLM output is not a JSON object")
    required = ("theme", "trigger", "causal_tree", "signal_grade", "confidence", "reasoning")
    missing = [k for k in required if k not in obj]
    if missing:
        raise ValueError(f"LLM verdict missing required keys: {missing}")
    if obj["signal_grade"] not in {g.value for g in SignalGrade}:
        raise ValueError(f"invalid signal_grade: {obj['signal_grade']!r}")
    conf = obj.get("confidence")
    if not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
        raise ValueError(f"confidence out of [0,1]: {conf!r}")
    if not isinstance(obj.get("causal_tree"), dict):
        raise ValueError("causal_tree must be an object")
