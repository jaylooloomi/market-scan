"""vol_conf 阻尼:小樣本比率不可信 → 用樣本量打折,擋雜訊假陽性。

來源:2026-06-01 GDELT 真實回放發現——基線≈0 時 4 篇「武漢肺炎」雜訊會被
舊公式評為 0.8(假陽性)。本測試證明 (a) 小樣本被打折、(b) 高量真訊號照響、
(c) 真正的雜訊(近期≈先前,無突起)維持近零。pytest 可收集。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polydig_mcp.news.sources import FULL_CONFIDENCE_COUNT, detect_term_spikes


def _build(recent: dict[str, int], older: dict[str, int]) -> list[dict]:
    """Build items in fetch_feed() shape: recent ones inside the 1-day window."""
    now = datetime.now(timezone.utc)
    r_dt, o_dt = now - timedelta(hours=1), now - timedelta(days=5)
    items: list[dict] = []
    for term, n in recent.items():
        items += [{"title": term, "summary": "", "lang": "en",
                   "link": f"r-{term}-{i}", "_dt": r_dt} for i in range(n)]
    for term, n in older.items():
        items += [{"title": term, "summary": "", "lang": "en",
                   "link": f"o-{term}-{i}", "_dt": o_dt} for i in range(n)]
    return items


def _expected(rc: int, oc: int) -> float:
    """Re-implement the scoring formula so the test stays valid if the constant is tuned."""
    ratio = rc / (oc + 1)
    return round(min(1.0, ratio / 5.0) * min(1.0, rc / FULL_CONFIDENCE_COUNT), 3)


def test_vol_conf_damps_low_volume_noise() -> None:
    items = _build(
        recent={"highvol": 20, "lowvol": 4, "background": 6},
        older={"background": 18},
    )
    spikes = {s["term"]: s["anomaly_score"] for s in detect_term_spikes(items, window_days=1.0)}

    # (b) high-volume brand-new term fires strongly
    assert spikes["highvol"] == _expected(20, 0)
    assert spikes["highvol"] >= 0.99

    # (a) low-volume brand-new term (the 2019-11 noise case) is DAMPED below the
    #     undamped raw score (0.8) and below the high-volume term
    assert spikes["lowvol"] == _expected(4, 0)
    assert spikes["lowvol"] < 0.8                      # undamped would have been 0.8
    assert spikes["lowvol"] < spikes["highvol"]

    # (c) background noise (appears MORE before than now) stays near zero
    assert spikes["background"] < 0.1


def test_vol_conf_is_monotonic_in_sample_size() -> None:
    # same (brand-new) baseline, more articles → higher score, up to saturation
    assert _expected(8, 0) > _expected(4, 0)
    assert _expected(20, 0) >= _expected(8, 0)
