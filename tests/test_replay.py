"""Replay harness test (offline) — regression for the GDELT 2019 COVID finding.

Uses the committed real GDELT 'Wuhan pneumonia' daily volume to assert:
 (1) with an absolute-volume floor, the first fire is the GENUINE late-Dec outbreak
     (not the November noise), with a real ~3-week lead vs mainstream (1/20);
 (2) the absolute floor reduces false fires vs no-floor (the 2019-11 lesson).
pytest-collectable; no network.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from polydig_mcp.reviewer.replay import replay_series

_DATA = Path(__file__).resolve().parents[1] / "reports" / "audit" / "gdelt-wuhan-2019.json"


def _load() -> list[tuple[date, float]]:
    raw = json.loads(_DATA.read_text(encoding="utf-8"))
    return [(date.fromisoformat(d), float(c)) for d, c in raw]


def test_replay_fires_on_genuine_outbreak_not_november_noise() -> None:
    series = _load()
    _points, fire = replay_series(series, abs_floor=30)
    assert fire is not None
    # genuine outbreak window (China notified WHO 2019-12-31), NOT November noise
    assert date(2019, 12, 20) <= fire <= date(2020, 1, 5)
    assert fire.month == 12
    # real, out-of-sample lead vs mainstream (1/20 human-to-human)
    assert (date(2020, 1, 20) - fire).days >= 14


def test_absolute_floor_reduces_false_fires() -> None:
    series = _load()
    pts_floor, fire_floor = replay_series(series, abs_floor=30)
    pts_none, fire_none = replay_series(series, abs_floor=0)
    n_floor = sum(p.fire for p in pts_floor)
    n_none = sum(p.fire for p in pts_none)
    assert fire_none is not None and fire_floor is not None
    assert n_none >= n_floor          # no floor is strictly more permissive
    assert fire_none <= fire_floor    # and never fires later than with the floor
