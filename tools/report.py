#!/usr/bin/env python3
"""Say what a change to the data adds for one queue, EB-2 rest of world: a title line, a blank
line, then a Markdown body.

Usage:  python3 tools/report.py --since REV [--mention USER]
        python3 tools/report.py --month YYYY-MM [--mention USER]

--since compares site/data.json at git revision REV with the working tree. It reports each
bulletin month added after REV's newest, with how the queue's two cutoffs moved against the
month before, and the chart USCIS named for REV's newest month if it had none (months added
before it, as in a backfill, aren't news). --month reports that one
bulletin as if it had just been added. Prints nothing when there is nothing to report. The
Notify workflow (.github/workflows/notify.yml) opens an issue from the output, which GitHub
emails to the owner.
"""
import argparse
import calendar
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://ulysses4ever.github.io/vb/"
# The one queue the notifications follow.
CATEGORY, COUNTRY, QUEUE = "EB-2", "ROW", "EB-2 rest of world"
CHARTS = {"filing": "Dates for Filing", "final": "Final Action Dates"}


def bulletins(rev=None):
    """site/data.json's bulletins by month, at a git revision or (None) in the working tree."""
    if rev is None:
        text = (ROOT / "site" / "data.json").read_text()
    else:
        text = subprocess.run(["git", "show", f"{rev}:site/data.json"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout
    return {b["month"]: b for b in json.loads(text)["bulletins"]}


def name(month):
    y, m = map(int, month.split("-"))
    return f"{calendar.month_name[m]} {y}"


def code(v):
    """A cutoff as the bulletin prints it: 01JAN25, C or U."""
    if v in ("C", "U"):
        return v
    d = dt.date.fromisoformat(v)
    return f"{d.day:02d}{calendar.month_abbr[d.month].upper()}{d.year % 100:02d}"


def move(old, new):
    if old is None or old == new:
        return code(new)
    if "C" in (old, new) or "U" in (old, new):
        return f"{code(old)} → {code(new)}"
    days = (dt.date.fromisoformat(new) - dt.date.fromisoformat(old)).days
    size = f"{days:+d} days" if abs(days) < 60 else f"{days / 30.436875:+.1f}".removesuffix(".0") + " months"
    return f"{code(old)} → {code(new)} ({size})"


def cutoff(b, table):
    return b.get(table, {}).get(CATEGORY, {}).get(COUNTRY)


def chart(b):
    """The chart USCIS takes for the month, and so who in the queue can file."""
    if b.get("uscis_chart") not in CHARTS:
        return f"USCIS hasn't named its chart for {name(b['month'])} yet; another issue will say when it does."
    source = f" ([source]({b['uscis_source']}))" if b.get("uscis_source") else ""
    v = cutoff(b, b["uscis_chart"])
    who = ("" if v is None else f", so {QUEUE} can file with any priority date" if v == "C"
           else f", so {QUEUE} can't file this month" if v == "U"
           else f", so {QUEUE} can file with a priority date before **{code(v)}**")
    return f"USCIS takes **{CHARTS[b['uscis_chart']]}** for I-485s filed in {name(b['month'])}{source}{who}."


def section(b, prev):
    lines = [f"The [{name(b['month'])} Visa Bulletin]({b['url']}) is on the [tracker]({SITE}).", "",
             f"{QUEUE}:", ""]
    for table, label in (("final", "Final action"), ("filing", "Dates for filing")):
        old, new = cutoff(prev, table) if prev else None, cutoff(b, table)
        if new is None:
            lines.append(f"- {label}: not in this bulletin")
        else:
            lines.append(f"- {label}: {move(old, new)}" + (" (no change)" if prev and old == new else ""))
    return lines + ["", chart(b)]


def main():
    ap = argparse.ArgumentParser()
    which = ap.add_mutually_exclusive_group(required=True)
    which.add_argument("--since", metavar="REV")
    which.add_argument("--month", metavar="YYYY-MM")
    ap.add_argument("--mention", metavar="USER")
    args = ap.parse_args()

    now = bulletins()
    months = sorted(now)
    if args.month:
        if args.month not in now:
            sys.exit(f"no bulletin for {args.month} in site/data.json")
        added, charted = [args.month], []
    else:
        try:
            old = bulletins(args.since)
        except subprocess.CalledProcessError:
            print(f"can't read site/data.json at {args.since}; nothing to report", file=sys.stderr)
            return
        # Only what's newer than the newest month before: a backfill of older months is not news.
        newest = max(old)
        added = [m for m in months if m > newest]
        charted = [m for m in months if m == newest and now[m].get("uscis_chart") in CHARTS
                   and now[m]["uscis_chart"] != old[m].get("uscis_chart")]
    if not added and not charted:
        return

    body = []
    for m in added:
        i = months.index(m)
        if len(added) > 1:
            body += [f"### {name(m)}", ""]
        body += section(now[m], now[months[i - 1]] if i else None) + [""]
    for m in charted:
        body += [chart(now[m]), ""]
    if not added:
        body.append(f"The [tracker]({SITE}) shows it now.")
    if args.mention and body[0].startswith("#"):
        body = [f"@{args.mention}", ""] + body
    elif args.mention:
        body[0] = f"@{args.mention} {body[0]}"
    if added:
        title = f"Visa Bulletin for {name(added[-1])}: {QUEUE}"
    else:
        title = f"USCIS: {CHARTS[now[charted[-1]]['uscis_chart']]} for {name(charted[-1])}"
    print(title, "", "\n".join(body).strip(), sep="\n")


if __name__ == "__main__":
    main()
