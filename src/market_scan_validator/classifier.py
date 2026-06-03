"""Classify a WindowReturns into 強領先 / 弱領先 / 太晚 / 無效.

Design note (2026-05-31): v0.1 only checked post30, which wrongly classified slow-burn
themes (AI 2022/11 → +205% at T+180 but only +3% at T+30) as 無效. v0.2 checks ALL
post-windows (30/90/180) and passes a signal if ANY window beats the threshold.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from market_scan_validator.excess_return import WindowReturns


class Verdict(str, Enum):
    STRONG = "🟢 強領先"
    WEAK = "🟡 弱領先"
    TOO_LATE = "🔴 太晚"
    NULL = "⚫ 無效"
    UNKNOWN = "⚠️ 無法判定"


@dataclass
class Thresholds:
    # 強領先: 事前低 AND 任一事後窗口爆發
    strong_pre_max: float = 0.10
    strong_post30_min: float = 0.30
    strong_post90_min: float = 0.50
    strong_post180_min: float = 0.80

    # 弱領先: 事前可接受 AND 任一窗口有明顯漲幅
    weak_pre_max: float = 0.30
    weak_post30_min: float = 0.10
    weak_post90_min: float = 0.20
    weak_post180_min: float = 0.15

    # 太晚: 事前已經漲很多
    too_late_pre: float = 0.30

    # 無效: 事後 180 天還是平的（題材沒成立）
    null_post180_max: float = 0.10


def _any_above(values: list[float | None], threshold: float) -> bool:
    return any(v is not None and v > threshold for v in values)


def classify(wr: WindowReturns, t: Thresholds | None = None) -> Verdict:
    t = t or Thresholds()

    if wr.error is not None or wr.pre_excess is None:
        return Verdict.UNKNOWN

    pre = wr.pre_excess
    post30 = wr.post_excess.get(30)
    post90 = wr.post_excess.get(90)
    post180 = wr.post_excess.get(180)

    # 太晚 — 最高優先（即使事後也漲，但已經 too late 進場）
    if pre > t.too_late_pre:
        return Verdict.TOO_LATE

    # 強領先 — 事前低 AND 任一事後窗口顯著爆發
    if pre < t.strong_pre_max:
        strong_hits = [
            (post30, t.strong_post30_min),
            (post90, t.strong_post90_min),
            (post180, t.strong_post180_min),
        ]
        if any(v is not None and v > thr for v, thr in strong_hits):
            return Verdict.STRONG

    # 弱領先 — 事前可接受 AND 任一窗口有明顯漲幅
    if pre < t.weak_pre_max:
        weak_hits = [
            (post30, t.weak_post30_min),
            (post90, t.weak_post90_min),
            (post180, t.weak_post180_min),
        ]
        if any(v is not None and v > thr for v, thr in weak_hits):
            return Verdict.WEAK

    # 無效 — 事後 180 天都沒漲起來
    if post180 is not None and post180 < t.null_post180_max:
        return Verdict.NULL

    return Verdict.NULL  # 預設：沒打到 STRONG/WEAK 條件，視為 NULL
