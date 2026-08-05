"""Pullback-Momentum signal logic (pure functions, no IB dependency).

Setup (evaluated on the daily close):
  1. Regime filter  : close > SMA(50)            — only buy dips in uptrends
  2. Trigger        : RSI(2) < 15                — aggressively oversold
  3. Confirmation   : next-session BUY STOP-LIMIT at setup-day high * 1.005
                      — price must reclaim upward momentum before we own it.

Exits (attached as bracket children + daily management):
  * Stop-loss   : fill - 1.5 * ATR(14)
  * Take-profit : limit at SMA(10), re-pegged every day
  * Time stop   : market-close the position on its 5th open session
"""

import logging
from dataclasses import dataclass

import pandas as pd

from config import CONFIG

log = logging.getLogger("bot.strategy")


@dataclass(frozen=True)
class EntrySignal:
    symbol: str
    setup_date: pd.Timestamp
    setup_close: float
    setup_high: float
    stop_price: float       # buy-stop trigger: high * (1 + 0.5%)
    limit_price: float      # limit cap just above the trigger
    atr14: float
    sma10: float
    stop_loss_distance: float  # 1.5 * ATR(14), in dollars per share


def evaluate_symbol(symbol: str, ind: pd.DataFrame) -> EntrySignal | None:
    """Return an EntrySignal if the latest completed daily bar is a setup."""
    s = CONFIG.strategy
    last = ind.iloc[-1]

    required = ("close", "high", "sma50", "sma10", "rsi2", "atr14")
    if any(pd.isna(last[c]) for c in required):
        log.debug("%s: indicators not warmed up yet", symbol)
        return None

    regime_ok = last["close"] > last["sma50"]          # strictly greater
    trigger_ok = last["rsi2"] < s.rsi_oversold

    if not regime_ok:
        log.debug("%s: regime filter failed (close %.2f <= sma50 %.2f)",
                  symbol, last["close"], last["sma50"])
        return None
    if not trigger_ok:
        log.debug("%s: rsi2 %.1f not below %.1f", symbol, last["rsi2"], s.rsi_oversold)
        return None

    stop_price = round(last["high"] * (1 + s.entry_stop_pct_above_high), 2)
    limit_price = round(stop_price * (1 + s.entry_limit_pct_above_stop), 2)
    signal = EntrySignal(
        symbol=symbol,
        setup_date=ind.index[-1],
        setup_close=float(last["close"]),
        setup_high=float(last["high"]),
        stop_price=stop_price,
        limit_price=limit_price,
        atr14=float(last["atr14"]),
        sma10=float(last["sma10"]),
        stop_loss_distance=round(s.stop_atr_multiple * float(last["atr14"]), 2),
    )
    log.info("%s SETUP: close=%.2f rsi2=%.1f > entry stop %.2f (limit %.2f), "
             "SL dist %.2f, TP ref sma10 %.2f",
             symbol, signal.setup_close, last["rsi2"], signal.stop_price,
             signal.limit_price, signal.stop_loss_distance, signal.sma10)
    return signal


def position_size(net_liquidation: float, stop_loss_distance: float) -> int:
    """Shares such that an exact stop-loss hit loses risk_pct of NLV.

    shares = (NLV * 1.5%) / (1.5 * ATR14)   — floored to a whole share count.
    """
    if stop_loss_distance <= 0:
        return 0
    risk_dollars = net_liquidation * CONFIG.strategy.risk_pct_of_nlv
    return int(risk_dollars // stop_loss_distance)


def affordable_size(shares: int, limit_price: float, buying_power: float) -> int:
    """Never send an order the account cannot settle at the limit price."""
    if limit_price <= 0:
        return 0
    max_affordable = int(buying_power // limit_price)
    return max(0, min(shares, max_affordable))
