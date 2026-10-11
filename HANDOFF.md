# Visa Bulletin Tracker: handoff

Written 2026-10-11 at the end of a claude.ai session. This folder is the source of truth; a private
preview of the same page also exists in the owner's claude.ai account.

## What it is

A static page (`site/index.html`) that reads `site/data.json` and shows, for any employment-based
category and country of chargeability:

- the latest bulletin's I-485 filing cutoff and final action cutoff, with a check of a priority date
  the viewer enters;
- a line chart of how many months each cutoff trailed its bulletin, with the months shaded where USCIS
  accepted the Dates for Filing chart;
- a table of every bulletin, linked to the State Department page and to the source for USCIS's chart choice.

No build step and no backend. Chart.js 4.4.1 loads from cdnjs; fonts load from Google Fonts.

## Status

- **Data:** 49 bulletins, October 2022 to October 2026. All employment-based categories for ROW, CN, IN,
  MX and PH, in both charts. USCIS's chart choice is recorded for all 49 months (23 Dates for Filing,
  26 Final Action). The November 2026 bulletin was not yet published on 2026-10-11.
- **Page:** finished; 8 headless checks pass (`npm test`).
- **Hosting:** live at https://ulysses4ever.github.io/vb/ (repo `ulysses4ever/vb`). The workflow
  `.github/workflows/pages.yml` publishes `site/` to GitHub Pages on every push to `main`.
- **Updates:** automatic. A systemd timer on the owner's machine (um690) runs `tools/update.py` daily
  and pushes whatever is new, which redeploys the site. Each new bulletin or USCIS chart opens an issue
  that GitHub emails to the owner. See "Monthly updates".

## Layout

```
site/index.html                the page; a comment at the top documents the JSON shape
site/data.json                 generated: do not hand-edit, run the build
data/bulletins/YYYY-MM.json    one extract per bulletin (the source of record)
data/uscis_chart.json          USCIS chart per month, with a source URL
tools/build_data.py            validates data/ and writes site/data.json
tools/update.py                adds new months from the dataset and USCIS, then runs the build
tools/report.py                describes what a push added, for the notification issue
tools/test.mjs                 headless checks; serves site/ itself
package.json                   npm scripts and test dependencies
.github/workflows/pages.yml    publishes site/ to GitHub Pages on push to main
.github/workflows/notify.yml   opens the notification issues (and the stale-data one)
```

## Commands

```sh
python3 tools/update.py               # add new bulletins and USCIS charts (see "Monthly updates")
python3 tools/build_data.py           # rebuild site/data.json; exits 1 on any problem
npm install && npm test               # headless checks (SCREENSHOTS=1 npm test also writes PNGs)
python3 -m http.server -d site 8000   # view at http://localhost:8000
```

On NixOS, Puppeteer's own Chrome download doesn't run. Install with `PUPPETEER_SKIP_DOWNLOAD=1 npm install`
and test with `PUPPETEER_EXECUTABLE_PATH=$(command -v chromium) npm test`.

Opening `index.html` straight from disk (`file://`) can't load `data.json`, because browsers block
`fetch` there. The page then shows an error and an "open a JSON file" control as a fallback.

## Data model

```json
{
 "generated": "2026-10-11",
 "countries": {"ROW": "All chargeability areas except those listed", "CN": "China (mainland-born)", "IN": "India", "MX": "Mexico", "PH": "Philippines"},
 "bulletins": [
  {
   "month": "2026-10",
   "url": "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin/2027/visa-bulletin-for-october-2026.html",
   "uscis_chart": "filing",
   "uscis_source": "https://www.aila.org/…",
   "final":  {"EB-2": {"ROW": "2025-01-01", "CN": "2021-10-01", "IN": "2013-11-01", "MX": "2025-01-01", "PH": "2025-01-01"}},
   "filing": {"EB-2": {"ROW": "2026-03-15", "CN": "2023-01-01", "IN": "2015-01-15", "MX": "2026-03-15", "PH": "2026-03-15"}}
  }
 ]
}
```

- The page needs only `bulletins[].month`, `final` and `filing`; the other fields add links and labels.
- `month` is the bulletin month, `YYYY-MM`.
- A cutoff is `"C"` (current), `"U"` (unavailable) or an ISO date converted from the bulletin's `DDMMMYY`.
- `uscis_chart` is `"filing"`, `"final"` or `null`: the chart USCIS accepted for employment-based I-485 filing that month.
- Categories: `EB-1`, `EB-2`, `EB-3`, `EB-3 Other`, `EB-4`, `EB-4 Religious`, `EB-5 Unreserved`,
  `EB-5 Rural`, `EB-5 High Unemployment`, `EB-5 Infrastructure`. Countries: `ROW`, `CN`, `IN`, `MX`, `PH`.
  The page also accepts other keys and lists them after these.
