# Game Library Analysis

Pull your gaming library — Steam, Xbox, PlayStation — into one Excel workbook,
then get "what should I play next" recommendations grounded in the hours you
actually logged, not review scores.

The premise: **people are unreliable narrators of their own taste.** You'll say
you love roguelikes when one outlier carries 90% of the genre's hours. Your
library is the ground truth. This project leads with it — including a skip list
of games your own data quietly rules out.

This repo is packaged as a [Claude skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills):
point Claude at it (or install it) and `SKILL.md` drives the workflow. The
scripts also run standalone.

## Quick start (Steam)

```bash
pip install -r requirements.txt

# Get a free key at https://steamcommunity.com/dev/apikey
export STEAM_API_KEY=your-key

python scripts/fetch_steam.py --vanity your-steam-name --out library.csv
python scripts/build_workbook.py library.csv --out library.xlsx
```

Open `library.xlsx` in Excel. Four sheets:

| Sheet | Contents |
| --- | --- |
| Summary | Counts and hours by genre — all live formulas |
| Recommendations | Ranked picks, written by hand from the analysis (see SKILL.md) |
| Library | Every title by hours, with a Status column for you to fill in |
| Backlog | Zero-playtime titles, with pre-2009 untracked ones split out |

Yellow-filled, blue-font cells are yours to fill in; the Summary formulas
follow your edits.

## Adding platforms

Each fetcher writes the same normalized CSV. Concatenate them (keep one header
row) and rebuild — the workbook grows a Platform column automatically.

- **Xbox** — `scripts/fetch_xbox.py`, via a free [OpenXBL](https://xbl.io) key.
  Newest and least battle-tested fetcher; last-played dates are more reliable
  than hours on Xbox generally.
- **PlayStation** — no script yet, deliberately. Sony has no official API, and
  the reverse-engineered routes need an NPSSO token that is
  password-equivalent, with a documented account-ban risk from heavy use.
  `references/platforms.md` lays out the options, including two safer ones,
  so you can make that call yourself.

## Credentials policy

Nothing in this repo accepts an API key as an argument, writes one to disk, or
prints one. Keys come from environment variables only. If you're running this
with an AI assistant: **you run the fetch, you hand over the output.** Never
paste a key, NPSSO, or session token into a chat — and if you already have,
regenerate it.

## Layout

```
SKILL.md                    the workflow — how to analyze, what makes recommendations trustworthy
references/platforms.md     per-platform data access routes and their tradeoffs
references/analysis.md      how to read a library: signals, confounders, framing
scripts/fetch_steam.py      Steam Web API -> normalized CSV
scripts/fetch_xbox.py       OpenXBL -> normalized CSV
scripts/build_workbook.py   normalized CSV -> Excel workbook
assets/genres.json          seed name->genre lookup; grows as libraries pass through
assets/pre2009_appids.json  Steam titles that predate playtime tracking
```

## The normalized CSV

```
platform,id,name,minutes,last_played,genre,note
Steam,427520,Factorio,16637,2024-11-16,,
Steam,400,Portal,0,,,Playtime untracked (pre-2009)
```

`genre` may be blank (the builder fills it from `assets/genres.json`);
`last_played` is `YYYY-MM-DD` or empty; `minutes` is an integer.
