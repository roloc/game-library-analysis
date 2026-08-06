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

1. Get the data — `python run.py` fetches every platform configured in
   `config.env`, merges, and builds the workbook + HTML report
   (see `references/platforms.md` for access routes and their tradeoffs)
2. Read `references/analysis.md` and do the analysis pass over the merged CSV
3. **Write `data/recommendations.json`** — the hand-written judgment
   (schema below). This step is yours, not a script's: verify release
   statuses and known issues by web search first, cite hours in every row.
4. Re-run `python run.py --no-fetch` — both the workbook and the report
   render the recommendations, skip list, on-hold list, and scoreboard.
5. Hand over both files and lead the writeup with the strongest finding.

**Running the pipeline alone is not the job.** The charts are measurements;
the recommendations are the point. A run that ends without step 3 has
produced a dashboard, not an analysis.

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

The whole pipeline is one command once `config.env` exists (copy
`config.example.env`, fill in keys — it is gitignored):

```bash
python run.py             # fetch all configured platforms, merge, workbook + HTML report
python run.py --no-fetch  # rebuild outputs from the existing data/library.csv
```

Or piece by piece:

```bash
# Steam, straight from the API (key comes from the environment, never an argument)
export STEAM_API_KEY=...
python scripts/fetch_steam.py --vanity <name> --out library.csv

# or from JSON the user already pulled themselves
python scripts/fetch_steam.py --from-json owned.json --out library.csv

# the interactive HTML dashboard
python scripts/build_report.py library.csv --out report.html

# build the workbook
python scripts/build_workbook.py library.csv --out library.xlsx
```

The workbook is all live formulas, so cached values do not exist until something
recalculates it. Excel and LibreOffice do this automatically on open, so a human
recipient needs nothing. Only if another program will *read* the file before a
human opens it do you need a recalc pass — in a claude.ai session use
`python /mnt/skills/public/xlsx/scripts/recalc.py library.xlsx`; elsewhere,
`soffice --headless --convert-to xlsx` or simply opening and saving in Excel.

## Onboarding a new user

When `config.env` does not exist, don't just report that the pipeline can't
run — walk them through hookup:

1. **Set up `config.env` for them — pick the path by surface:**
   - *User has a terminal (Claude Code CLI):* point them at the wizard —
     `python run.py` walks through every platform interactively and writes
     `config.env` itself. Keys get typed locally, never into the chat.
   - *User has no terminal (Cowork, claude.ai, desktop app):* **create
     `config.env` yourself** — copy `config.example.env` to `config.env`
     with the values left blank, then tell the user to open that file in
     any editor, paste their keys in, and say "done". Do not just tell
     them to create the file; that's your job. Never ask for a key in
     chat, and never read the file back — verify by re-running the
     pipeline, which reports which platforms are configured.
2. **Front-load the Steam privacy settings** — this is the #1 first-run
   failure and it costs a whole retry cycle if discovered late. Before the
   first pull, tell them plainly:
   - *Game details* = Public + untick "keep my total playtime private"
     (required for the library at all), and
   - *"My profile"* = Public (required only for the achievement /
     completion signal; Steam 403s it even against their own key, and they
     can revert it right after the pull — the cache persists).
3. **Let them make the PlayStation call.** Surface the NPSSO
   password-equivalence and ban-risk warnings from `references/platforms.md`
   yourself — don't let the wizard text be the only place they could have
   seen them. Remind them the pull is one-shot and cached.
4. After the first successful run, check the report for the two teach-state
   sections (empty completion signal, missing recommendations) and resolve
   them: the first is usually the privacy setting, the second is your
   analysis pass — which is the actual job.

## Credentials

Never accept, read, or store a user's API key, NPSSO, or session token in the
conversation, and say so plainly when one is offered. Steam keys and PSN NPSSO
tokens are account-level credentials — an NPSSO is password-equivalent by
Sony's own documentation. If the user pastes one into a chat, or uploads a file
containing one, tell them to regenerate it.

The pattern that works: **keys live in the user's local, gitignored
`config.env`, and the user fills that file in themselves.** You run `run.py`,
which passes them to the fetchers through the environment — you never read,
print, or quote the file. If there is no config file (e.g. a chat-only
session), fall back to: they run the call, they send you the output.

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

## The recommendations file

Write `data/recommendations.json` by hand — this is judgement, not a script.
Both builders render it (`run.py` passes it automatically when it exists):
the workbook gets a Recommendations sheet, the report a card section.

```json
{
  "generated": "YYYY-MM-DD",
  "frame": "one paragraph: how these are ranked and for what play-slot",
  "picks":   [{"rank": 1, "game": "", "status": "release status, verified",
               "why": "", "evidence": "the cited hours", "watch": "real known issues"}],
  "skips":   [{"game": "", "verdict": "", "evidence": ""}],
  "on_hold": [{"game": "", "status": "", "note": ""}],
  "outcomes": [{"game": "", "recommended": "rank + original evidence",
                "result": "what the next data pull showed", "verdict": "Hit/Miss"}],
  "attribution": "who judged, when, and that hours are measured but verdicts are opinion"
}
```

**The scoreboard keeps you honest.** When a later data pull shows a pick got
real hours (or conspicuously didn't), move it from `picks` to `outcomes` with
a verdict and re-rank what remains. A recommender with a public hit rate is
the whole credibility model — record misses as plainly as hits.

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
