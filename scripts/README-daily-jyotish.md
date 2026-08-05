# Daily Jyotish Brief — 9 AM setup

A GitHub Action sends your daily brief at **09:00 Singapore time** via **ntfy**
(a free push app). It leads with your diplomacy anchor, then computes the day's
phase, numerology day-number, Rahu Kalam window, and the japa/remedy due.

The ntfy topic must be set as a **repo secret** (`NTFY_TOPIC`) — it is not
baked into the script. ntfy.sh topics are unauthenticated: anyone who knows
the topic name can read your brief or push spoofed notifications to it, so
the topic name must never be committed to the repo.

## 1. Pick a topic name
Generate something long and random (not a guessable slug) — e.g.
`openssl rand -hex 16`. Do not commit it anywhere.

## 2. Add the topic as a repo secret
Repo → **Settings → Secrets and variables → Actions → New repository secret**:
- Name: `NTFY_TOPIC`
- Value: the topic name from step 1

## 3. Subscribe in the ntfy app
Install **ntfy** (App Store / Play Store), allow notifications, tap **+**, and
subscribe to that same topic name.

## 4. Make it live
Scheduled Actions only run from the **default branch (`main`)**, so **merge this to main**.
The push then fires daily at 09:00 SGT. Test any time (needs the desktop site):
**Actions tab → Daily Jyotish Brief → Run workflow**.

## Notes
- If the topic is ever exposed (committed, shared, screenshotted), rotate it —
  generate a new random value, update the repo secret, and resubscribe in the app.
- GitHub's scheduler can be a few minutes late (or occasionally skip under load) — normal.
- Interpretive guidance, not certainty. Health flags → see a doctor.
- To change wording/logic, edit `scripts/daily_jyotish.py`.
