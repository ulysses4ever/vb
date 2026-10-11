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
- **Not done:** automatic monthly updates. See "Next steps".

## Layout

```
site/index.html                the page; a comment at the top documents the JSON shape
site/data.json                 generated: do not hand-edit, run the build
data/bulletins/YYYY-MM.json    one extract per bulletin (the source of record)
data/uscis_chart.json          USCIS chart per month, with a source URL
tools/build_data.py            validates data/ and writes site/data.json
tools/test.mjs                 headless checks; serves site/ itself
package.json                   npm scripts and test dependencies
```

## Commands

```sh
python3 tools/build_data.py           # rebuild site/data.json; exits 1 on any problem
npm install && npm test               # headless checks (SCREENSHOTS=1 npm test also writes PNGs)
python3 -m http.server -d site 8000   # view at http://localhost:8000
```

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
  a USCIS chart for every month; no missing months; 48 spot checks (`SPOT_CHECKS` in `build_data.py`).

## How the data was gathered and checked

- **Cutoffs.** The session's shell could not reach travel.state.gov, so each bulletin page was read
  with a web-fetch tool. Its two employment-based tables were transcribed to CSV, converted, and
  written to `data/bulletins/`, and every conversion was re-parsed and compared cell by cell. The fetch
  tool returns a model's transcription of the page rather than raw HTML, so treat the extracts as very
  likely right, not byte-exact. A real HTML parser should re-derive them (see "Next steps").
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

## Next steps

1. **Monthly updater (the main open task).**
   - Cutoffs: `https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin/{FY}/visa-bulletin-for-{month}-{year}.html`,
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
   - USCIS chart: `https://www.uscis.gov/green-card/green-card-processes-and-procedures/visa-availability-priority-dates/adjustment-of-status-filing-charts-from-the-visa-bulletin`.
     Its employment-based section names the chart for the current month and sometimes the next. Add the
     month, chart and URL to `data/uscis_chart.json`. USCIS usually posts a few days after the bulletin.
     The build fails while the newest month has no chart; relax that check for the newest month only if
     you want to publish before USCIS posts (the page already handles `null`).
   - Write `data/bulletins/YYYY-MM.json`, run the build and the tests, then commit or open a PR. A
     GitHub Actions schedule (say, daily from the 5th to the 25th, doing nothing when there's nothing
     new) fits well.
   - Before trusting the parser, run it over all 49 existing months and diff against `data/bulletins/`.
     Any difference is either a parser bug or a transcription error in an extract; settle it from the
     bulletin page.
   - uscis.gov refused automated fetches during the session. Expect bot protection there and keep a
     fallback, such as recording the chart by hand from the page.
2. **Hosting.** GitHub Pages (serving `site/`) or any static host. Keep `data.json` next to `index.html`
   unless `?data=` points elsewhere.
3. **Optional.** A notice when a configured priority date becomes fileable under the chart USCIS
   accepts; a backfill to October 2015, when the Dates for Filing chart began; family-based tables.

## Gotchas

- October–December bulletins live in the next fiscal year's folder.
- Some FY2023 bulletins print an extra El Salvador/Guatemala/Honduras column for EB-4. Ignore it.
- Row labels change punctuation between months (for example "(Rural - 20%)"), so match by keyword.
- `U` does occur: EB-2 India final action from July to September 2026, and EB-4 and EB-4 religious
  workers in several months.
- A priority date equal to the cutoff is not current.
