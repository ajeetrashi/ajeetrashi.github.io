"""Central configuration for the Pullback-Momentum swing-trading bot.

Every tunable number in the system lives here so the strategy can be
audited (and re-parameterized) without touching logic code.
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConnectionConfig:
    host: str = "127.0.0.1"
    # 4002 = IB Gateway PAPER trading (recommended for the dry run)
    # 7497 = TWS PAPER trading
    # 4001 = IB Gateway LIVE   |   7496 = TWS LIVE  (do NOT use until validated)
    port: int = 4002
    client_id: int = 17
    # Reconnect/backoff policy for socket drops
    reconnect_max_attempts: int = 10
    reconnect_base_delay_s: float = 2.0     # doubles each attempt, capped below
    reconnect_max_delay_s: float = 120.0
    # ib_async request timeout
    request_timeout_s: float = 30.0


# ---------------------------------------------------------------------------
# Strategy parameters (Pullback-Momentum / mean-reversion-in-uptrend)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrategyConfig:
    # Asset universe: highly liquid, high-ATR US equities and ETFs
    universe: tuple = ("SPY", "QQQ", "NVDA", "META", "TSLA", "AMD", "IWM")

    # Regime filter: daily close must be strictly above the 50-day SMA
    regime_sma_period: int = 50

    # Trigger: 2-period RSI below this value marks a short-term oversold dip
    rsi_period: int = 2
    rsi_oversold: float = 15.0

    # Confirmation entry: buy STOP-LIMIT for the next session, stop trigger
    # 0.5% above the setup day's high (limit a touch above the stop so a fast
    # gap-through doesn't leave us unfilled forever, but a runaway gap is
    # skipped rather than chased).
    entry_stop_pct_above_high: float = 0.005
    entry_limit_pct_above_stop: float = 0.003

    # Risk / exits
    atr_period: int = 14
    stop_atr_multiple: float = 1.5          # SL = fill - 1.5 * ATR(14)
    risk_pct_of_nlv: float = 0.015          # max loss 1.5% of Net Liquidation
    take_profit_sma_period: int = 10        # TP limit = 10-day SMA, refreshed daily
    time_stop_sessions: int = 5             # flat at market before close on day 5

    # Data
    daily_bars_lookback: str = "1 Y"        # enough history for SMA50 + warmup


# ---------------------------------------------------------------------------
# PDT (Pattern Day Trader) guard — account is under 25k USD
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PDTConfig:
    max_day_trades: int = 3                 # hard ceiling in any rolling window
    rolling_window_days: int = 5            # 5 *business* days
    # Persisted execution/trade journal used to reconstruct the rolling count
    trade_log_path: str = "logs/trade_journal.json"


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BotConfig:
    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    pdt: PDTConfig = field(default_factory=PDTConfig)
    log_dir: str = "logs"
    # Minutes before the exchange close when the daily decision cycle runs
    # (signals are evaluated on that day's nearly-final bar, and time-stop
    # liquidations go out as market orders while liquidity is still deep).
    minutes_before_close: int = 10
    timezone: str = "US/Eastern"
    dry_run: bool = True                    # log orders instead of transmitting


CONFIG = BotConfig()
