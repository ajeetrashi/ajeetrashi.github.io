# CLAUDE.md

Context for Claude Code sessions working in this repository. Read this before
exploring — it saves you the archaeology.

## Who and what this repo is

This is Ajeet's personal GitHub Pages repo (`ajeetrashi.github.io`). It is a
**multi-project workspace**, not a single app. Ajeet uses Claude Code (usually
remote/web sessions) to build and maintain personal automation tools here.
Active areas of work: health tracking, IBKR swing trading, and personal
productivity tooling.

## Repository map

| Path | What it is |
|---|---|
| `index.html`, `css/`, `js/` | **Health Automation Scheduler** — the live site at https://ajeetrashi.github.io. Vanilla HTML/CSS/JS single-page app (no framework, no build step). Tabs: Today checklist, Protocols, Biomarkers, Oura Ring, Settings. All state lives in `localStorage`; the Oura tab calls the Oura v2 API directly from the browser with a personal token the user pastes in Settings (stored in `localStorage`, never in this repo). |
| `trading-bot/` | **Pullback-Momentum IBKR swing-trading bot** (Python, `ib_async`). Mean-reversion-in-uptrend strategy for a sub-$25k account with a Pattern Day Trader guard. Has its own thorough `README.md` — read it before touching strategy or execution code. `dry_run=True` and the paper-trading port are the defaults; **never change those defaults in a commit**. Runs on Ajeet's own machine (Singapore timezone; IBKR account base currency is SGD), not in CI. |

Deleted history you should NOT resurrect: a daily Jyotish (Vedic astrology)
GitHub Action + ntfy notifier, and a client-confidential prototype. Both were
deliberately removed.

## Deployment

- GitHub Pages serves the **repo root** from `main`. Anything merged to `main`
  is live at https://ajeetrashi.github.io within a minute or two.
- `.nojekyll` is present: the site is plain static files, no Jekyll.
- There is no test suite, linter, or CI. Verify frontend changes by opening
  `index.html` locally (or a quick `python3 -m http.server`); verify
  trading-bot changes with `python main.py --once` in dry-run (needs an IB
  Gateway connection, so usually reason through the code instead).

## Working conventions

- Work on a feature branch, push, open a **draft PR** to `main`. Ajeet merges.
- Keep the Health Scheduler dependency-free vanilla JS — no frameworks or
  build tooling unless explicitly asked.
- The trading bot separates concerns deliberately: `strategy.py` is pure logic
  with no IB dependency; keep it that way so it stays reasoning-friendly.

## Standing safety rules (learned the hard way — see git history)

1. **Never commit secrets, tokens, API keys, or ntfy topics** — not even
   "harmless" ones baked into scripts. This has required history scrubbing
   before. Secrets belong in GitHub Actions secrets, local env vars, or
   `localStorage` (frontend), never in tracked files.
2. **Never commit client or third-party confidential material.** This repo is
   public; everything in it is world-readable, including history.
3. Trading-bot changes must preserve the safety defaults: `dry_run=True`,
   paper port `4002`, the PDT journal gate, and the 1.5%-of-NLV risk cap.
   Flipping any of these is a manual, deliberate act by Ajeet only.
4. The live site is Ajeet's daily health tool — don't break `localStorage`
   key names or stored-data shapes without a migration, or his tracked data
   silently disappears.
