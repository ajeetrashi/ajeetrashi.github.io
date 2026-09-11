# AI Recommendations — Trading Playbook

Distilled from live Claude-assisted IBKR trading sessions (Aug–Sep 2026).
This file deliberately contains **no account values, position sizes, P&L
figures, or personal data** — this repo is public. It records the *rules*
those sessions paid to learn, so future sessions (human or AI) start from
them instead of rediscovering them.

These rules are consistent with the pullback-momentum bot in this directory
(`strategy.py`, `config.py`): signal-based entries, pre-defined exits, hard
risk caps. Where they conflict with an impulse, the rules win.

## The one-line summary

Across every week measured: **entries taken on a pre-defined signal with
exits already in the market were consistently profitable; entries taken
on demand ("find me a trade today") or held past a broken stop were
consistently not.** The picks were rarely the problem. The exits were.

## Entry rules

1. **Trade signals, not moods.** An entry needs a level that fired (breakout,
   pullback-to-support, gap-reclaim) — defined *before* price got there.
   "I want a trade today" is not a signal; scanning until something looks
   tradable is how the losing entries happened.
2. **Never enter to recover a loss.** Loss-recovery sizing ("make back X
   today") preceded every major drawdown episode. The market does not know
   the account is down.
3. **Don't chase.** If price has gapped or run meaningfully past the trigger
   level, the trade is gone. The edge was the level, not the ticker.
4. **No averaging down.** Adding to a loser below its stop level turned small
   planned losses into the largest ones on record. Adding is permitted only
   to a *winning* position on a fresh confirmation signal, at reduced size.

## Exit rules

5. **Both exits go into the market with the entry** — a limit at the target
   and a stop (real stop order, not an alert, not a mental level). Every
   trade run this way closed at plan; every "I'll watch it" eventually
   didn't get watched.
6. **A broken stop level is an exit, not a discussion.** The question "if I
   close, do I book a loss?" has one answer: the loss already exists;
   closing only stops it growing. Delay was billed by the hour.
7. **Don't move targets away from price** (raising a sell as price
   approaches) **and don't move stops away from price** (lowering them to
   "give it room"). Both behaviors are on the record and both cost money.
   One deliberate, pre-planned target adjustment on a *winning* trend
   position is acceptable; re-negotiating every day is not.
8. **Winners get harvested at their level.** Two separate round trips —
   a position at target left unbanked, then ridden back down — were among
   the most expensive lessons. If the plan says exit, exit.

## Sizing and account limits

9. **Risk per trade: 1–2% of net liquidation value**, defined as
   (entry − stop) × size. This matches the bot's risk cap in `config.py`.
10. **Leverage ceiling: 1.5x gross positions / NLV.** The account visited
    ~3x three times; each visit ended within hours of forced liquidation,
    where the broker picks the exit price. Platform buying power is not a
    suggestion to use it.
11. **Keep dry powder.** A fully-deployed account cannot take the next real
    signal — and the next real signal is worth more than the current
    impulse position.
12. **Concentration:** avoid two highly-correlated positions being most of
    gross exposure; they move as one trade with double the risk.

## Order-handling hygiene (the click-error tax)

The most expensive mistakes were not market calls — they were order
mechanics. Each item below is a real incident class:

13. **Verify the position before submitting any exit.** A stale sell
    instruction submitted after the shares were already sold created an
    accidental short. Instructions are snapshots; positions change.
14. **One position, one exit path.** Cancel the old order *before* (or
    immediately after) placing its replacement. Duplicate working sells =
    accidental short on a rally; duplicate covers = accidental long.
15. **Cancel orphan orders the moment a position closes.** A GTC sell with
    no position behind it is a landmine, not a leftover.
16. **Match order size to position size** after partial exits — a stop for
    the original quantity oversells the remainder.
17. **After any batch of order changes, re-read the open-orders list** and
    confirm it shows exactly the intended lines — nothing more, nothing
    less. Every multi-order accident would have been caught by this check.
18. **Overnight/extended sessions:** day orders don't work there, GTC limits
    don't execute there by default, and thin quotes lie. Match the
    time-in-force to when the exit must be able to fire.

## Instruments

19. **New asset classes are earned, not reached for.** Futures (23-hour,
    levered, broker-enforced liquidation) amplify every weakness above.
    The ladder is: plain ETF → micro contract → full contract, each step
    only after the previous one has been traded with exits in place.
20. **Short-dated long options** need direction *and* timing *and* speed;
    the account's own history with them is negative. Defined-risk spreads
    only, sized to the premium, and never as loss recovery.

## Working with an AI session

21. The assistant stages instructions; **the human's submit click is the
    last safety check, not a formality.** Read what's being submitted.
22. "Voice concerns once, then execute" is the agreed protocol — but a
    concern voiced and overridden goes on the scorecard either way. The
    scorecard, not the feeling, is the referee.
23. Keep alerts armed on every open position's stop level as a backstop,
    but an alert is a notification, not an exit. Only orders act.
