# Pullback-Momentum Swing Trading Bot (IBKR / ib_async)

Automated swing-trading bot implementing a **mean-reversion-in-an-uptrend**
strategy, designed for a sub-25k USD account subject to the US Pattern Day
Trader (PDT) rule.

> **This code is for paper-trading validation first.** `dry_run` is `True` by
> default — orders are logged, never transmitted — and the default port is the
> IB Gateway **paper** port. Do not point it at a live port until the strategy
> has been validated to your satisfaction. Nothing here is financial advice.

## Strategy (exact parameters)

| Component | Rule |
|---|---|
| Universe | SPY, QQQ, NVDA, META, TSLA, AMD, IWM (edit in `config.py`) |
| Regime filter | Daily close **strictly >** 50-day SMA |
| Trigger | RSI(2) **< 15** at the daily close |
| Entry | Next-session **BUY STOP-LIMIT** at setup-day high × 1.005 (DAY order) |
| Stop-loss | Fill − **1.5 × ATR(14)**, re-anchored to the actual fill |
| Sizing | Exact SL hit = **1.5% of Net Liquidation Value** max loss |
| Take-profit | Limit at the **10-day SMA**, re-pegged every session |
| Time stop | Market close before the end of the **5th** open session |
| PDT guard | Local journal blocks anything that could be a 4th day trade in 5 business days |

## File structure

```
trading-bot/
├── config.py        # every tunable parameter (ports, universe, risk, PDT)
├── data_fetcher.py  # IB historical daily bars + SMA/RSI/ATR indicators
├── strategy.py      # pure signal logic + position sizing (no IB dependency)
├── execution.py     # bracket construction, order routing, reconnect/backoff
├── pdt_tracker.py   # persistent day-trade journal + rolling 3-in-5 gate
├── main.py          # daily decision loop (runs ~10 min before the close)
├── requirements.txt
└── logs/            # bot.log + trade_journal.json (created at runtime)
```

## Setup

```bash
cd trading-bot
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## IBKR Paper Trading configuration

1. Log in to **IB Gateway** (or TWS) with your **paper** account.
2. Configure → Settings → API → Settings:
   - ✅ *Enable ActiveX and Socket Clients*
   - ❌ *Read-Only API* must be **unchecked** (the bot places orders)
   - Socket port:
     - **IB Gateway paper: `4002`** ← default in `config.py`
     - TWS paper: `7497` (change `ConnectionConfig.port` if you use TWS)
   - Trusted IP: add `127.0.0.1`
3. Live ports (`4001` gateway / `7496` TWS) — only after full validation,
   and only by editing `config.py` deliberately.

## Running

```bash
python main.py --once    # one decision cycle immediately (dry test)
python main.py           # scheduled loop: runs ~10 min before each close
```

With `dry_run = True` (default) the bot logs the exact bracket it *would*
send — symbol, share count, stop/limit/SL/TP prices — without transmitting.
Set `dry_run = False` in `config.py` to transmit to the paper account.

## PDT protection

Every fill is journaled to `logs/trade_journal.json` (atomic writes, survives
restarts). Before any new entry — and before any same-day liquidation — the
bot recounts round-trips in the rolling 5-business-day window and refuses
the order if it could become the 4th day trade. A corrupt journal fails
closed and is quarantined for manual reconciliation against IBKR's own
trade history.
