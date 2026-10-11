#!/usr/bin/env python3
"""Add the Visa Bulletin months data/ doesn't have yet, then rebuild site/data.json.

Usage:  python3 tools/update.py

travel.state.gov turns away automated clients (Cloudflare answers 403), so cutoffs come from
armanckeser/visa-bulletin-data, a CC0 dataset that caches each bulletin page and parses it.
Before anything is imported, every month already in data/bulletins is compared with the
dataset cell by cell, and any difference stops the run: the dataset or its parser has changed.
On 2026-10-11 all 4,900 cells of 2022-10 to 2026-10 matched.

The chart USCIS takes comes from USCIS's own page, which names it for the current month and
sometimes the next. A month that page no longer shows falls back to the dataset's weekly
record of the same page. A recorded chart is never overwritten; if the USCIS page contradicts
one, the run stops.

Exit status: 0 when data/ has the current month's bulletin; 3 when the dataset doesn't have
it yet (whatever it does have is still imported); 1 on any other problem.
"""
import calendar
import datetime as dt
import html
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BULLETINS = ROOT / "data" / "bulletins"
CHARTS_FILE = ROOT / "data" / "uscis_chart.json"

DATASET = "https://github.com/armanckeser/visa-bulletin-data"
DATASET_RAW = "https://raw.githubusercontent.com/armanckeser/visa-bulletin-data/main/data/"
USCIS = ("https://www.uscis.gov/green-card/green-card-processes-and-procedures/"
         "visa-availability-priority-dates/adjustment-of-status-filing-charts-from-the-visa-bulletin")
BULLETIN = ("https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin/"
            "{fy}/visa-bulletin-for-{name}-{year}.html")

# Dataset category code -> ours, in the order the bulletin files list them.
CATEGORIES = {
    "EB1": "EB-1", "EB2": "EB-2", "EB3": "EB-3", "EW": "EB-3 Other", "EB4": "EB-4",
    "EB4_RW": "EB-4 Religious", "EB5_UNRESERVED": "EB-5 Unreserved", "EB5_RURAL": "EB-5 Rural",
    "EB5_HIGH_UNEMPLOYMENT": "EB-5 High Unemployment", "EB5_INFRASTRUCTURE": "EB-5 Infrastructure",
}
# The dataset files today's "5th Unreserved" row under EB5_UNRESERVED_I5_R5, though its README
# keeps that code for May 2022, when the row was split in two. Either code is taken; a month
# that has both is ambiguous.
UNRESERVED = ("EB5_UNRESERVED", "EB5_UNRESERVED_I5_R5")
COUNTRIES = ("ROW", "CN", "IN", "MX", "PH")
CHARTS = {"final_action": "final", "dates_for_filing": "filing"}
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
USCIS_RE = re.compile(
    r"employment-based preference categories, you (?:must|may|should) use the "
    r"(Dates for Filing|Final Action Dates?) chart in the (?:U\.S\. )?Department of State "
    r"Visa Bulletin for ([A-Za-z]+) (\d{4})", re.I)


class Stop(Exception):
    pass


def next_month(m):
    y, mo = map(int, m.split("-"))
    return f"{y + (mo == 12):04d}-{mo % 12 + 1:02d}"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "vb-update (+https://github.com/ulysses4ever/vb)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def dataset_bulletins():
    """{month: {"final": {category: {country: value}}, "filing": ...}}, or None for an ambiguous month."""
    out, codes = {}, {}
    for r in json.loads(fetch(DATASET_RAW + "visa_bulletin.json")):
        code, mo = r["category"], r["bulletin"]
        if r["kind"] != "employment" or r["country"] not in COUNTRIES:
            continue
        if code in UNRESERVED:
            codes.setdefault(mo, set()).add(code)
            code = "EB5_UNRESERVED"
        if code not in CATEGORIES:
            continue
        value = {"current": "C", "unavailable": "U"}.get(r["status"], r["date"])
        table = out.setdefault(mo, {"final": {}, "filing": {}})[CHARTS[r["chart"]]]
        table.setdefault(CATEGORIES[code], {})[r["country"]] = value
    out.update({mo: None for mo, seen in codes.items() if len(seen) > 1})
    return out


def canonical(b, mo):
    """The bulletin with every category and country, in file order; stops if any is missing."""
    try:
        return {t: {cat: {c: b[t][cat][c] for c in COUNTRIES} for cat in CATEGORIES.values()}
                for t in ("final", "filing")}
    except KeyError as e:
        raise Stop(f"{mo}: the dataset has no value for {e}") from None


