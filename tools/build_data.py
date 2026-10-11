#!/usr/bin/env python3
"""Build site/data.json from data/bulletins/*.json and data/uscis_chart.json.

Usage:  python3 tools/build_data.py [--generated YYYY-MM-DD]

Inputs (relative to the repo root):
  data/bulletins/YYYY-MM.json  one file per Visa Bulletin month:
      {"month": "2026-10", "url": "<bulletin url>",
       "final":  {"EB-2": {"ROW": "2025-01-01", ...}, ...},
       "filing": {"EB-2": {"ROW": "2026-03-15", ...}, ...}}
  data/uscis_chart.json        {"2026-10": {"chart": "filing" | "final" | null, "source": "<url>"}, ...}

Checks (exit 1 on any problem): month keys, value format (C, U or a real ISO date),
Dates for Filing never earlier than Final Action, a USCIS chart recorded for every month,
no missing months, and spot checks against values confirmed from independent sources.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
VALUE_RE = re.compile(r"^(C|U|\d{4}-\d{2}-\d{2})$")

# (month, table, category, country) -> value, each confirmed against a source other than
# the bulletin extract (law-firm or university summaries of that month's bulletin; 2023-07
# EB-2 ROW filing was re-read directly from the State Department page).
SPOT_CHECKS = {
    ("2022-10", "final", "EB-2", "IN"): "2012-04-01", ("2022-12", "final", "EB-2", "IN"): "2011-10-08",
    ("2022-12", "final", "EB-2", "CN"): "2019-06-08", ("2023-04", "final", "EB-2", "ROW"): "2022-07-01",
    ("2023-05", "final", "EB-2", "ROW"): "2022-02-15", ("2023-05", "final", "EB-3", "ROW"): "2022-06-01",
    ("2023-05", "final", "EB-2", "IN"): "2011-01-01", ("2023-05", "final", "EB-3 Other", "CN"): "2015-04-15",
    ("2023-07", "final", "EB-3", "ROW"): "2022-02-01", ("2023-07", "final", "EB-3", "IN"): "2009-01-01",
    ("2023-07", "filing", "EB-2", "ROW"): "2022-12-01", ("2024-01", "final", "EB-2", "IN"): "2012-03-01",
    ("2024-04", "final", "EB-2", "CN"): "2020-02-01", ("2024-07", "final", "EB-2", "ROW"): "2023-03-15",
    ("2024-07", "filing", "EB-2", "ROW"): "2023-03-22", ("2024-08", "final", "EB-2", "IN"): "2012-07-15",
    ("2024-12", "final", "EB-2", "ROW"): "2023-03-15", ("2024-12", "filing", "EB-2", "ROW"): "2023-08-01",
    ("2024-12", "final", "EB-1", "CN"): "2022-11-08", ("2024-12", "filing", "EB-3", "ROW"): "2023-03-01",
    ("2025-01", "final", "EB-2", "CN"): "2020-04-22", ("2025-01", "final", "EB-3", "ROW"): "2022-12-01",
    ("2025-03", "final", "EB-2", "ROW"): "2023-05-15", ("2025-03", "final", "EB-2", "CN"): "2020-05-08",
    ("2025-03", "final", "EB-2", "IN"): "2012-12-01", ("2025-03", "final", "EB-3", "CN"): "2020-08-01",
    ("2025-06", "final", "EB-2", "ROW"): "2023-10-15", ("2025-06", "filing", "EB-2", "ROW"): "2023-11-15",
    ("2025-06", "final", "EB-3", "ROW"): "2023-02-08", ("2025-08", "final", "EB-2", "ROW"): "2023-09-01",
    ("2025-08", "final", "EB-3", "IN"): "2013-05-22", ("2025-12", "final", "EB-2", "ROW"): "2024-02-01",
    ("2025-12", "final", "EB-2", "IN"): "2013-05-15", ("2025-12", "final", "EB-3", "ROW"): "2023-04-15",
    ("2026-02", "final", "EB-3", "ROW"): "2023-06-01", ("2026-03", "final", "EB-2", "ROW"): "2024-10-15",
    ("2026-03", "filing", "EB-2", "ROW"): "C", ("2026-03", "filing", "EB-3", "ROW"): "2024-01-15",
    ("2026-06", "final", "EB-2", "IN"): "2013-09-01", ("2026-06", "final", "EB-3", "ROW"): "2024-06-01",
    ("2026-07", "final", "EB-2", "IN"): "U", ("2026-07", "final", "EB-3", "CN"): "2021-12-22",
    ("2026-10", "final", "EB-2", "ROW"): "2025-01-01", ("2026-10", "filing", "EB-2", "ROW"): "2026-03-15",
    ("2026-10", "final", "EB-3 Other", "ROW"): "2022-01-01", ("2026-10", "filing", "EB-2", "IN"): "2015-01-15",
    ("2026-10", "filing", "EB-5 Unreserved", "CN"): "2021-03-01", ("2026-10", "filing", "EB-4", "ROW"): "2025-01-01",
}


def next_month(m):
    y, mo = map(int, m.split("-"))
    return f"{y + (mo == 12):04d}-{mo % 12 + 1:02d}"


def fmt(o, ind=0):
    """Pretty JSON with each innermost country map on one line."""
    pad = " " * ind
    if isinstance(o, dict):
        if ind >= 3 and all(not isinstance(v, (dict, list)) for v in o.values()):
            return "{" + ", ".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in o.items()) + "}"
        return "{\n" + ",\n".join(f"{pad} {json.dumps(k)}: {fmt(v, ind + 1)}" for k, v in o.items()) + "\n" + pad + "}"
    if isinstance(o, list):
        return "[\n" + ",\n".join(f"{pad} {fmt(v, ind + 1)}" for v in o) + "\n" + pad + "]"
    return json.dumps(o, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generated", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    args = ap.parse_args()

    uscis = json.loads((ROOT / "data" / "uscis_chart.json").read_text())
    problems, bulletins = [], []
    for f in sorted((ROOT / "data" / "bulletins").glob("*.json")):
        d = json.loads(f.read_text())
        mo = d.get("month")
        if mo != f.stem or not MONTH_RE.match(mo or ""):
            problems.append(f"{f.name}: month field {mo!r} does not match the file name")
            continue
        for table in ("final", "filing"):
            for cat, row in d.get(table, {}).items():
                for c, v in row.items():
                    if not VALUE_RE.match(v):
                        problems.append(f"{mo} {table} {cat} {c}: bad value {v!r}")
                    elif v not in ("C", "U"):
                        try:
                            dt.date.fromisoformat(v)
                        except ValueError:
                            problems.append(f"{mo} {table} {cat} {c}: impossible date {v!r}")
        for cat, row in d.get("final", {}).items():
            for c, fa in row.items():
                df = d.get("filing", {}).get(cat, {}).get(c)
                if not df or "U" in (fa, df):
                    continue
                if fa == "C" and df != "C":
                    problems.append(f"{mo} {cat} {c}: final action is C but filing is {df}")
                elif fa != "C" and df != "C" and df < fa:
                    problems.append(f"{mo} {cat} {c}: filing {df} is earlier than final {fa}")
        u = uscis.get(mo) or {}
        if u.get("chart") not in ("filing", "final"):
            problems.append(f"{mo}: no USCIS chart recorded in data/uscis_chart.json")
        bulletins.append({
            "month": mo,
            "url": d.get("url"),
            "uscis_chart": u.get("chart"),
            "uscis_source": u.get("source"),
            "final": d.get("final", {}),
            "filing": d.get("filing", {}),
        })

    for a, b in zip(bulletins, bulletins[1:]):
        if next_month(a["month"]) != b["month"]:
            problems.append(f"missing bulletin(s) between {a['month']} and {b['month']}")

    by = {b["month"]: b for b in bulletins}
    passed = 0
    for (mo, table, cat, c), want in SPOT_CHECKS.items():
        got = by.get(mo, {}).get(table, {}).get(cat, {}).get(c)
        if got == want:
            passed += 1
        else:
            problems.append(f"spot check {mo} {table} {cat} {c}: got {got}, expected {want}")

    data = {
        "description": "U.S. Visa Bulletin employment-based cutoff dates, with the chart USCIS designated for I-485 filing each month.",
        "generated": args.generated,
        "sources": {
            "cutoffs": "U.S. Department of State Visa Bulletin (url per month)",
            "uscis_chart": "USCIS 'Adjustment of Status Filing Charts from the Visa Bulletin', as quoted per month (uscis_source)",
        },
        "countries": {"ROW": "All chargeability areas except those listed", "CN": "China (mainland-born)",
                      "IN": "India", "MX": "Mexico", "PH": "Philippines"},
        "bulletins": bulletins,
    }
    out = ROOT / "site" / "data.json"
    out.write_text(fmt(data) + "\n")
    json.loads(out.read_text())
    print(f"{len(bulletins)} bulletins ({bulletins[0]['month']} to {bulletins[-1]['month']}), "
          f"spot checks {passed}/{len(SPOT_CHECKS)}, wrote {out.relative_to(ROOT)}")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
