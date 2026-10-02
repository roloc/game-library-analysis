#!/usr/bin/env python3
"""Pull a Steam library into the normalized CSV this skill's builder expects.

The API key is read from the STEAM_API_KEY environment variable and is never
written to disk, echoed, or included in output. Get one at
https://steamcommunity.com/dev/apikey

Usage:
    export STEAM_API_KEY=...
    python fetch_steam.py --vanity <name> --out library.csv
    python fetch_steam.py --steamid 7656119... --out library.csv

If you already have the raw JSON (pasted from a browser, saved from a previous
run), skip the network entirely:

    python fetch_steam.py --from-json owned.json --out library.csv
"""
import argparse
import csv
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

API = "https://api.steampowered.com"


def _get(path, params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def resolve_vanity(key, vanity):
    d = _get("ISteamUser/ResolveVanityURL/v1/", {"key": key, "vanityurl": vanity})
    r = d.get("response", {})
    if r.get("success") != 1:
        sys.exit(f"Could not resolve vanity name '{vanity}'. Check the spelling.")
    return r["steamid"]


def owned_games(key, steamid):
    d = _get(
        "IPlayerService/GetOwnedGames/v1/",
        {
            "key": key,
            "steamid": steamid,
            "include_appinfo": 1,
            "include_played_free_games": 1,
            "format": "json",
        },
    )
    games = d.get("response", {}).get("games")
    if games is None:
        sys.exit(
            "Steam returned no games. The profile's Game Details privacy setting "
            "is probably not Public, or the steamid is wrong."
        )
    return games


# Steam did not record playtime until March 2009. A zero on an older title means
# the data does not exist, not that the game was never played. Treating those as
# "never launched" produces a materially wrong backlog count, so flag them.
TRACKING_START_YEAR = 2009
UNTRACKED = "Playtime untracked (pre-2009)"


def to_rows(games, pre2009_appids):
    rows = []
    for g in games:
        ts = g.get("rtime_last_played", 0) or 0
        # Steam uses small sentinel values (commonly 86400) for "played, date unknown"
        if ts > 100000:
            last = datetime.datetime.fromtimestamp(
                ts, datetime.timezone.utc
            ).strftime("%Y-%m-%d")
        else:
            last = ""
        mins = g.get("playtime_forever", 0)
        rows.append(
            {
                "platform": "Steam",
                "id": g["appid"],
                "name": g.get("name", f"(unknown app {g['appid']})"),
                "minutes": mins,
                "last_played": last,
                "genre": "",
                "note": UNTRACKED
                if (mins == 0 and g["appid"] in pre2009_appids)
                else "",
            }
        )
    rows.sort(key=lambda r: -r["minutes"])
    return rows


def load_pre2009(path):
    if not path or not os.path.exists(path):
        return set()
    with open(path) as f:
        return {int(x) for x in json.load(f).get("appids", [])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vanity", help="Steam vanity URL name")
    p.add_argument("--steamid", help="64-bit SteamID")
    p.add_argument("--from-json", help="Skip the network; read a saved API response")
    p.add_argument("--out", default="library.csv")
    p.add_argument(
        "--pre2009",
        default=os.path.join(
            os.path.dirname(__file__), "..", "assets", "pre2009_appids.json"
        ),
        help="JSON list of appids released before playtime tracking began",
    )
    a = p.parse_args()

    if a.from_json:
        with open(a.from_json) as f:
            games = json.load(f)["response"]["games"]
    else:
        key = os.environ.get("STEAM_API_KEY")
        if not key:
            sys.exit(
                "Set STEAM_API_KEY first: export STEAM_API_KEY=...\n"
                "Never paste the key into a chat or commit it to a repo."
            )
        steamid = a.steamid or (a.vanity and resolve_vanity(key, a.vanity))
        if not steamid:
            sys.exit("Pass --vanity or --steamid.")
        games = owned_games(key, steamid)

    rows = to_rows(games, load_pre2009(a.pre2009))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "platform",
                "id",
                "name",
                "minutes",
                "last_played",
                "genre",
                "note",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    played = sum(1 for r in rows if r["minutes"] > 0)
    untracked = sum(1 for r in rows if r["note"] == UNTRACKED)
    print(f"{len(rows)} games -> {a.out}")
    print(f"  ever launched:      {played}")
    print(f"  never launched:     {len(rows) - played - untracked}")
    print(f"  untracked pre-2009: {untracked}")
    print(f"  total hours:        {sum(r['minutes'] for r in rows) / 60:,.0f}")


if __name__ == "__main__":
    main()
