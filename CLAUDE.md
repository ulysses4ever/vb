# Visa Bulletin Tracker

Static page plus JSON. Read HANDOFF.md before changing anything; it has the state, data model,
provenance and next steps.

- Never hand-edit `site/data.json`. Change `data/` and run `python3 tools/build_data.py`.
- Take cutoff values only from the State Department bulletin pages, or through `tools/update.py`
  (which imports a dataset that parses those pages), never from summaries or memory.
- After any change, run `npm test` (10 headless checks).
- Keep the page free of a build step; its only external loads are Chart.js 4.4.1 (cdnjs) and Google Fonts.
- Colors are CSS tokens with light and dark values. Keep both in sync.
