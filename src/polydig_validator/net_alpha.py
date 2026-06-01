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


# ── yfinance-backed report (manual/analyst use; needs network) ───────────────
MASK_TRIO = [("9919.TW", "康那香"), ("1325.TW", "恆大"), ("6504.TW", "南六")]


def net_alpha_report(
    tickers=MASK_TRIO,
    trigger: date = date(2020, 1, 20),  # 鍾南山證實人傳人 (actionable mid trigger)
) -> str:
    """Fetch real prices and render the gross→net haircut table (Markdown)."""
    import warnings

    warnings.filterwarnings("ignore")
    from polydig_validator.data_fetcher import DataFetcher

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


def main() -> int:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    md = net_alpha_report()
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
