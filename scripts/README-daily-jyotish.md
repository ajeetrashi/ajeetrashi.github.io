# Daily Jyotish Brief — 9 AM setup

A GitHub Action sends your daily brief at **09:00 Singapore time** via **ntfy**
(a free push app). It leads with your diplomacy anchor, then computes the day's
phase, numerology day-number, Rahu Kalam window, and the japa/remedy due.

The ntfy topic is **baked into the script** (`DEFAULT_TOPIC` in
`scripts/daily_jyotish.py`), so **no repo secret is required.** Two steps:

## 1. Subscribe in the ntfy app
Install **ntfy** (App Store / Play Store), allow notifications, tap **+**, and
subscribe to the exact topic in `DEFAULT_TOPIC` (currently
`ajeet-jyotish-2f8k3m9q`).

## 2. Make it live
Scheduled Actions only run from the **default branch (`main`)**, so **merge this to main**.
The push then fires daily at 09:00 SGT. Test any time (needs the desktop site):
**Actions tab → Daily Jyotish Brief → Run workflow**.

## Notes
- The topic name lives in a public repo, so treat the brief as non-private. To make
  it private instead, remove `DEFAULT_TOPIC`, set an `NTFY_TOPIC` repo secret, and it
  will override the default.
- GitHub's scheduler can be a few minutes late (or occasionally skip under load) — normal.
- Interpretive guidance, not certainty. Health flags → see a doctor.
- To change wording/logic or the topic, edit `scripts/daily_jyotish.py`.