- The build checks: valid values and real dates; Dates for Filing never earlier than Final Action;
  a USCIS chart for every month but the newest (which may be `null` until USCIS names it); no missing
  months; 48 spot checks (`SPOT_CHECKS` in `build_data.py`).

## How the data was gathered and checked

- **Cutoffs.** The session's shell could not reach travel.state.gov, so each bulletin page was read
  with a web-fetch tool. Its two employment-based tables were transcribed to CSV, converted, and
  written to `data/bulletins/`, and every conversion was re-parsed and compared cell by cell. The fetch
  tool returns a model's transcription of the page rather than raw HTML, so the extracts were only
  "very likely right" until 2026-10-11. Then all 4,900 cells matched armanckeser/visa-bulletin-data,
  which parses the bulletin pages with a real HTML parser (see "Monthly updates").
- **Independent checks.** 48 values spread across every fiscal year in the data were compared with law-firm and
  university summaries of the same bulletins, and the July 2023 EB-2 ROW filing date was re-read from
  the State Department page. All match.
- **USCIS chart.** USCIS's own page shows only the current month, and uscis.gov and the Wayback Machine
  were unreachable from the session. Each month therefore comes from AILA's monthly post quoting USCIS's
  announcement (Morgan Lewis where AILA had no post), corroborated by at least one other summary. No
  sources disagreed. Every month's URL is in `data/uscis_chart.json`.
- **Lesson.** One secondary summary listed 1 May 2023 as the July 2023 EB-2 ROW Dates for Filing
  cutoff; the bulletin says 01DEC22. Take values from the bulletin pages only.

## Domain rules the page encodes

- Every bulletin has two tables for each category and country: **A. Final Action Dates** (when a green
  card can be approved) and **B. Dates for Filing** (an earlier cutoff for starting paperwork).
- For applicants inside the US, USCIS decides each month which table governs I-485 filing; approval
  always needs Final Action. Employment- and family-based choices can differ, and only employment-based
  is stored.
- A priority date qualifies when it is **earlier than** the cutoff. Equal does not qualify; `C` means
  everyone qualifies and `U` means no one does.
- Lag = (first day of the bulletin month − cutoff date) in months of 30.436875 days, never below 0.
  `C` counts as 0 and `U` leaves a gap in the chart.
- The fiscal year starts in October. In FY2023–FY2026, USCIS accepted Dates for Filing from October
  and switched to Final Action in April 2023, March 2024, February 2025 and May 2026. October 2026 is
  Dates for Filing again.

## Page details

- Query parameters: `?data=<url>` loads another JSON file (a cross-origin host must allow CORS);
  `?category=EB-2&country=IN&pd=2027-01-15` preselects the queue and priority date.
- The chosen category, country and priority date are saved in `localStorage` under `vbt-prefs`, in that
  browser only.
- Fallbacks: a clear error if the data can't load, an "open a JSON file" control, and table-only
  rendering if Chart.js fails to load.
- Accessibility: the table holds every charted value; the chart takes keyboard focus (←/→, Home, End)
  and shows the same tooltip as on hover.
