# generator

Three scripts and a font. No web fonts, no badge services: every card is an SVG whose
letters are outlines taken from Martian Mono.

| File | What it does |
|---|---|
| `build.py` | Draws the twelve cards in `cards/` (six, light and dark) and writes `README.md`. |
| `fetch_calendar.py` | Reads my contribution calendar from GitHub into `data/calendar.json`. |
| `mine.py` | Measures language mix and median change size in private clones into `data/work.json`. Runs on my machine only. |
| `fonts/` | Martian Mono, under the SIL Open Font License. |

## Run it

```
pip install fonttools
python generator/build.py
```

`build.py` also writes `preview-dark.html` and `preview-light.html`, which stand in for
GitHub's README column.

## Where the numbers come from

- `data/profile.json`: the words, the systems and their scale. Edit it and rebuild.
- `data/calendar.json`: GitHub, every night, through the workflow in `.github/workflows/cards.yml`.
- `data/work.json`: `python generator/mine.py --author SabillonJ --branch origin/Dev <repo> <repo>`.
  A shape, not a history: the language mix and the median size of one change. No commit
  count, no breakdown by subject, no messages, no file names. The repositories are the
  company's and private; this file is public.

## Motion

The block line rides past its camera, a marker walks down the systems, thin lines sweep
and two dots blink. Every frame is a complete card — nothing grows in from nothing,
because a browser freezes an SVG in a hidden tab — and `prefers-reduced-motion` turns
all of it off.
