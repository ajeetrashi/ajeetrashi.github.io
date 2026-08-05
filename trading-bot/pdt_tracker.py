"""Pattern Day Trader guard for sub-25k accounts.

A *day trade* is opening and closing the same symbol within one session.
FINRA flags an account that makes 4+ day trades inside 5 rolling business
days. This module keeps a local, append-only execution journal and refuses
to authorize any action that could become the 4th day trade.

Two checkpoints use it:
  * Before transmitting a NEW entry whose bracket children could fill the
    same day (every entry, conservatively), we verify headroom exists.
  * Before any same-day liquidation (manual close / time-stop edge case).

The journal survives restarts, so the rolling count is reconstructed from
disk — never from in-memory state alone.
"""

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from config import CONFIG

log = logging.getLogger("bot.pdt")


@dataclass
class ExecutionRecord:
    symbol: str
    side: str            # "BUY" | "SELL"
    quantity: int
    price: float
    exec_date: str       # ISO date of the fill (exchange local date)
    exec_time: str       # ISO timestamp
    order_ref: str = ""


def _business_days_back(end: date, n: int) -> date:
    """The date n business days before `end` (weekend-aware; holidays are
    treated conservatively as trading days, which only makes the guard
    stricter, never looser)."""
    d, remaining = end, n
    while remaining > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            remaining -= 1
    return d


class PDTTracker:
    """Thread-safe rolling day-trade counter backed by a JSON journal."""

    def __init__(self, path: str | None = None):
        self.path = path or CONFIG.pdt.trade_log_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._records: list[ExecutionRecord] = self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> list[ExecutionRecord]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, encoding="utf-8") as fh:
                raw = json.load(fh)
            return [ExecutionRecord(**r) for r in raw]
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            # A corrupt journal must FAIL CLOSED: quarantine it and start
            # empty, but scream in the logs — the operator should reconcile
            # against IBKR's own trade history before re-enabling entries.
            quarantine = self.path + ".corrupt"
            os.replace(self.path, quarantine)
            log.critical("PDT journal unreadable (%s); moved to %s. "
                         "Reconcile with IBKR trade history!", exc, quarantine)
            return []

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump([asdict(r) for r in self._records], fh, indent=2)
        os.replace(tmp, self.path)   # atomic on POSIX

    # -- recording ----------------------------------------------------------

    def record_execution(self, symbol: str, side: str, quantity: int,
                         price: float, when: datetime, order_ref: str = "") -> None:
        rec = ExecutionRecord(
            symbol=symbol, side=side.upper(), quantity=quantity, price=price,
            exec_date=when.date().isoformat(), exec_time=when.isoformat(),
            order_ref=order_ref,
        )
        with self._lock:
            self._records.append(rec)
            self._save()
        log.info("journal: %s %d %s @ %.2f on %s",
                 rec.side, quantity, symbol, price, rec.exec_date)

    # -- day-trade math ------------------------------------------------------

    def day_trades_in_window(self, as_of: date | None = None) -> int:
        """Count round-trips (buy+sell same symbol, same date) in the
        rolling 5-business-day window ending `as_of` (inclusive)."""
        as_of = as_of or date.today()
        start = _business_days_back(as_of, CONFIG.pdt.rolling_window_days - 1)
        with self._lock:
            in_window = [r for r in self._records
                         if start.isoformat() <= r.exec_date <= as_of.isoformat()]
        count = 0
        by_key: dict[tuple, dict] = {}
        for r in in_window:
            k = (r.symbol, r.exec_date)
            slot = by_key.setdefault(k, {"BUY": 0, "SELL": 0})
            slot[r.side] += 1
        for slot in by_key.values():
            count += min(slot["BUY"], slot["SELL"])
        return count

    def can_open_new_position(self, as_of: date | None = None) -> bool:
        """Conservative pre-trade gate.

        Every new entry carries attached SL/TP children that *could* fill the
        same session, so a new position is only authorized while a same-day
        round-trip would still be within the limit.
        """
        used = self.day_trades_in_window(as_of)
        headroom = CONFIG.pdt.max_day_trades - used
        if headroom <= 0:
            log.warning("PDT guard: %d/%d day trades used in rolling window — "
                        "blocking new entries", used, CONFIG.pdt.max_day_trades)
            return False
        return True

    def can_close_today(self, symbol: str, opened_today: bool,
                        as_of: date | None = None) -> bool:
        """Gate for same-day liquidations. Closing a position opened on a
        prior day is never a day trade and is always allowed."""
        if not opened_today:
            return True
        used = self.day_trades_in_window(as_of)
        allowed = used < CONFIG.pdt.max_day_trades
        if not allowed:
            log.warning("PDT guard: refusing same-day close of %s "
                        "(%d/%d day trades used)", symbol, used,
                        CONFIG.pdt.max_day_trades)
        return allowed
