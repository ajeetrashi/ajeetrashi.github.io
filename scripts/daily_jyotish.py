#!/usr/bin/env python3
"""Ajeet's daily Jyotish dashboard — computes today's reading (Singapore time)
and pushes it via ntfy. Astrology phase + numerology day-number merged, plus the
day's Rahu Kalam window. Traditional/interpretive guidance, not certainty.

Env:
  NTFY_TOPIC   (required) the ntfy topic you subscribe to in the ntfy app
  NTFY_SERVER  (optional) defaults to https://ntfy.sh
"""
import os
import sys
import datetime
import urllib.request
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")

# (start_date, rating, phase_name, do, avoid)
PHASES = [
    ("2026-01-01", "neutral", "Venus / Sun sub-period",      "introspect, review finances",      "impulsive spends, clashes"),
    ("2026-08-01", "caution", "Moon sub-period",             "protect sleep, do remedies",       "emotional overcommitment"),
    ("2026-09-18", "danger",  "Mars / Manglik",              "stay silent and calm",             "fights, risk, big spends, major decisions"),
    ("2026-10-06", "caution", "New year (Rahu-Sani still on)","year pujas, delegate conflict",    "confrontation, risk"),
    ("2026-11-06", "caution", "The Turn (Rahu-Budha begins)","look for openings; Narasimha yantra","neglecting spouse's health"),
    ("2026-12-09", "neutral", "Settling",                    "consolidate",                      "forcing outcomes"),
    ("2027-01-12", "good",    "Strongest run",               "launch, decide, ask, initiate",    "wasting the window"),
    ("2027-03-15", "good",    "Momentum",                    "push the big moves",               "coasting"),
    ("2027-04-23", "neutral", "Steady (dhaiya ends 10 Jun)", "follow-through, rebuild health",   "new big bets"),
    ("2027-07-21", "good",    "Second good window",          "expand, travel, property",         "overreach"),
    ("2027-09-07", "danger",  "Manglik close",               "keep quiet, finish check-ups",     "risk, investment, major decisions"),
    ("2027-10-06", "neutral", "New year - refresh due",      "ask Prithvi for the next-year chart", "assuming this map still applies"),
]

GOODFOR = {
    "good":    "starting new things, investing, big decisions, launches, travel",
    "neutral": "routine, follow-through, planning, meditation",
    "caution": "rest, meditation, reflection, finishing old tasks",
    "danger":  "rest, silence, prayer & meditation, doing nothing risky",
}
AVOID = {
    "good": "-", "neutral": "brand-new big commitments",
    "caution": "new ventures, risk, big spends",
    "danger": "any risk, investment, decision or confrontation",
}
EMOJI = {"good": "\U0001F7E2", "neutral": "⚪", "caution": "\U0001F7E0", "danger": "\U0001F534"}
WORD  = {"good": "GOOD", "neutral": "STEADY", "caution": "CAUTION", "danger": "DANGER"}

# Rahu Kalam fixed Singapore windows by weekday (Mon=0 .. Sun=6)
RAHU_KALAM = {
    0: ("08:36", "10:06"), 1: ("16:08", "17:39"), 2: ("13:07", "14:38"),
    3: ("14:38", "16:08"), 4: ("11:37", "13:07"), 5: ("10:06", "11:37"),
    6: ("17:39", "19:10"),
}


def reduce_num(n):
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def personal_year(d):
    if d < datetime.date(2026, 10, 14):
        return 7
    if d < datetime.date(2027, 10, 14):
        return 8
    return 9


def personal_day(d):
    return reduce_num(personal_year(d) + d.month + d.day)


def phase_for(d):
    cur = PHASES[0]
    for p in PHASES:
        if d >= datetime.date.fromisoformat(p[0]):
            cur = p
    return cur


def weekday_remedy(d):
    b = "Sri Rudram; \"Om Namah Shivaya\" x108; Hanuman Chalisa (evening)."
    w = d.weekday()
    if w == 0:
        b += " Mon: 40-day Shivalinga offering (bel-patra + white sandalwood)."
    if w == 3:
        b += " Thu eve: \"Klim Kamalatmike...\" x108."
    if w == 5:
        b += " Sat: lamp before Durga in Rahu Kalam + Durga Chalisa."
    if d >= datetime.date(2026, 11, 6):
        b += " Ongoing: Narasimha yantra."
    return b


def build_message(now):
    d = now.date()
    _, rating, name, do, avoid = phase_for(d)
    pd = personal_day(d)
    five = (pd == 5)
    if rating != "danger" and five:
        rating = "caution"

    rk = RAHU_KALAM[d.weekday()]
    long_date = now.strftime("%A %d %b %Y")
    lines = [
        f"{EMOJI[rating]} TODAY IS A {WORD[rating]} DAY — {long_date}",
        name + (" · numerology 5-day" if five else ""),
        f"GOOD FOR: {GOODFOR[rating]}",
        f"AVOID: {AVOID[rating]}",
        f"AVOID HOURS: Rahu Kalam {rk[0]}–{rk[1]} SGT (don't start/sign/commit)",
        f"REMEDY: {weekday_remedy(d)}",
    ]
    if rating == "danger" or five:
        lines.append("KEEP QUIET — NO RISK, NO INVESTMENT, NO MAJOR DECISION.")
    title = f"Jyotish - {WORD[rating]} day"
    priority = "urgent" if rating == "danger" else ("high" if rating == "caution" else "default")
    tags = "warning" if rating in ("danger", "caution") else "sparkles"
    return "\n".join(lines), title, priority, tags


def main():
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print("ERROR: NTFY_TOPIC secret is not set. Add it in repo Settings > Secrets and variables > Actions.", file=sys.stderr)
        return 1
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")

    now = datetime.datetime.now(SGT)
    body, title, priority, tags = build_message(now)
    print(body)

    req = urllib.request.Request(
        f"{server}/{topic}",
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": tags,
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Sent to {server}/{topic} -> HTTP {resp.status}")
    except Exception as e:  # noqa: BLE001
        print(f"ERROR sending to ntfy: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
