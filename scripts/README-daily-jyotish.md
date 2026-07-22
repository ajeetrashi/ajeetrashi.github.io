# Daily Jyotish Push — setup

A GitHub Action sends your daily reading at **07:00 Singapore time** via **ntfy**
(a free push app). Two things to do once:

## 1. Subscribe in the ntfy app
1. Install **ntfy** (App Store / Play Store).
2. Tap **+** → subscribe to a topic. Pick a **long, hard-to-guess name**, e.g.
   `ajeet-jyotish-7k3n9q2p4w` (ntfy topics are public if the name is known, so make it unguessable).

## 2. Add the topic as a repo secret
In this repo → **Settings → Secrets and variables → Actions → New repository secret**:
- Name: `NTFY_TOPIC`
- Value: the exact topic name you subscribed to
- (optional) `NTFY_SERVER` if you self-host ntfy; otherwise it defaults to `https://ntfy.sh`.

## 3. Make it live
Scheduled Actions only run from the **default branch (`main`)**, so **merge this PR** for the
daily 7 AM push to start. Before merging you can test it: **Actions tab → Daily Jyotish Push →
Run workflow**.

## Notes
- GitHub's scheduler can be a few minutes late (or occasionally skip under load) — normal.
- The reading is Prithvi's + numerology guidance organised into a traffic-light; it's
  interpretive belief, not certainty. Health flags → see a doctor.
- To change wording/logic, edit `scripts/daily_jyotish.py`.
