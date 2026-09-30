"""Offline pre-market scanner for the Pullback-Momentum universe.

Answers one question without touching IB Gateway: given saved daily bars,
which symbols are a setup on the latest completed bar, and what bracket
would the bot stage?

It imports `compute_indicators` and `evaluate_symbol` from the live modules
rather than reimplementing them, so the scanner can never drift away from
what the bot actually trades. A rule change in strategy.py shows up here
on the next run, for free.

Bars file: JSON, one entry per symbol, oldest bar first.

    {
      "TSLA": {
        "time":  ["2026-07-06", ...],
        "high":  [420.0, ...],
        "low":   [390.5, ...],
        "close": [419.77, ...]
      },
      ...
    }

`open` and `volume` are accepted and ignored. At least
regime_sma_period + 5 bars are required per symbol (same rule the live
bot applies via has_enough_history).

Usage:
    python scan.py --bars bars.json
    python scan.py --bars bars.json --nlv 17000        # size the signals
    python scan.py --bars bars.json --available 600    # apply a funding cap
    python scan.py --bars bars.json --json             # machine-readable
"""

import argparse
import json
import sys

import pandas as pd

from config import CONFIG
from data_fetcher import compute_indicators, has_enough_history
from strategy import affordable_size, evaluate_symbol, position_size

REQUIRED_COLUMNS = ("time", "high", "low", "close")


def load_frames(path: str) -> dict[str, pd.DataFrame]:
    """Read the bars file into one OHLC frame per symbol."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    frames: dict[str, pd.DataFrame] = {}
    for symbol, series in raw.items():
        missing = [c for c in REQUIRED_COLUMNS if c not in series]
        if missing:
            raise ValueError(f"{symbol}: bars file is missing {', '.join(missing)}")
        lengths = {len(series[c]) for c in REQUIRED_COLUMNS}
        if len(lengths) != 1:
            raise ValueError(f"{symbol}: time/high/low/close have differing lengths")

        df = pd.DataFrame(
            {
                "open": series.get("open", series["close"]),
                "high": series["high"],
                "low": series["low"],
                "close": series["close"],
                "volume": series.get("volume", [0] * len(series["close"])),
            },
            index=pd.to_datetime(series["time"]),
        ).sort_index()
        frames[symbol] = df
    return frames


def scan(frames: dict[str, pd.DataFrame], nlv: float | None,
         available: float | None) -> list[dict]:
    """Evaluate every symbol; one result row each, signal or not."""
    rows: list[dict] = []
    for symbol, df in sorted(frames.items()):
        if not has_enough_history(df):
            rows.append({
                "symbol": symbol,
                "skipped": f"only {len(df)} bars, need "
                           f"{CONFIG.strategy.regime_sma_period + 5}",
            })
            continue

        ind = compute_indicators(df)
        last = ind.iloc[-1]
        row = {
            "symbol": symbol,
            "setup_date": str(ind.index[-1].date()),
            "close": round(float(last["close"]), 2),
            "sma50": round(float(last["sma50"]), 2),
            "rsi2": round(float(last["rsi2"]), 1),
            "regime_ok": bool(last["close"] > last["sma50"]),
            "trigger_ok": bool(last["rsi2"] < CONFIG.strategy.rsi_oversold),
        }

        signal = evaluate_symbol(symbol, ind)
        row["signal"] = signal is not None
        if signal is not None:
            row.update({
                "entry_stop": signal.stop_price,
                "entry_limit": signal.limit_price,
                "stop_loss": round(signal.stop_price - signal.stop_loss_distance, 2),
                "take_profit": round(signal.sma10, 2),
                "risk_per_share": signal.stop_loss_distance,
                "reward_risk": signal.reward_risk,
            })
            if nlv:
                shares = position_size(nlv, signal.stop_loss_distance)
                if available is not None:
                    shares = affordable_size(shares, signal.limit_price, available)
                row["shares"] = shares
                row["notional"] = round(shares * signal.limit_price)
                row["risk_total"] = round(shares * signal.stop_loss_distance)
        rows.append(row)
    return rows


def render(rows: list[dict], nlv: float | None) -> None:
    header = (f"{'SYM':<6}{'close':>10}{'sma50':>10}{'RSI2':>7}"
              f"{'regime':>8}{'trigger':>9}{'SIGNAL':>9}")
    print(header)
    print("-" * len(header))
    for r in rows:
        if "skipped" in r:
            print(f"{r['symbol']:<6}  skipped: {r['skipped']}")
            continue
        print(f"{r['symbol']:<6}{r['close']:>10.2f}{r['sma50']:>10.2f}"
              f"{r['rsi2']:>7.1f}{'pass' if r['regime_ok'] else 'FAIL':>8}"
              f"{'pass' if r['trigger_ok'] else 'FAIL':>9}"
              f"{'YES' if r['signal'] else '-':>9}")

    fired = [r for r in rows if r.get("signal")]
    print()
    if not fired:
        print("No setups on the latest bar.")
        return
    for r in fired:
        print(f"{r['symbol']} setup ({r['setup_date']}):")
        print(f"  entry   BUY STP {r['entry_stop']:.2f} LMT {r['entry_limit']:.2f}")
        print(f"  stop    {r['stop_loss']:.2f}   ({r['risk_per_share']:.2f}/share)")
        print(f"  target  {r['take_profit']:.2f}   (SMA10, re-pegged daily)")
        print(f"  R:R     {r['reward_risk']:.2f}   "
              f"(floor {CONFIG.strategy.min_reward_risk_ratio:.2f})")
        if nlv and "shares" in r:
            print(f"  size    {r['shares']} shares, notional ${r['notional']:,}, "
                  f"risk ${r['risk_total']:,}")
        print(f"  exit    time stop after {CONFIG.strategy.time_stop_sessions} "
              f"open sessions")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bars", required=True, help="path to the bars JSON file")
    ap.add_argument("--nlv", type=float, default=None,
                    help="net liquidation in USD; adds position sizing")
    ap.add_argument("--available", type=float, default=None,
                    help="available funds in USD; caps the sizing")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="emit the raw result rows instead of a table")
    args = ap.parse_args()

    try:
        frames = load_frames(args.bars)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"cannot read bars: {exc}", file=sys.stderr)
        return 2

    rows = scan(frames, args.nlv, args.available)
    if args.as_json:
        print(json.dumps(rows, indent=2))
    else:
        render(rows, args.nlv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
