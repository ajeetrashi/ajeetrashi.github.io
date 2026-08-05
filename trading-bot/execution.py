"""Order routing, bracket construction, and connection resilience.

Entry orders are BUY STOP-LIMIT parents with two attached children
(OCA group, transmitted atomically):
    * STP  stop-loss   at fill_ref - 1.5 * ATR(14)
    * LMT  take-profit at SMA(10)  — re-pegged daily by manage_open_positions

The IBConnection wrapper owns the socket: every disconnect (drop, pacing
lockout, gateway restart) funnels through an exponential-backoff reconnect
loop, and callers simply await `ensure_connected()` before touching the API.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime

from ib_async import IB, Forex, LimitOrder, MarketOrder, Order, StopOrder, Trade

from config import CONFIG
from data_fetcher import make_contract
from pdt_tracker import PDTTracker
from strategy import EntrySignal, affordable_size, position_size

log = logging.getLogger("bot.exec")


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

class IBConnection:
    """Owns the IB socket and transparently recovers from disconnects."""

    def __init__(self):
        self.ib = IB()
        self._reconnecting = asyncio.Lock()
        self.ib.disconnectedEvent += self._on_disconnect
        self.ib.errorEvent += self._on_error

    async def connect(self) -> None:
        c = CONFIG.connection
        delay = c.reconnect_base_delay_s
        for attempt in range(1, c.reconnect_max_attempts + 1):
            try:
                await self.ib.connectAsync(c.host, c.port, clientId=c.client_id,
                                           timeout=c.request_timeout_s)
                log.info("connected to IB on %s:%d (clientId=%d)",
                         c.host, c.port, c.client_id)
                return
            except (ConnectionRefusedError, OSError, asyncio.TimeoutError) as exc:
                log.warning("connect attempt %d/%d failed: %s — retrying in %.0fs",
                            attempt, c.reconnect_max_attempts, exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, c.reconnect_max_delay_s)
        raise ConnectionError(
            f"could not reach IB Gateway/TWS on {c.host}:{c.port} after "
            f"{c.reconnect_max_attempts} attempts — is the gateway running "
            f"and the API port enabled?")

    async def ensure_connected(self) -> IB:
        if not self.ib.isConnected():
            async with self._reconnecting:
                if not self.ib.isConnected():      # re-check under the lock
                    log.warning("socket down — reconnecting")
                    await self.connect()
        return self.ib

    def _on_disconnect(self):
        log.error("IB API disconnected")

    def _on_error(self, reqId, errorCode, errorString, *args):
        # 1100/1101/1102 = connectivity lost/restored; 100/162 = pacing
        if errorCode in (1100,):
            log.error("IB connectivity lost (code %d): %s", errorCode, errorString)
        elif errorCode in (1101, 1102):
            log.info("IB connectivity restored (code %d)", errorCode)
        elif errorCode in (100, 162, 165, 366):
            log.warning("IB pacing/data notice (code %d): %s", errorCode, errorString)
        elif errorCode >= 2000:   # 21xx are status notices, not failures
            log.debug("IB notice %d: %s", errorCode, errorString)
        else:
            log.warning("IB error %d (reqId %s): %s", errorCode, reqId, errorString)


# ---------------------------------------------------------------------------
# Account helpers
# ---------------------------------------------------------------------------

async def usd_conversion_rate(ib: IB, currency: str) -> float | None:
    """USD value of 1 unit of `currency` (e.g. SGD -> ~0.74), via the
    latest midpoint of the USD.<currency> forex pair. None on failure —
    callers must treat that as "size nothing", never guess a rate."""
    if currency == "USD":
        return 1.0
    try:
        pair = Forex("USD" + currency)
        await ib.qualifyContractsAsync(pair)
        bars = await asyncio.wait_for(
            ib.reqHistoricalDataAsync(
                pair, endDateTime="", durationStr="2 D",
                barSizeSetting="1 day", whatToShow="MIDPOINT", useRTH=False,
            ),
            timeout=CONFIG.connection.request_timeout_s,
        )
        if bars and bars[-1].close > 0:
            return 1.0 / bars[-1].close      # <ccy> per USD -> USD per <ccy>
    except Exception as exc:  # noqa: BLE001
        log.error("FX rate USD%s unavailable: %s", currency, exc)
    return None


async def account_values(ib: IB) -> tuple[float, float]:
    """(net_liquidation, buying_power) in USD.

    IBKR reports account summary in the account's BASE currency (SGD for
    this account), so non-USD values are converted at the current forex
    midpoint. If the FX rate can't be fetched, returns (0, 0) so sizing
    fails closed instead of trading on a wrong account value.
    """
    summary = await ib.accountSummaryAsync()
    raw: dict[str, tuple[float, str]] = {}
    for row in summary:
        if row.tag in ("NetLiquidation", "BuyingPower"):
            raw[row.tag] = (float(row.value), row.currency)

    out = []
    for tag in ("NetLiquidation", "BuyingPower"):
        value, ccy = raw.get(tag, (0.0, "USD"))
        rate = await usd_conversion_rate(ib, ccy)
        if rate is None:
            log.critical("%s reported in %s but no FX rate — refusing to size",
                         tag, ccy)
            return 0.0, 0.0
        out.append(value * rate)
    return out[0], out[1]


# ---------------------------------------------------------------------------
# Bracket construction
# ---------------------------------------------------------------------------

@dataclass
class ManagedPosition:
    symbol: str
    entry_trade: Trade
    stop_trade: Trade
    tp_trade: Trade
    entry_date: date
    sessions_open: int = 0


def build_entry_bracket(signal: EntrySignal, quantity: int,
                        next_order_id: int) -> list[Order]:
    """Stop-limit parent + ATR stop-loss + SMA10 take-profit (OCA children).

    The SL/TP prices are seeded from the signal's reference levels; the SL is
    re-anchored to the actual fill price on execution, and the TP is re-pegged
    to the fresh SMA10 every session by manage_open_positions().
    """
    s = CONFIG.strategy
    parent = Order(
        orderId=next_order_id,
        action="BUY",
        orderType="STP LMT",
        totalQuantity=quantity,
        auxPrice=signal.stop_price,        # stop trigger
        lmtPrice=signal.limit_price,       # limit cap
        tif="DAY",                          # confirmation valid next session only
        transmit=False,
    )
    stop_loss = StopOrder(
        "SELL", quantity,
        round(signal.stop_price - signal.stop_loss_distance, 2),
        orderId=next_order_id + 1, parentId=parent.orderId,
        tif="GTC", transmit=False,
    )
    take_profit = LimitOrder(
        "SELL", quantity,
        round(signal.sma10, 2),
        orderId=next_order_id + 2, parentId=parent.orderId,
        tif="GTC", transmit=True,           # last child transmits the batch
    )
    return [parent, stop_loss, take_profit]


# ---------------------------------------------------------------------------
# Order routing
# ---------------------------------------------------------------------------

class Executor:
    def __init__(self, conn: IBConnection, pdt: PDTTracker):
        self.conn = conn
        self.pdt = pdt
        self.positions: dict[str, ManagedPosition] = {}

    async def submit_entry(self, signal: EntrySignal) -> ManagedPosition | None:
        ib = await self.conn.ensure_connected()

        # --- PDT gate: checked against the on-disk journal, every time -----
        if not self.pdt.can_open_new_position():
            log.warning("%s: entry suppressed by PDT guard", signal.symbol)
            return None
        if signal.symbol in self.positions:
            log.info("%s: already holding — one position per symbol", signal.symbol)
            return None

        nlv, buying_power = await account_values(ib)
        shares = position_size(nlv, signal.stop_loss_distance)
        shares = affordable_size(shares, signal.limit_price, buying_power)
        if shares <= 0:
            log.warning("%s: sized to 0 shares (nlv=%.0f, SL dist=%.2f) — skipping",
                        signal.symbol, nlv, signal.stop_loss_distance)
            return None

        risk = shares * signal.stop_loss_distance
        log.info("%s: sizing %d shares — max SL loss $%.0f (%.2f%% of NLV $%.0f)",
                 signal.symbol, shares, risk, 100 * risk / nlv, nlv)

        if CONFIG.dry_run:
            log.info("[DRY RUN] %s bracket NOT transmitted: BUY %d STP %.2f "
                     "LMT %.2f / SL %.2f / TP %.2f",
                     signal.symbol, shares, signal.stop_price, signal.limit_price,
                     signal.stop_price - signal.stop_loss_distance, signal.sma10)
            return None

        contract = make_contract(signal.symbol)
        await ib.qualifyContractsAsync(contract)
        orders = build_entry_bracket(signal, shares, ib.client.getReqId())
        trades = [ib.placeOrder(contract, o) for o in orders]
        pos = ManagedPosition(
            symbol=signal.symbol,
            entry_trade=trades[0], stop_trade=trades[1], tp_trade=trades[2],
            entry_date=date.today(),
        )
        self.positions[signal.symbol] = pos
        trades[0].fillEvent += self._make_fill_recorder(signal.symbol)
        trades[1].fillEvent += self._make_fill_recorder(signal.symbol)
        trades[2].fillEvent += self._make_fill_recorder(signal.symbol)
        return pos

    def _make_fill_recorder(self, symbol: str):
        def _on_fill(trade: Trade, fill):
            self.pdt.record_execution(
                symbol=symbol,
                side=trade.order.action,
                quantity=int(fill.execution.shares),
                price=float(fill.execution.price),
                when=datetime.now(),
                order_ref=str(trade.order.orderId),
            )
        return _on_fill

    # -- daily management ---------------------------------------------------

    async def manage_open_positions(self, sma10_by_symbol: dict[str, float],
                                    atr_by_symbol: dict[str, float]) -> None:
        """Run once per session near the close.

        1. Drop brackets whose DAY entry never triggered (auto-expired).
        2. Re-anchor the stop-loss to the actual fill price.
        3. Re-peg the take-profit limit to today's SMA10.
        4. Enforce the 5-session time stop with a market close.
        """
        ib = await self.conn.ensure_connected()

        for symbol in list(self.positions):
            pos = self.positions[symbol]
            entry = pos.entry_trade

            if entry.orderStatus.status in ("Cancelled", "Inactive", "ApiCancelled"):
                log.info("%s: entry never triggered — bracket expired", symbol)
                del self.positions[symbol]
                continue
            if not entry.orderStatus.filled:
                continue    # still waiting on the confirmation trigger

            pos.sessions_open += 1
            fill_px = entry.orderStatus.avgFillPrice
            atr = atr_by_symbol.get(symbol)
            sma10 = sma10_by_symbol.get(symbol)

            # (2) stop-loss re-anchored to the true fill
            if atr:
                new_sl = round(fill_px - CONFIG.strategy.stop_atr_multiple * atr, 2)
                if abs(new_sl - pos.stop_trade.order.auxPrice) >= 0.01:
                    pos.stop_trade.order.auxPrice = new_sl
                    ib.placeOrder(entry.contract, pos.stop_trade.order)
                    log.info("%s: SL re-anchored to %.2f", symbol, new_sl)

            # (3) TP re-pegged to the fresh short-term mean
            if sma10:
                new_tp = round(sma10, 2)
                if abs(new_tp - pos.tp_trade.order.lmtPrice) >= 0.01:
                    pos.tp_trade.order.lmtPrice = new_tp
                    ib.placeOrder(entry.contract, pos.tp_trade.order)
                    log.info("%s: TP re-pegged to SMA10 %.2f", symbol, new_tp)

            # (4) time stop
            if pos.sessions_open >= CONFIG.strategy.time_stop_sessions:
                await self._close_at_market(pos, reason="time stop (5 sessions)")

    async def _close_at_market(self, pos: ManagedPosition, reason: str) -> None:
        ib = await self.conn.ensure_connected()
        opened_today = pos.entry_date == date.today()
        if not self.pdt.can_close_today(pos.symbol, opened_today):
            log.warning("%s: %s close DEFERRED to next session by PDT guard",
                        pos.symbol, reason)
            return
        qty = int(pos.entry_trade.orderStatus.filled)
        log.info("%s: closing %d shares at market — %s", pos.symbol, qty, reason)
        for child in (pos.stop_trade, pos.tp_trade):
            if child.orderStatus.status not in ("Filled", "Cancelled"):
                ib.cancelOrder(child.order)
        close = MarketOrder("SELL", qty)
        trade = ib.placeOrder(pos.entry_trade.contract, close)
        trade.fillEvent += self._make_fill_recorder(pos.symbol)
        del self.positions[pos.symbol]
