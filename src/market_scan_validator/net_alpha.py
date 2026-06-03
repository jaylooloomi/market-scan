"""Net-alpha haircut — turn Phase 0's GROSS hindsight returns into realistic NET ones.

Answers the finance review's P0: "+310% is gross, T-1-close entry, no costs, no exit
— what is the *net, fillable* number?" Three scenarios per ticker:

  A. Gross (validator-style): enter T-1 close, hold to T+180. (the headline number)
  B. Worst-case net: enter ~2 trading days AFTER the trigger (small/mid-caps open
     limit-up the first 1-2 days, so a T-1 fill is fiction) + round-trip cost.
  C. + exit rule: from the same realistic entry, exit on a -20% stop or a 30-bar
     time-stop, whichever first, net of cost.

The pure functions (`round_trip_net`, `exit_with_rules`) are unit-tested offline.
The yfinance-backed `net_alpha_report` is for manual/analyst use (network; not CI).

NOTE (honest): close-based stop (not intraday), raw returns (beta NOT removed — that
is a *further* haircut, see reports/optimization/03-financial-analyst-value.md §1).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# ~0.1425% 手續費 ×2 (買賣) + 0.3% 證交稅 (賣) + 滑價估計 ≈ 0.5% round-trip
ROUND_TRIP_COST = 0.005


def round_trip_net(gross_return: float, cost: float = ROUND_TRIP_COST) -> float:
    """Net return after paying `cost` on the round trip (entry + exit)."""
    return (1.0 + gross_return) * (1.0 - cost) - 1.0


def exit_with_rules(
    closes: list[float],
    entry_idx: int,
    *,
    stop_loss: float | None = -0.20,
    time_stop: int = 30,
    take_profit: float | None = None,
) -> tuple[int, float]:
    """Walk forward from entry_idx; exit (close-based) on stop_loss / take_profit
    measured vs the entry price, else after `time_stop` bars, else at series end.

    Returns (exit_idx, gross_return). A real strategy needs this — Phase 0 has no
    exit at all, so its "+180-day" numbers are paper gains through deep drawdowns.
    """
    if entry_idx >= len(closes) - 1:
        return entry_idx, 0.0
    entry = closes[entry_idx]
    last = min(entry_idx + time_stop, len(closes) - 1)
    for j in range(entry_idx + 1, last + 1):
        r = closes[j] / entry - 1.0
        if stop_loss is not None and r <= stop_loss:
            return j, r
        if take_profit is not None and r >= take_profit:
            return j, r
    return last, closes[last] / entry - 1.0


@dataclass
class TickerNet:
    symbol: str
    name: str
    gross_A: float | None          # T-1 entry → T+180 (validator headline)
    net_B: float | None            # T+2 entry → T+180, net of cost
    net_C: float | None            # T+2 entry → exit rule, net of cost
    exit_C_days: int | None        # trading bars held under the exit rule


def _idx_on_or_before(dates, target):
    out = None
    for i, d in enumerate(dates):
        if d <= target:
            out = i
        else:
            break
    return out


def _idx_on_or_after(dates, target):
    for i, d in enumerate(dates):
        if d >= target:
            return i
    return None


def compute_ticker_net(
    dates: list[date],
    closes: list[float],
    trigger: date,
    *,
    fill_lag_trading_days: int = 2,
    horizon_days: int = 180,
    cost: float = ROUND_TRIP_COST,
    stop_loss: float = -0.20,
    time_stop: int = 30,
) -> TickerNet | None:
    """Pure computation of the three scenarios from a daily close series."""
    i_tm1 = _idx_on_or_before(dates, trigger - timedelta(days=1))
    i_trig = _idx_on_or_after(dates, trigger)
    if i_tm1 is None or i_trig is None:
        return None
    i_entry = min(i_trig + fill_lag_trading_days, len(dates) - 1)  # realistic fill
    i_exit = _idx_on_or_before(dates, trigger + timedelta(days=horizon_days))
    if i_exit is None or i_exit <= i_entry:
        i_exit = len(dates) - 1

    gross_A = closes[i_exit] / closes[i_tm1] - 1.0
    gross_B = closes[i_exit] / closes[i_entry] - 1.0
    net_B = round_trip_net(gross_B, cost)
    ex_idx, gross_C = exit_with_rules(closes, i_entry, stop_loss=stop_loss, time_stop=time_stop)
    net_C = round_trip_net(gross_C, cost)
    return TickerNet(
        symbol="", name="", gross_A=gross_A, net_B=net_B, net_C=net_C,
        exit_C_days=ex_idx - i_entry,
    )


def compute_case_ticker(
    dates: list[date],
    closes: list[float],
    trigger: date,
    *,
    horizons: tuple[int, ...] = (30, 90, 180),
    fill_lag_trading_days: int = 2,
    cost: float = ROUND_TRIP_COST,
    stop_loss: float = -0.20,
) -> dict[str, Any] | None:
    """Pure: gross(A, T-1 entry) + net-full(B, T+2 entry) + net-with-exit at each
    horizon (C@H = T+2 entry, -20% stop or N-day exit, net of cost).

    Reporting C at 30/90/180 lets the reader SEE exit-horizon sensitivity (the fix
    for 'fixed 30d is too short for slow themes') without parsing free-text hold_period.
    """
    i_tm1 = _idx_on_or_before(dates, trigger - timedelta(days=1))
    i_trig = _idx_on_or_after(dates, trigger)
    if i_tm1 is None or i_trig is None:
        return None
    i_entry = min(i_trig + fill_lag_trading_days, len(dates) - 1)
    i_long = _idx_on_or_before(dates, trigger + timedelta(days=max(horizons)))
    if i_long is None or i_long <= i_entry:
        return None
    gross_A = closes[i_long] / closes[i_tm1] - 1.0
    net_B = round_trip_net(closes[i_long] / closes[i_entry] - 1.0, cost)
    net_C: dict[int, float | None] = {}
    for H in horizons:
        i_cap = _idx_on_or_before(dates, trigger + timedelta(days=H))
        if i_cap is None or i_cap <= i_entry:
            net_C[H] = None
            continue
        _, g = exit_with_rules(closes, i_entry, stop_loss=stop_loss, time_stop=i_cap - i_entry)
        net_C[H] = round_trip_net(g, cost)
    return {"gross_A": gross_A, "net_B": net_B, "net_C": net_C}


_HOLD_UNIT_DAYS = {"年": 365, "月": 30, "週": 7, "周": 7, "日": 1, "天": 1}


def parse_hold_period(text: str) -> tuple[int, int] | None:
    """Parse free-text hold_period ('1-3 個月' / '6-12 個月' / '1-2 年(...)') into
    (lo_days, hi_days). Returns None if no number+unit found. Uses the FIRST numeric
    range/number and the FIRST unit character present."""
    import re

    if not text:
        return None
    unit = next((d for ch, d in _HOLD_UNIT_DAYS.items() if ch in text), None)
    if unit is None:
        return None
    m = re.search(r"(\d+)\s*[-~–]\s*(\d+)", text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
    else:
        m1 = re.search(r"(\d+)", text)
        if not m1:
            return None
        lo = hi = int(m1.group(1))
    return lo * unit, hi * unit


def theme_aware_net(
    dates: list[date],
    closes: list[float],
    trigger: date,
    hold_hi_days: int,
    *,
    fill_lag_trading_days: int = 2,
    cost: float = ROUND_TRIP_COST,
    stop_loss: float = -0.20,
) -> dict[str, Any] | None:
    """Net return when holding for the theme's OWN hold_period upper bound, exiting
    early on a -20% stop. `capped=True` if hold_hi extends past the price data."""
    i_trig = _idx_on_or_after(dates, trigger)
    if i_trig is None:
        return None
    i_entry = min(i_trig + fill_lag_trading_days, len(dates) - 1)
    target = trigger + timedelta(days=hold_hi_days)
    i_hold = _idx_on_or_before(dates, target)
    capped = (i_hold is None) or (dates[-1] < target)
    if i_hold is None or i_hold <= i_entry:
        i_hold = len(dates) - 1
    if i_hold <= i_entry:
        return None
    _, g = exit_with_rules(closes, i_entry, stop_loss=stop_loss, time_stop=i_hold - i_entry)
    return {"net": round_trip_net(g, cost), "hold_days": hold_hi_days, "capped": capped}


# cases.json case id -> themes.json theme id (for hold_period lookup)
_CASE_TO_THEME = {
    "mask": "mask_2020",
    "shipping": "shipping_2020",
    "ai": "ai_first_wave_2023",
    "defense": "defense_2022",
    "silicon_photonics": "silicon_photonics_2024",
}


# ── yfinance-backed report (manual/analyst use; needs network) ───────────────
MASK_TRIO = [("9919.TW", "康那香"), ("1325.TW", "恆大"), ("6504.TW", "南六")]


def net_alpha_report(
    tickers=MASK_TRIO,
    trigger: date = date(2020, 1, 20),  # 鍾南山證實人傳人 (actionable mid trigger)
) -> str:
    """Fetch real prices and render the gross→net haircut table (Markdown)."""
    import warnings

    warnings.filterwarnings("ignore")
    from market_scan_validator.data_fetcher import DataFetcher

    f = DataFetcher()
    rows: list[TickerNet] = []
    for sym, name in tickers:
        try:
            s = f.fetch(sym, trigger - timedelta(days=20), trigger + timedelta(days=230))
            dates = [d.date() for d in s.df.index]
            closes = [float(c) for c in s.df["Close"].tolist()]
            r = compute_ticker_net(dates, closes, trigger)
        except Exception as e:  # noqa: BLE001
            r = None
        if r is None:
            continue
        r.symbol, r.name = sym, name
        rows.append(r)

    def pct(x):
        return f"{x*100:+.0f}%" if x is not None else "N/A"

    out = [
        f"# 口罩股 net-alpha 試算 — trigger {trigger.isoformat()} (人傳人)",
        "",
        "> A=毛報酬(T-1 收盤進場,持有 T+180,validator 口徑) · "
        "B=最保守 net(T+2 進場+0.5% 成本) · C=B+出場規則(-20% 停損 / 30 日 time-stop)。"
        "raw return,**未扣 beta**(再扣會更低)。",
        "",
        "| 股票 | A 毛報酬(headline) | B 最保守 net | C +出場規則 net | C 持有日 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(f"| {r.name}({r.symbol}) | {pct(r.gross_A)} | {pct(r.net_B)} | {pct(r.net_C)} | {r.exit_C_days} |")
    if rows:
        avg = lambda key: sum(getattr(r, key) for r in rows) / len(rows)
        out.append(f"| **平均** | **{pct(avg('gross_A'))}** | **{pct(avg('net_B'))}** | **{pct(avg('net_C'))}** | — |")
    out += ["", "→ A→B 的落差 = 漲停買不到 + 成本;B→C 的落差 = 出場規則的取捨(犧牲部分上檔換有界下檔)。"]
    return "\n".join(out)


def net_alpha_all_cases(
    config_path: str = "cases.json",
    trigger_label: str = "mid",
    themes_path: str | None = None,
) -> str:
    """Net-alpha haircut across ALL cases in cases.json (raw returns, no beta).

    Besides fixed 30/90/180-day exits, adds a **theme-aware** exit (C@hold): hold for
    the theme's own `hold_period` upper bound (from themes.json via parse_hold_period),
    exiting early on a -20% stop. `*` on the hold label = the hold window runs past
    available price data (capped). Per-ticker fetch failures skipped + listed. Network.
    """
    import json
    import warnings
    from datetime import datetime
    from pathlib import Path

    warnings.filterwarnings("ignore")
    from market_scan_validator.data_fetcher import DataFetcher

    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if themes_path is None:
        themes_path = Path(__file__).resolve().parents[1] / "market_scan_mcp" / "history" / "themes.json"
    try:
        themes = {t["id"]: t for t in json.loads(Path(themes_path).read_text(encoding="utf-8"))["themes"]}
    except Exception:  # noqa: BLE001
        themes = {}

    f = DataFetcher()
    fixed = (30, 90, 180)

    def pct(x: float | None) -> str:
        return f"{x * 100:+.0f}%" if x is not None else "N/A"

    def avg(xs: list[float]) -> float | None:
        return (sum(xs) / len(xs)) if xs else None

    out = [
        "# Net-alpha across all Phase 0 cases",
        "",
        f"> 每案用 **{trigger_label}** trigger 進場。A=毛(T-1→T+180) · B=最保守 net(T+2+0.5% 成本→T+180) · "
        "C@N=net(T+2、−20% 停損 / N 日出場) · **C@hold=依該題材 `hold_period` 出場**(本次新增)。"
        "raw return、未扣 beta;`*`=hold 視窗超出可得股價(截斷)。",
        "",
        "| 案例 | 訊號日 | A 毛 | B net | C@30 | C@90 | C@180 | C@hold(題材時間軸) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    overall: dict[Any, list[float]] = {"A": [], "B": [], 30: [], 90: [], 180: [], "hold": []}
    skipped: list[str] = []
    for case in cfg["cases"]:
        trig = next((t for t in case["triggers"] if t["label"] == trigger_label), case["triggers"][0])
        tdate = datetime.strptime(trig["date"], "%Y-%m-%d").date()
        theme = themes.get(_CASE_TO_THEME.get(case.get("id", ""), ""))
        hp = parse_hold_period(theme.get("hold_period", "")) if theme else None
        hold_hi = hp[1] if hp else 180
        fetch_to = max(230, hold_hi + 30)
        agg: dict[Any, list[float]] = {"A": [], "B": [], 30: [], 90: [], 180: [], "hold": []}
        capped = False
        for tk in case["tickers"]:
            try:
                s = f.fetch(tk["symbol"], tdate - timedelta(days=20), tdate + timedelta(days=fetch_to))
                dts = [d.date() for d in s.df.index]
                cl = [float(c) for c in s.df["Close"].tolist()]
                r = compute_case_ticker(dts, cl, tdate, horizons=fixed)
                th = theme_aware_net(dts, cl, tdate, hold_hi)
            except Exception:  # noqa: BLE001 — network/ticker flakiness, skip
                r = th = None
            if r is None:
                skipped.append(tk["symbol"])
                continue
            agg["A"].append(r["gross_A"])
            agg["B"].append(r["net_B"])
            for H in fixed:
                if r["net_C"][H] is not None:
                    agg[H].append(r["net_C"][H])
            if th is not None:
                agg["hold"].append(th["net"])
                capped = capped or th["capped"]
        if not agg["A"]:
            out.append(f"| {case['name']} | {trig['date']} | (fetch 失敗) |  |  |  |  |  |")
            continue
        row = {k: avg(agg[k]) for k in agg}
        for k, v in row.items():
            if v is not None:
                overall[k].append(v)
        hold_lbl = f"{pct(row['hold'])}（{hold_hi}天{'*' if capped else ''}）"
        out.append(
            f"| {case['name']} | {trig['date']} | {pct(row['A'])} | {pct(row['B'])} | "
            f"{pct(row[30])} | {pct(row[90])} | {pct(row[180])} | {hold_lbl} |"
        )
    out.append(
        f"| **平均** | — | **{pct(avg(overall['A']))}** | **{pct(avg(overall['B']))}** | "
        f"**{pct(avg(overall[30]))}** | **{pct(avg(overall[90]))}** | **{pct(avg(overall[180]))}** | "
        f"**{pct(avg(overall['hold']))}** |"
    )
    out += [
        "",
        "→ **C@hold = 依各題材自己的 `hold_period` 出場**(而非固定天數),是「合理出場」最接近的單一數字;"
        "對照 C@30(太死)與 C@180,可見配對題材時間軸的價值。`*` = 題材 hold 期超出可得股價、已截斷。",
    ]
    if skipped:
        out += ["", f"> ⚠️ 略過(fetch 失敗,多為 .TWO 上櫃股 yfinance 不穩):{', '.join(sorted(set(skipped)))}"]
    return "\n".join(out)


def main() -> int:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(net_alpha_all_cases())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
