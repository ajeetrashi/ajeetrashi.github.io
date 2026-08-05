"""Historical data retrieval + indicator computation.

All IB API access in this module is defensive: every request is wrapped
against pacing violations (IB error 100/162) and socket drops, with
exponential-backoff retries handled by the shared connection manager.
"""

import asyncio
import logging

import numpy as np
import pandas as pd
from ib_async import IB, Stock, util
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

from config import CONFIG

log = logging.getLogger("bot.data")

# IB error codes that mean "slow down and retry", not "give up"
PACING_ERROR_CODES = {100, 162, 165, 366}
RETRYABLE_ATTEMPTS = 4
PACING_COOLDOWN_S = 15.0


def make_contract(symbol: str) -> Stock:
    """SMART-routed US stock/ETF contract."""
    return Stock(symbol, "SMART", "USD")


async def fetch_daily_bars(ib: IB, symbol: str) -> pd.DataFrame | None:
    """Fetch ~1 year of daily bars for `symbol`.

    Returns a DataFrame indexed by date with open/high/low/close/volume,
    or None if the data could not be retrieved after retries.
    """
    contract = make_contract(symbol)
    delay = PACING_COOLDOWN_S
    for attempt in range(1, RETRYABLE_ATTEMPTS + 1):
        try:
            await ib.qualifyContractsAsync(contract)
            bars = await asyncio.wait_for(
                ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime="",
                    durationStr=CONFIG.strategy.daily_bars_lookback,
                    barSizeSetting="1 day",
                    whatToShow="TRADES",
                    useRTH=True,
                    formatDate=1,
                ),
                timeout=CONFIG.connection.request_timeout_s,
            )
            if not bars:
                log.warning("%s: empty historical data response", symbol)
                return None
            df = util.df(bars)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            return df[["open", "high", "low", "close", "volume"]]
        except asyncio.TimeoutError:
            log.warning("%s: historical data timeout (attempt %d/%d)",
                        symbol, attempt, RETRYABLE_ATTEMPTS)
        except ConnectionError:
            # Socket died mid-request; the connection manager owns reconnects.
            log.error("%s: connection lost during data fetch", symbol)
            raise
        except Exception as exc:  # noqa: BLE001 - IB raises bare Exception subtypes
            code = getattr(exc, "code", None)
            if code in PACING_ERROR_CODES:
                log.warning("%s: pacing violation (code %s), cooling down %.0fs",
                            symbol, code, delay)
            else:
                log.warning("%s: data fetch error (attempt %d/%d): %s",
                            symbol, attempt, RETRYABLE_ATTEMPTS, exc)
        await asyncio.sleep(delay)
        delay *= 2
    log.error("%s: giving up on historical data after %d attempts",
              symbol, RETRYABLE_ATTEMPTS)
    return None


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Append every indicator the strategy needs to a daily-bar frame.

    Columns added: sma50, sma10, rsi2, atr14.
    """
    s = CONFIG.strategy
    out = df.copy()
    out["sma50"] = out["close"].rolling(s.regime_sma_period).mean()
    out["sma10"] = out["close"].rolling(s.take_profit_sma_period).mean()
    out["rsi2"] = RSIIndicator(close=out["close"], window=s.rsi_period).rsi()
    out["atr14"] = AverageTrueRange(
        high=out["high"], low=out["low"], close=out["close"],
        window=s.atr_period,
    ).average_true_range()
    return out


def has_enough_history(df: pd.DataFrame) -> bool:
    """True when the frame is deep enough for the slowest indicator (SMA50)."""
    needed = CONFIG.strategy.regime_sma_period + 5
    return len(df) >= needed and np.isfinite(df["close"].iloc[-1])
