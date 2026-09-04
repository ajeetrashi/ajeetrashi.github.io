# Daily Jyotish Brief — setup

A GitHub Action sends a daily brief to your phone (~9 AM Singapore) via **ntfy**
(a free push app). Each brief leads with your diplomacy anchor, then computes the
day's phase, numerology day-number, Rahu Kalam window, and the japa/remedy due.

The ntfy topic is **read from a repo secret** — nothing is hardcoded (this is a
public repo). One secret to check, then it runs itself.

## 1. Subscribe in the ntfy app
Install **ntfy**, allow notifications, tap **+**, and subscribe to a long,
hard-to-guess topic name (e.g. `ajeet-jyotish-7k3n9q2p4w`).

## 2. Add the topic as a repo secret
Repo → **Settings → Secrets and variables → Actions → New repository secret**:
- Name: `NTFY_TOPIC`
- Value: the exact topic you subscribed to (case-sensitive)
- (optional) `NTFY_SERVER` if self-hosting ntfy; otherwise it defaults to `https://ntfy.sh`

## 3. It's live
Runs daily from `main`. Test any time (needs the desktop site):
**Actions tab → Daily Jyotish Brief → Run workflow**.

## Notes
- If `NTFY_TOPIC` is not set, the run is a harmless no-op (it prints a notice and
  succeeds) — it will not spam failure emails.
- GitHub's scheduler can be 20-60 min late, or skip under load — normal.
- Interpretive guidance, not certainty. Health flags → see a doctor.
- To change wording/logic, edit `scripts/daily_jyotish.py`.