- Theming: every color is a CSS token on `:root`, redefined for dark under `prefers-color-scheme` and
  `[data-theme="dark"]`. The chart re-reads the tokens when the theme changes. The series colors
  (#2a78d6 and #eb6834; dark #3987e5 and #d95926) passed color-vision-deficiency separation and
  contrast checks against both page backgrounds. Re-validate if you change them or the backgrounds.
- Fonts: Merriweather for the title, Public Sans for the interface, Roboto Mono for the bulletin's own
  date codes (15MAR26).

## Monthly updates

- **Why a third-party source.** travel.state.gov sits behind Cloudflare and answers every automated
  client with 403. On 2026-10-11 that included curl, an undisguised headless Chrome and Claude's web
  fetch. The Internet Archive's crawler has been blocked too since mid-2026, so its snapshots are 403
  pages. Getting past that would mean disguising the client; the owner chose a third-party source instead.
- **The source.** [armanckeser/visa-bulletin-data](https://github.com/armanckeser/visa-bulletin-data),
  CC0. A GitHub Action checks for new bulletins every 6 hours, keeps each one's page in `raw/` and
  parses it strictly (an unknown header, row or cell is an error). It covers October 2015 onward.
  `tools/update.py` reads its `data/visa_bulletin.json` and imports the months after the newest one in
  `data/bulletins/`. Each new file carries `"source"` naming the dataset, and is written in the
  one-line-per-category layout of most existing files.
- **The safety check.** Before importing anything, the updater compares every month already in
  `data/bulletins/` with the dataset, cell by cell. Any difference stops the run with nothing written,
  because it means the dataset or its parser changed. On 2026-10-11 all 4,900 cells matched. The
  dataset files the current EB-5 unreserved row under `EB5_UNRESERVED_I5_R5`, which its README reserves
  for May 2022. The updater accepts either that code or `EB5_UNRESERVED`.
- **USCIS chart.** uscis.gov does answer, and its page names the employment-based chart for the current
  month (sometimes the next too). A month that page no longer shows falls back to the dataset's weekly
  record of the same page (its `data/uscis_chart.json`). A recorded chart is never overwritten, and a
  contradiction from the USCIS page stops the run. The newest month may stay `null`; the page then
  says "USCIS chart not recorded".
- **Exit status.** 0 means `data/` has the current month's bulletin. 3 means the dataset doesn't have
  it yet; whatever it has is still imported. 1 means anything else went wrong.
- **The timer.** `~/dotfiles/machines/um690/vb-update.nix` runs it daily at 08:00 local time; a run with
  nothing new changes nothing. A bulletin comes out some time in the month before it applies (as late
  as the 29th for October 2026), the dataset has it within six hours, and USCIS names its chart days
  later, so each reaches the site within a day. The job uses a clone of its own in
  `/var/lib/vb-update/vb`, commits as the owner, and pushes with a deploy key that can write to this
  repo only (`~/.ssh/vb-deploy`). Logs: `journalctl -u vb-update`. Run it now:
  `sudo systemctl start vb-update`. A failed run, exit 3 included, shows in `systemctl --failed`.
- **Notifications.** `.github/workflows/notify.yml` runs on every push that touches `data/`.
  `tools/report.py` says what the push added, for EB-2 rest of world only (`CATEGORY` and `COUNTRY` at
  its top): the new bulletin's two cutoffs and how they moved against the month before, and the chart
  USCIS takes with the filing cutoff that makes, or the chart alone when USCIS names it later. The workflow opens that as an issue
  from github-actions[bot] that @-mentions the owner, and GitHub emails it. A daily run also opens one
  issue when the current month's bulletin is still missing on the 3rd or later. To send a month's
  notification again: `gh workflow run notify.yml -f month=2026-10`.

### If the dataset goes away

Read the bulletin pages directly. You'll have to fetch them by hand, given the block above.

- URL: `https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin/{FY}/visa-bulletin-for-{month}-{year}.html`,
  where `{month}` is the lowercase full month name and `{FY}` is `year + 1` for October–December
  bulletins (October 2026 lives under `/2027/`). The index page
  `https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html` lists published
  bulletins; they usually appear mid-month for the following month.
- Parse the tables under the headings "A. FINAL ACTION DATES FOR EMPLOYMENT-BASED PREFERENCE CASES"
  and "B. DATES FOR FILING OF EMPLOYMENT-BASED VISA APPLICATIONS". Map columns by header text:
  "All Chargeability Areas Except Those Listed" → ROW, "CHINA-mainland born" → CN, "INDIA" → IN,
  "MEXICO" → MX, "PHILIPPINES" → PH; ignore any other column. Map rows by keyword: 1st, 2nd, 3rd,
  Other Workers, 4th, Certain Religious Workers, 5th Unreserved, then the Rural, High Unemployment and
  Infrastructure set-asides. Convert `DDMMMYY` to `YYYY-MM-DD` (all years are 20YY) and keep `C` and `U`.
- Before trusting a new parser, run it over the existing months and diff against `data/bulletins/`.

## Next steps

1. **Optional.** A notice when a configured priority date becomes fileable under the chart USCIS
   accepts; a backfill to October 2015, when the Dates for Filing chart began (the dataset has it);
   family-based tables.

## Gotchas

- travel.state.gov blocks automated clients (see "Monthly updates"); uscis.gov doesn't.
- October–December bulletins live in the next fiscal year's folder.
- Some FY2023 bulletins print an extra El Salvador/Guatemala/Honduras column for EB-4. Ignore it.
- Row labels change punctuation between months (for example "(Rural - 20%)"), so match by keyword.
- `U` does occur: EB-2 India final action from July to September 2026, and EB-4 and EB-4 religious
  workers in several months.
- A priority date equal to the cutoff is not current.
