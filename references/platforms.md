# Getting library data off each platform

Ordered by how easy they are. Steam is trivial, Xbox is easy, PlayStation is a
judgement call. Verify anything time-sensitive here with a search before relying
on it — these are third-party services and they change.

## Steam

**Best route: the official Web API.** Free key at
`https://steamcommunity.com/dev/apikey`.

```
# vanity name -> 64-bit SteamID
https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key=KEY&vanityurl=NAME

# the library, with playtime
https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key=KEY&steamid=ID&include_appinfo=1&include_played_free_games=1&format=json
```

Fields that matter: `playtime_forever` (minutes, all-time), `rtime_last_played`
(unix), `name`, `appid`. Per-platform splits (`playtime_windows_forever`,
`playtime_mac_forever`, `playtime_deck_forever`) are often zero or inconsistent
even when `playtime_forever` is populated — do not rely on them.

**Fallback: the public profile page.** `steamcommunity.com/id/<name>/games/?tab=all`
requires *two* privacy settings, and people routinely get this wrong because
their own logged-in view always looks correct:

1. Edit Profile → Privacy Settings → **Game details** = Public
2. Uncheck **"Always keep my total playtime private even if users can see my game details"**

Even when public, the page renders through JavaScript, so a fetch may return the
shell without the data. If it redirects to a sign-in, game details are private.

**Fallback: Steam's data export.** `help.steampowered.com/en/accountdata` includes
a games and playtime section. No key involved, good when the user would rather
not touch an API.

## Xbox

No official public API for playtime. **OpenXBL** (`xbl.io`) is the practical
route: sign in with a Microsoft account, get a free API key, pass it in an
`X-Authorization` header. Plain HTTP, no SDK. Their title history endpoint
returns playtime, last-played dates and title details.

The API key is a scoped third-party key rather than an account password, which
makes Xbox meaningfully lower-risk than PlayStation. Still: the user runs it and
sends the output.

Alternative: the Microsoft privacy dashboard at `account.microsoft.com/privacy`
offers a data download.

Caveat: Xbox playtime coverage is patchier than Steam's. Achievement and
last-played data are more reliable than hours. Set expectations accordingly.

## PlayStation

No official API at all. The working libraries are reverse-engineered from the PSN
app:

- `psn-api` (JavaScript) — `getUserPlayedGames()` returns played games with
  playtime info, ordered by recency
- `psnawp` (Python) — same surface; `scripts/fetch_psn.py` uses this one

Note the data-shape difference from Steam: PSN only reports titles actually
*played*. Unplayed purchases never appear, so there is no PSN backlog view and
zero-playtime analysis is Steam-only.

Both authenticate with an **NPSSO** token, obtained by signing in at
playstation.com and then visiting `ca.account.sony.com/api/v1/ssocookie`.

**Surface both of these before the user proceeds, and let them decide:**

1. The libraries' own documentation says not to expose the NPSSO anywhere because
   it is equivalent to the account password.
2. `psnawp` explicitly warns that excessive API use can get a PSN account
   temporarily or permanently banned, and suggests using a throwaway account
   rather than a primary one.

A single one-shot pull is very unlikely to trip anything, but it is the user's
account and their call. Offer the safer routes:

- **Sony's personal data request** through account settings — official, no token,
  takes days.
- **Read it off the console.** The PS5 Game Library shows hours per title. For 30
  or 40 games, photographing the list is genuinely faster than any of this.

## Battle.net

No playtime API, official or reverse-engineered — Blizzard's developer API
(develop.battle.net) exposes characters, achievements and game data, but not
hours. The routes that exist:

- **WoW: the in-game `/played` command.** Exact to the minute, per character.
  Log each character in, type `/played`, read "Total time played". Sum across
  characters (and across Retail/Classic, which count separately). For a
  many-alt account this is tedious but it is the ground truth, and even
  mains-only gives a solid lower bound. Note the output is in *days* —
  convert before entering (1 day = 1,440 minutes).
- **Overwatch/D4/others:** no reliable per-account hours surface. Career
  profiles show per-hero time in-game but nothing exportable.
- **Blizzard's GDPR data request** (account privacy settings) returns an
  account archive after days-to-weeks; playtime coverage in it is
  inconsistent — treat as a bonus, not a plan.

Enter what you get as rows in `data/manual.csv` (schema in
`manual.example.csv`); `run.py` merges it automatically.

## Other launchers

Epic, GOG and the EA App likewise have no playtime export (Epic's GDPR data
request sometimes includes minutes played). Use `data/manual.csv` for anything
recovered by hand, and if a sizeable chunk of someone's play happens on a
platform with no data, say so as a known gap rather than letting the workbook
imply the picture is complete.
