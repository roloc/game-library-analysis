---
name: game-library-analysis
description: Pull a gaming library with playtime from Steam, Xbox, or PlayStation, build an Excel workbook analyzing it, and produce ranked "what should I play next" recommendations grounded in the actual hours rather than critical acclaim. Use this whenever the user mentions their Steam library, backlog, playtime, unplayed games, what to play next, "hidden gems", game recommendations based on what they already own, or wants to connect a gaming account so recommendations skip the games they have already played. Also use it when refreshing or extending an existing library workbook, or adding a second platform to one.
---

# Game Library Analysis

Turn a raw platform export into a workbook plus recommendations that are actually
defensible — every pick traceable to hours the person really logged.

The core insight this exists to serve: **people are unreliable narrators of their
own taste.** They will tell you they love roguelikes when one outlier game
accounts for 90% of the genre's hours, or that they "played that at launch" when
the data says five hours and never again. The library is the ground truth. Lead
with it, and be willing to contradict the person's self-description when the
numbers disagree — that contradiction is usually the most valuable thing you
produce.

## Workflow

1. Get the data (see `references/platforms.md` for per-platform access routes)
2. Normalize it to the CSV schema below
3. Run `scripts/build_workbook.py` to produce the workbook
4. Read `references/analysis.md` and do the analysis pass
5. Write the Recommendations sheet by hand, grounded in the numbers
6. Recalculate, then hand over the file

### The normalized CSV

Everything funnels through one shape so platforms can be merged later:

```
platform,id,name,minutes,last_played,genre,note
Steam,427520,Factorio,16637,2024-11-16,,
Steam,400,Portal,0,,,Playtime untracked (pre-2009)
```

`genre` may be left blank — the builder fills it from `assets/genres.json`.
`last_played` is `YYYY-MM-DD` or empty. `minutes` is an integer.

### Scripts

```bash
# Steam, straight from the API (key comes from the environment, never an argument)
export STEAM_API_KEY=...
python scripts/fetch_steam.py --vanity <name> --out library.csv

# or from JSON the user already pulled themselves
python scripts/fetch_steam.py --from-json owned.json --out library.csv

# build the workbook
python scripts/build_workbook.py library.csv --out library.xlsx
```

The workbook is all live formulas, so cached values do not exist until something
recalculates it. Excel and LibreOffice do this automatically on open, so a human
recipient needs nothing. Only if another program will *read* the file before a
human opens it do you need a recalc pass — in a claude.ai session use
`python /mnt/skills/public/xlsx/scripts/recalc.py library.xlsx`; elsewhere,
`soffice --headless --convert-to xlsx` or simply opening and saving in Excel.

## Credentials

Never accept, read, or store a user's API key, NPSSO, or session token, and say
so plainly when one is offered. Steam keys and PSN NPSSO tokens are
account-level credentials — an NPSSO is password-equivalent by Sony's own
documentation. If the user pastes one, or points at a file containing one, tell
them to regenerate it.

The pattern that works: **they run the call, they send you the output.** Offer to
write the script if that is the friction point. When a script needs a key, read
it from an environment variable so it never lands in shell history, a file, or
the conversation.

## Data integrity checks

Run these before drawing any conclusion. Each one has burned a real analysis:

- **Pre-2009 Steam titles.** Steam did not record playtime until March 2009.
  Portal, Half-Life 2, BioShock and friends can read 0 while having been played
  to death. `assets/pre2009_appids.json` seeds the known ones; add more as you
  meet them. Never count these as "never launched" — it inflates the backlog
  number and it will be the first thing the user notices is wrong.
- **Sentinel timestamps.** Steam uses small values (commonly 86400 = 1970-01-02)
  for "played, date unknown." Treat anything under ~100000 as no date.
- **Launcher splits.** A game bought on Steam but played through its own client
  (Path of Exile 2, Battle.net titles, EA App) reads as 0. If the user says they
  played something the data says they did not, believe the user and note it.
- **Console history is missing entirely.** A Steam-only pull will show 3 hours
  for a game they sank 200 hours into on PS5. Ask what else they play on before
  concluding a genre "did not stick."
- **Duplicate store entries.** Old titles often appear twice; keep both rows but
  do not double-count them in commentary.

## Reading the library

Full guidance in `references/analysis.md`. The short version:

- **Hours per game beats total hours.** A genre with 800 hours across 11 titles
  is a much stronger signal than 800 across 60.
- **Look at the recency curve.** Sort by last-played and read the last 18 months.
  A wall of 1–3 hour sessions is a person browsing, not playing, and that
  reframes the whole request.
- **Distrust genre averages with an outlier.** Check whether one title carries
  the genre before recommending more of it.
- **Zero-playtime titles are the highest-value output.** Something acclaimed,
  already owned, unplayed, and matching a 200-hour pattern is the best
  recommendation available — it costs nothing and the evidence is overwhelming.
- **Ask about buying habits.** Some people buy early access to support a
  developer and deliberately wait for 1.0. That single fact reclassifies a large
  chunk of an apparent backlog from neglect to intent, and it changes which
  recommendations are even eligible.

## The Recommendations sheet

Write it by hand — this is judgement, not a script. Columns:

| Rank | Game | Release status | Why it fits | Supporting hours in your library | Watch out for | Status (fill in) |

Rules that make it trustworthy:

- **Cite specific hours in every row.** "Factorio 277h; Dyson Sphere Program 20h"
  beats "you like automation games." The user should be able to audit every pick.
- **Rank by fit to their data, not by review scores.** Say so at the top.
- **Every row gets a real "watch out for."** A recommendation with no downside
  reads as marketing. Search for current known issues and community complaints
  before ranking anything, and give a sense of how widespread they are.
- **Include a skip list.** Naming what *not* to play, with the evidence, does
  more for credibility than another pick — especially for the obvious
  suggestions their data quietly rules out.
- **Check release status against their buying rule** before ranking anything.
- **Prefer games they already own.** The backlog is the point.

## Output conventions

- Formulas, never hardcoded values, for anything derived — the user will edit
  genre tags and Status, and the Summary should follow.
- Yellow fill plus blue font marks every cell meant for the user to fill in.
- One genre per game. The point is grouping titles that scratch the same itch,
  not taxonomic correctness.
- Note the data source and pull date on each sheet, and attribute the judgement
  calls to Claude so future readers know which numbers are measured and which
  are opinion.

## Extending to a second platform

Fetch it, normalize to the same CSV, concatenate, rebuild. The builder adds a
Platform column automatically when it sees more than one. Merging is where the
real picture appears — console hours routinely overturn a Steam-only read.
