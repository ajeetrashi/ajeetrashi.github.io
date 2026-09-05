# ajeetrashi.github.io

Personal automation workspace, served at **https://ajeetrashi.github.io**.

## Projects

### Health Automation Scheduler (`/` — the live site)

A dependency-free vanilla HTML/CSS/JS single-page app for daily health
tracking: a time-blocked daily checklist, protocol library, biomarker log,
and Oura Ring integration (sleep, readiness, activity — synced client-side
with a personal Oura API token entered in Settings). All data stays in the
browser's `localStorage`; nothing is sent to any server except the Oura API.

### Pullback-Momentum Trading Bot (`/trading-bot`)

An automated IBKR swing-trading bot (Python + `ib_async`) implementing a
mean-reversion-in-an-uptrend strategy, built for a sub-$25k account with a
Pattern Day Trader guard. Ships with `dry_run=True` and the paper-trading
port by default. See [`trading-bot/README.md`](trading-bot/README.md) for
strategy parameters, setup, and safety notes. Not financial advice.

## Development

No build step, no framework, no CI. The root site deploys automatically via
GitHub Pages on every push to `main`. Work happens on feature branches via
pull requests — much of it written with [Claude Code](https://claude.com/claude-code);
see [`CLAUDE.md`](CLAUDE.md) for the conventions those sessions follow.
