"""Reviewer output contract — the causal propagation tree + verdict.

Mirrors the design spec §6.3. The Reviewer is a causal-reasoning engine: it
MUST output a tree (tier 1/2/3+), each branch carrying 台股 tickers + expected
lag, plus historical matches and a graded verdict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalGrade(str, Enum):
    STRONG = "strong"        # 強訊號 — 強歷史對應 + 強邏輯 → 列入今日報告
    WATCHLIST = "watchlist"  # 觀察清單 — 歷史弱但邏輯成立(新型題材)
    REJECT = "reject"        # 駁回(記錄理由作為負樣本)


@dataclass
class TreeMember:
    ticker: str
    name: str
    lag_days: int | None
    role: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"ticker": self.ticker, "name": self.name, "lag_days": self.lag_days, "role": self.role}


@dataclass
class CausalTree:
    tier_1: list[TreeMember] = field(default_factory=list)
    tier_2: list[TreeMember] = field(default_factory=list)
    tier_3: list[TreeMember] = field(default_factory=list)
    tier_4: list[TreeMember] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            k: [m.to_dict() for m in v]
            for k, v in {
                "tier_1": self.tier_1,
                "tier_2": self.tier_2,
                "tier_3": self.tier_3,
                "tier_4": self.tier_4,
            }.items()
            if v
        }


@dataclass
class HistoricalMatch:
    theme_id: str
    event: str
    similarity: float
    outcome: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme_id": self.theme_id,
            "event": self.event,
            "similarity": self.similarity,
            "outcome": self.outcome,
        }


@dataclass
class ReviewVerdict:
    theme: str
    trigger: str
    causal_tree: CausalTree
    historical_match: list[HistoricalMatch]
    signal_grade: SignalGrade
    confidence: float
    reasoning: str
    expected_lead_days: int | None = None  # 預期領先市場的天數

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "trigger": self.trigger,
            "causal_tree": self.causal_tree.to_dict(),
            "historical_match": [h.to_dict() for h in self.historical_match],
            "signal_grade": self.signal_grade.value,
            "confidence": self.confidence,
            "expected_lead_days": self.expected_lead_days,
            "reasoning": self.reasoning,
        }


# JSON schema the LLM is asked to fill (kept in sync with the dataclasses above).
REVIEW_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["theme", "trigger", "causal_tree", "historical_match", "signal_grade", "confidence", "reasoning"],
    "properties": {
        "theme": {"type": "string"},
        "trigger": {"type": "string"},
        "causal_tree": {
            "type": "object",
            "properties": {
                tier: {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["ticker", "name", "lag_days"],
                        "properties": {
                            "ticker": {"type": "string"},
                            "name": {"type": "string"},
                            "lag_days": {"type": ["integer", "null"]},
                            "role": {"type": "string"},
                        },
                    },
                }
                for tier in ("tier_1", "tier_2", "tier_3", "tier_4")
            },
        },
        "historical_match": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme_id": {"type": "string"},
                    "event": {"type": "string"},
                    "similarity": {"type": "number"},
                    "outcome": {"type": "string"},
                },
            },
        },
        "signal_grade": {"enum": ["strong", "watchlist", "reject"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "expected_lead_days": {"type": ["integer", "null"]},
        "reasoning": {"type": "string"},
    },
}