def dump(b):
    """A bulletin file in the layout most of data/bulletins uses: one line per category."""
    lines = [f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in b.items() if k not in ("final", "filing")]
    for t in ("final", "filing"):
        rows = ",\n".join(f"    {json.dumps(cat)}: {json.dumps(row)}" for cat, row in b[t].items())
        lines.append(f"  {json.dumps(t)}: {{\n{rows}\n  }}")
    return "{\n" + ",\n".join(lines) + "\n}\n"


def check_history(ours, theirs):
    diffs = []
    for mo, b in ours.items():
        if not theirs.get(mo):
            diffs.append(f"{mo}: {'ambiguous' if mo in theirs else 'missing'} in the dataset")
            continue
        for table in ("final", "filing"):
            for cat, row in b[table].items():
                for c, v in row.items():
                    got = theirs[mo][table].get(cat, {}).get(c)
                    if got != v:
                        diffs.append(f"{mo} {table} {cat} {c}: ours {v}, dataset {got}")
    if diffs:
        more = f"\n  ... and {len(diffs) - 20} more" if len(diffs) > 20 else ""
        raise Stop("the dataset no longer matches data/bulletins, so nothing was imported:\n  "
                   + "\n  ".join(diffs[:20]) + more)


def uscis_charts():
    """{month: {"filing" | "final", ...}} as the USCIS page states it for employment-based filings."""
    text = re.sub(r"(?s)<(script|style)\b.*?</\1>", " ", fetch(USCIS))
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)))
    found = {}
    for chart, name, year in USCIS_RE.findall(text):
        if name.lower() in MONTHS:
            mo = f"{int(year):04d}-{MONTHS[name.lower()]:02d}"
            found.setdefault(mo, set()).add("filing" if chart.lower().startswith("dates") else "final")
    if not found:
        raise ValueError("no employment-based chart found; the page may have changed")
    return found


def main():
    ours = {f.stem: json.loads(f.read_text()) for f in sorted(BULLETINS.glob("*.json"))}
    theirs = dataset_bulletins()
    check_history(ours, theirs)
    print(f"the dataset matches all {len(ours)} months in data/bulletins")

    new, mo = [], next_month(max(ours))
    while mo in theirs:
        if theirs[mo] is None:
            raise Stop(f"{mo}: the dataset has both EB-5 unreserved rows")
        new.append(mo)
        mo = next_month(mo)
    files = {}
    for mo in new:
        y, m = map(int, mo.split("-"))
        url = BULLETIN.format(fy=y + (m >= 10), name=calendar.month_name[m].lower(), year=y)
        files[mo] = {"month": mo, "url": url, "source": DATASET, **canonical(theirs[mo], mo)}

    charts = json.loads(CHARTS_FILE.read_text())
    before = json.dumps(dict(sorted(charts.items())), indent=1, ensure_ascii=False)
    try:
        page = uscis_charts()
    except (OSError, ValueError) as e:
        page = {}
        print(f"warning: couldn't read the USCIS page: {e}", file=sys.stderr)
    try:
        recorded = json.loads(fetch(DATASET_RAW + "uscis_chart.json"))
    except (OSError, ValueError) as e:
        recorded = {}
        print(f"warning: couldn't read the dataset's USCIS record: {e}", file=sys.stderr)
    for mo in sorted([*ours, *new]):
        have, said = (charts.get(mo) or {}).get("chart"), page.get(mo, set())
        if len(said) > 1:
            raise Stop(f"{mo}: the USCIS page names both charts")
        said = next(iter(said), None)
        if have and said and have != said:
            raise Stop(f"{mo}: data/uscis_chart.json has {have}, but the USCIS page now says {said}")
        if have:
            continue
        if said:
            charts[mo] = {"chart": said, "source": USCIS}
        elif (rec := (recorded.get(mo) or {}).get("employment")) in CHARTS:
            charts[mo] = {"chart": CHARTS[rec], "source": f"{DATASET}/blob/main/data/uscis_chart.json"}
    after = json.dumps(dict(sorted(charts.items())), indent=1, ensure_ascii=False)

    for mo, b in files.items():
        (BULLETINS / f"{mo}.json").write_text(dump(b))
        print(f"added {mo}; USCIS chart: {(charts.get(mo) or {}).get('chart') or 'not named yet'}")
    if after != before:
        CHARTS_FILE.write_text(after)
        print("updated data/uscis_chart.json")
    if files or after != before:
        sys.stdout.flush()  # keep this run's lines ahead of the build's in a log
        if subprocess.run([sys.executable, str(ROOT / "tools" / "build_data.py")]).returncode:
            raise Stop("tools/build_data.py rejected the update")
    else:
        print(f"nothing new; the latest bulletin is {max(ours)}")

    current = dt.date.today().strftime("%Y-%m")
    if max([*ours, *new]) < current:
        print(f"the dataset has no bulletin for {current} yet", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Stop, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
