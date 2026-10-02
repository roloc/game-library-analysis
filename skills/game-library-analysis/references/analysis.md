# Reading a library

## Run these first

```python
# concentration: which genres hold attention, not just which are owned
hours_per_game = genre_hours / genre_titles

# the recency curve - the single most revealing view
sorted(rows, key=lambda r: -r.last_played)[:25]

# outlier check: does one title carry a genre?
top_title_hours / genre_hours          # > 0.5 means the genre signal is fake

# the gold seam
[r for r in rows if r.minutes == 0 and r.note != UNTRACKED]
```

## What each view tells you

**Hours per game.** Total hours mostly measures how many games someone bought in
a genre. Hours per game measures whether the genre holds them. A bucket with 863
hours across 11 titles is a far stronger signal than 1,056 across 61 — the first
is a home, the second is a hobby they keep shopping for.

**The recency curve.** Sort by last-played and read the most recent 20–25 rows.
You are looking for the shape, not the titles. A run of 1–3 hour sessions across
many different games means the person is sampling, not playing, and no
recommendation fixes that. Naming it plainly is more useful than a tenth pick —
and it is often exactly what they came to talk about without saying so.

**Outlier check.** Before recommending more of a genre, check whether one title
carries it. A person with 287 hours in one roguelike, 10 in its sequel and 3 in
the genre's most acclaimed entry does not like roguelikes; they liked that game.
Recommending the obvious sequel here is the classic failure.

Then go one level deeper: find what the *stuck* titles share that the bounced
ones do not. Long runs with roster and economy management versus fast
single-character combat. Open-ended optimization versus scripted execution. That
shared property is the real recommendation target, and it will rarely match a
store genre tag.

**Zero-playtime titles.** The most valuable output in the whole exercise. An
acclaimed game, already owned, never launched, sitting in the person's single
highest hours-per-game genre is as close to a sure thing as recommendation gets.
Check the backlog before reaching for anything they would need to buy.

## Cross-checks against what they told you

Compare the data to the person's self-description and surface the gaps
explicitly. These are the highest-value moments in the conversation:

- Claimed a genre they actually bounced off
- Claimed to have played something the data says they barely touched
- A stated preference contradicted by where the hours went
- A recommendation you already made that the data now rules out — say so
  directly and revise, don't quietly drop it

Being wrong out loud and correcting with evidence builds more trust than being
vague. It also teaches them something about their own habits, which is usually
the thing they actually enjoy about this.

## Common confounders

| Signal | Innocent explanation | How to check |
| --- | --- | --- |
| 0 hours, old game | Predates playtime tracking | Release year < 2009 |
| 0 hours, recent game | Bought in early access, waiting for 1.0 | Ask about buying habits |
| 0 hours, has a launcher | Played outside Steam | Ask |
| Low hours, loved genre | Played it on console | Ask what else they own |
| High hours, one session | Left running idle | Check last-played and session pattern |
| Huge hours, ancient date | Legacy import | Sanity-check the timestamp |

## Framing the writeup

Lead with the single strongest finding, usually the best unplayed game. Then the
corrections. Then the aggregate picture. Then the uncomfortable observation about
the pattern, if there is one — do that last, once the useful material has earned
the right to say it, and keep it brief and non-judgemental. The person asked for
recommendations; the pattern observation is a gift, not the assignment.
