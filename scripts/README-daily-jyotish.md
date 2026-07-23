# Daily Jyotish Brief — 9 AM setup

A GitHub Action sends your daily brief at **09:00 Singapore time** via **ntfy**
(a free push app). It leads with your diplomacy anchor, then computes the day's
phase, numerology day-number, Rahu Kalam window, and the japa/remedy due.

Two one-time steps to make it live:

## 1. Subscribe in the ntfy app
1. Install **ntfy** (App Store / Play Store) and allow notifications.
2. Tap **+** → subscribe to a topic. Pick a **long, hard-to-guess name**, e.g.
   `ajeet-jyotish-7k3n9q2p4w` (ntfy topics are public if the name is known, so make it unguessable).

## 2. Add the topic as a repo secret
Repo → **Settings → Secrets and variables → Actions → New repository secret**:
- Name: `NTFY_TOPIC`
- Value: the exact topic name you subscribed to
- (optional) `NTFY_SERVER` if you self-host ntfy; otherwise it defaults to `https://ntfy.sh`.

## 3. Make it live
Scheduled Actions only run from the **default branch (`main`)**, so **merge this to main**
for the daily 9 AM push to start. Before merging you can test it any time:
**Actions tab → Daily Jyotish Brief → Run workflow**.

## Notes
- GitHub's scheduler can be a few minutes late (or occasionally skip under load) — normal.
- The brief is Prithvi's roadmap + numerology organised into a traffic-light; it's
  interpretive belief, not certainty. Health flags → see a doctor.
- To change wording/logic, edit `scripts/daily_jyotish.py`.
