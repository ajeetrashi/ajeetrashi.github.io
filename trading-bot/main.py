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
    python main.py --status   # is the bot alive? what did it last do? (no IB needed)
"""

import argparse
import asyncio
import json
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
HEARTBEAT_PATH = os.path.join(CONFIG.log_dir, "heartbeat.json")


def write_heartbeat(state: str, **fields) -> None:
    """Persist a small status snapshot so `--status` can answer "is it
    alive?" without needing the bot's terminal or an IB connection."""
    os.makedirs(CONFIG.log_dir, exist_ok=True)
    # Carry the last cycle summary forward so a sleep/stop heartbeat doesn't
    # erase what the bot last did.
    if "last_cycle" not in fields and os.path.exists(HEARTBEAT_PATH):
        try:
            with open(HEARTBEAT_PATH, encoding="utf-8") as fh:
                prev = json.load(fh).get("last_cycle")
            if prev:
                fields["last_cycle"] = prev
        except (json.JSONDecodeError, OSError):
            pass
    payload = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "state": state,
        "mode": "dry_run" if CONFIG.dry_run else "LIVE",
        "port": CONFIG.connection.port,
        **fields,
    }
    tmp = HEARTBEAT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, HEARTBEAT_PATH)


def print_status() -> int:
    """Plain-English health report from the heartbeat file. Exit code 0 when
    the bot looks alive, 1 when it looks dead or has never run."""
    if not os.path.exists(HEARTBEAT_PATH):
        print("NOT RUNNING — the bot has never completed a start on this "
              "machine (no logs/heartbeat.json). Start it with: python main.py")
        return 1
    with open(HEARTBEAT_PATH, encoding="utf-8") as fh:
        hb = json.load(fh)
    updated = datetime.fromisoformat(hb["updated_at"])
    age = datetime.now().astimezone() - updated
    hours = age.total_seconds() / 3600
    state = hb.get("state", "?")

    # While sleeping the heartbeat is deliberately untouched (a Friday sleep
    # legitimately lasts until Monday), so judge a sleeper by whether its
    # scheduled cycle has come and gone. Any other state goes stale at ~26h.
    now = datetime.now().astimezone()
    if state == "sleeping" and "next_cycle" in hb:
        due = datetime.fromisoformat(hb["next_cycle"])
        alive = now < due + timedelta(hours=1)
    else:
        alive = state in ("cycle_done", "started") and hours < 26
    verdict = "ALIVE" if alive else "NOT RUNNING"
    if state == "stopped":
        verdict = "STOPPED (exited cleanly)"

    print(f"{verdict} — mode: {hb.get('mode')} on port {hb.get('port')}")
    print(f"Last heartbeat: {updated:%Y-%m-%d %H:%M %Z} ({hours:.1f} h ago), "
          f"state: {state}")
    if "next_cycle" in hb:
        print(f"Next decision cycle: {hb['next_cycle']}")
    if "last_cycle" in hb:
        lc = hb["last_cycle"]
        print(f"Last cycle: {lc['at']} — scanned {lc['scanned']} symbols, "
              f"setups found: {lc['setups'] or 'none'}, "
              f"open positions: {lc['open_positions']}, "
              f"day trades used: {lc['day_trades_used']}/{CONFIG.pdt.max_day_trades}")
    else:
        print("Last cycle: none completed yet")
    if not alive and state != "stopped":
        print("→ The bot process is not running (or the Mac was asleep). "
              "Restart it with: caffeinate -i python main.py")
    return 0 if alive else 1


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
    setups = []
    for symbol, ind in indicators.items():
        signal = evaluate_symbol(symbol, ind)
        if signal is not None:
            setups.append(symbol)
            await executor.submit_entry(signal)

    used = executor.pdt.day_trades_in_window()
    log.info("cycle complete — open positions: %d, day trades used: %d/%d",
             len(executor.positions), used, CONFIG.pdt.max_day_trades)
    write_heartbeat("cycle_done", last_cycle={
        "at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "scanned": len(indicators),
        "setups": setups,
        "open_positions": len(executor.positions),
        "day_trades_used": used,
    })


async def main(once: bool) -> None:
    setup_logging()
    mode = "DRY RUN (orders logged, not transmitted)" if CONFIG.dry_run \
        else "LIVE TRANSMIT"
    log.info("Pullback-Momentum bot starting — %s — universe: %s",
             mode, ", ".join(CONFIG.strategy.universe))

    conn = IBConnection()
    await conn.connect()
    executor = Executor(conn, PDTTracker())
    write_heartbeat("started")

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
            write_heartbeat("sleeping", next_cycle=target.isoformat(timespec="minutes"))
            await asyncio.sleep(max(wait_s, 0))
            try:
                await run_cycle(conn, executor)
            except ConnectionError:
                log.error("cycle aborted on connection loss — will reconnect "
                          "before the next cycle")
                write_heartbeat("connection_lost")
    finally:
        if conn.ib.isConnected():
            conn.ib.disconnect()
        write_heartbeat("stopped")
        log.info("bot stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pullback-Momentum swing bot")
    parser.add_argument("--once", action="store_true",
                        help="run one decision cycle immediately and exit")
    parser.add_argument("--status", action="store_true",
                        help="report whether the bot is alive and what it last did")
    args = parser.parse_args()
    if args.status:
        sys.exit(print_status())
    try:
        asyncio.run(main(args.once))
    except KeyboardInterrupt:
        print("interrupted — exiting")
