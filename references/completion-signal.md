# The completion signal (designed, not yet built)

Prompted by a review note from Steve's wife, and she's right: **hours measure
retention, and retention only means something for games without an ending.**

A loop game (Factorio, WoW, Total War) has no ceiling — hours are the honest
score. A finite game (Elden Ring, God of War, Clair Obscur) has a natural
maximum somewhere around 40–120h, after which *stopping is the correct
outcome*. Scoring both on the same hours axis makes every finished campaign
look like a bounced roguelike. The fix is a second axis: **completion**.

## Data availability (all three platforms have it)

| Platform | Source | What you get |
| --- | --- | --- |
| Steam | `GetPlayerAchievements` + `GetSchemaForGame` (same key as the library pull, one call per appid) | unlocked/total achievements per game; global unlock %s identify which achievement is "finished the story" |
| Xbox | OpenXBL — the titleHistory response we already fetch carries an `achievement` block | currentGamerscore / totalGamerscore, progressPercentage — **already in the raw pull, currently discarded** |
| PlayStation | psnawp `trophy_titles()` | earned/total trophies, progress %, and the platinum flag (one extra pass; same NPSSO caveats as the library pull) |

## Proposed views

1. **The quadrant scatter** — x: achievement/trophy completion %, y: hours
   (log-ish). Four readable regions:
   - *high hours, low %* — the loops (WoW, Factorio). Measured in hours; this
     chart just confirms it.
   - *modest hours, high %* — **finished campaigns**. The games the hours view
     erases. This quadrant is the wife-point, visualized.
   - *low hours, low %* — bounced or backlog. Already covered today.
   - *high hours, high %* — the 100% obsessions (rare, worth celebrating).
2. **"Rolled credits" list** — Steam's global achievement stats make the
   story-completion achievement identifiable (the last high-global-% story
   marker). A game with it unlocked is *done*, not *abandoned*, regardless of
   hours. PSN platinums are the same signal, stronger.
3. **Genre-aware framing** — tag each genre bucket loop vs finite (MMO,
   factory, city builder = loop; open-world action, RPG = finite) so summary
   views can say "loop genres ranked by hours; finite genres ranked by
   completion" instead of one lying axis.

## Implementation sketch

- Fetchers gain optional columns: `ach_earned`, `ach_total`, `ach_pct`,
  `platinum` (CSV schema addition is backward-compatible; blank = not
  fetched).
- Steam: ~430 API calls, throttled — a couple of minutes, same key.
- Xbox: parse the achievement block already present in titleHistory. Free.
- PSN: one `trophy_titles()` pass, merged by name.
- Report: quadrant scatter + rolled-credits list; workbook: two new columns
  on Library plus a Completed sheet.
