"""Entry point: daily decision cycle for the Pullback-Momentum swing bot.

Flow (once per trading day, shortly before the NYSE close):
    1. Ensure the IB socket is up (reconnect with backoff if not).
    2. Pull daily bars + indicators for the whole universe.
    3. Manage open positions: expire dead brackets, re-anchor SLs,
       re-peg TPs to SMA10, enforce the 5-session time stop.
    4. Scan for fresh setups (close > SMA50 and RSI2 < 15) and stage
       next-session buy stop-limit brackets — gated by the PDT tracker.
    5. Sleep until the next session's decision time.

Run modes:
    python main.py            # scheduled loop (waits for decision time)
    python main.py --once     # single cycle immediately, then exit (dry test)
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from config import CONFIG
from data_fetcher import compute_indicators, fetch_daily_bars, has_enough_history
from execution import Executor, IBConnection
from pdt_tracker import PDTTracker
from strategy import evaluate_symbol

log = logging.getLogger("bot")

NYSE_CLOSE = time(16, 0)


def setup_logging() -> None:
    os.makedirs(CONFIG.log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(CONFIG.log_dir, "bot.log")),
        ],
    )


def next_decision_time(now: datetime) -> datetime:
    """Next weekday decision point: N minutes before the 16:00 ET close."""
    tz = ZoneInfo(CONFIG.timezone)
    now = now.astimezone(tz)
    target_t = (datetime.combine(now.date(), NYSE_CLOSE)
                - timedelta(minutes=CONFIG.minutes_before_close)).time()
    candidate = datetime.combine(now.date(), target_t, tzinfo=tz)
    while candidate <= now or candidate.weekday() >= 5:
        candidate = datetime.combine(candidate.date() + timedelta(days=1),
                                     target_t, tzinfo=tz)
    return candidate


async def run_cycle(conn: IBConnection, executor: Executor) -> None:
    ib = await conn.ensure_connected()

    # ---- data sweep -------------------------------------------------------
    indicators, sma10_map, atr_map = {}, {}, {}
    for symbol in CONFIG.strategy.universe:
        df = await fetch_daily_bars(ib, symbol)
        if df is None or not has_enough_history(df):
            log.warning("%s: skipping this cycle (no/insufficient data)", symbol)
            continue
        ind = compute_indicators(df)
        indicators[symbol] = ind
        last = ind.iloc[-1]
        sma10_map[symbol] = float(last["sma10"])
        atr_map[symbol] = float(last["atr14"])

    # ---- manage what we already hold first --------------------------------
    await executor.manage_open_positions(sma10_map, atr_map)

    # ---- then hunt for new setups -----------------------------------------
    for symbol, ind in indicators.items():
        signal = evaluate_symbol(symbol, ind)
        if signal is not None:
            await executor.submit_entry(signal)

    used = executor.pdt.day_trades_in_window()
    log.info("cycle complete — open positions: %d, day trades used: %d/%d",
             len(executor.positions), used, CONFIG.pdt.max_day_trades)


async def main(once: bool) -> None:
    setup_logging()
    mode = "DRY RUN (orders logged, not transmitted)" if CONFIG.dry_run \
        else "LIVE TRANSMIT"
    log.info("Pullback-Momentum bot starting — %s — universe: %s",
             mode, ", ".join(CONFIG.strategy.universe))

    conn = IBConnection()
    await conn.connect()
    executor = Executor(conn, PDTTracker())

    try:
        if once:
            await run_cycle(conn, executor)
            return
        while True:
            tz = ZoneInfo(CONFIG.timezone)
            target = next_decision_time(datetime.now(tz))
            wait_s = (target - datetime.now(tz)).total_seconds()
            log.info("next decision cycle at %s (%.0f min from now)",
                     target.isoformat(), wait_s / 60)
            await asyncio.sleep(max(wait_s, 0))
            try:
                await run_cycle(conn, executor)
            except ConnectionError:
                log.error("cycle aborted on connection loss — will reconnect "
                          "before the next cycle")
    finally:
        if conn.ib.isConnected():
            conn.ib.disconnect()
        log.info("bot stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pullback-Momentum swing bot")
    parser.add_argument("--once", action="store_true",
                        help="run one decision cycle immediately and exit")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.once))
    except KeyboardInterrupt:
        print("interrupted — exiting")
