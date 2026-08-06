#!/usr/bin/env python3
"""Pull per-game Steam achievement progress into a local JSON cache.

One GetPlayerAchievements call per played game (unplayed games are 0% by
definition and are skipped), throttled to stay well inside Steam's limits.
The key comes from STEAM_API_KEY in the environment, same as fetch_steam.py.

Usage:
    export STEAM_API_KEY=...
    python fetch_achievements_steam.py --vanity roloc59 --library data/steam.csv \\
        --out data/achievements_steam.json

The cache maps appid -> {"earned": n, "total": n} and is reused by run.py's
merge step. Games with no achievement schema (common for older titles) are
cached as {"total": 0} so they are not re-queried every run. Pass --refresh
to re-pull everything.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.steampowered.com"
THROTTLE_S = 0.25


def _get(path, params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def resolve_vanity(key, vanity):
    d = _get("ISteamUser/ResolveVanityURL/v1/", {"key": key, "vanityurl": vanity})
    r = d.get("response", {})
    if r.get("success") != 1:
        sys.exit(f"Could not resolve vanity name '{vanity}'.")
    return r["steamid"]


class ProfilePrivate(Exception):
    """Steam 403s achievements when the profile's base privacy is not Public
    - a different setting from Game Details, and it blocks even the account's
    own API key. Distinguish it so we never cache the zeros it produces."""


def player_achievements(key, steamid, appid):
    """Return (earned, total). (0, 0) means the app has no achievements."""
    try:
        d = _get("ISteamUserStats/GetPlayerAchievements/v1/",
                 {"key": key, "steamid": steamid, "appid": appid})
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode(errors="replace")
        except Exception:
            pass
        if e.code == 403 and "not public" in body.lower():
            raise ProfilePrivate from None
        # Steam answers 400 (and the odd 403) for apps with no stats
        if e.code in (400, 403):
            return 0, 0
        raise
    ps = d.get("playerstats", {})
    if not ps.get("success") or "achievements" not in ps:
        return 0, 0
    ach = ps["achievements"]
    return sum(1 for a in ach if a.get("achieved")), len(ach)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vanity")
    p.add_argument("--steamid")
    p.add_argument("--library", required=True, help="steam.csv from fetch_steam.py")
    p.add_argument("--out", default="achievements_steam.json")
    p.add_argument("--refresh", action="store_true", help="re-pull cached entries too")
    a = p.parse_args()

    key = os.environ.get("STEAM_API_KEY")
    if not key:
        sys.exit("Set STEAM_API_KEY first (or run via run.py with config.env).")
    steamid = a.steamid or (a.vanity and resolve_vanity(key, a.vanity))
    if not steamid:
        sys.exit("Pass --vanity or --steamid.")

    with open(a.library, encoding="utf-8") as f:
        played = [r for r in csv.DictReader(f)
                  if r["platform"] == "Steam" and int(r["minutes"] or 0) > 0]

    cache = {}
    if os.path.exists(a.out) and not a.refresh:
        with open(a.out) as f:
            cache = json.load(f)

    todo = [r for r in played if str(r["id"]) not in cache]
    print(f"{len(played)} played Steam games; {len(todo)} to query "
          f"({len(played) - len(todo)} cached)")
    errors = 0
    for i, r in enumerate(todo, 1):
        try:
            earned, total = player_achievements(key, steamid, r["id"])
            cache[str(r["id"])] = {"earned": earned, "total": total}
        except ProfilePrivate:
            print(
                "\n*** Steam blocked achievement access: the profile's base "
                "privacy is not Public. ***\n"
                "Game Details being public is enough for the library pull, "
                "but achievements ALSO need:\n"
                "  Steam -> Edit Profile -> Privacy Settings -> "
                "\"My profile\" -> Public\n"
                "Flip it, re-run, and flip it back afterwards if you like - "
                "the cache persists.\n"
                "(Nothing was cached from this failed run, so a re-run "
                "queries everything cleanly. If an OLDER run cached zeros "
                "while the profile was private, re-run once with --refresh.)",
                file=sys.stderr)
            print(f"cache unchanged ({len(cache)} entries) -> {a.out}")
            with open(a.out, "w") as f:
                json.dump(cache, f, indent=1)
            return
        except Exception as e:
            errors += 1
            print(f"  {r['name']}: {e}", file=sys.stderr)
            if errors > 10:
                print("Too many errors; writing partial cache and stopping.",
                      file=sys.stderr)
                break
        if i % 25 == 0:
            print(f"  {i}/{len(todo)}...")
        time.sleep(THROTTLE_S)

    with open(a.out, "w") as f:
        json.dump(cache, f, indent=1)
    with_ach = sum(1 for v in cache.values() if v.get("total"))
    done = sum(1 for v in cache.values()
               if v.get("total") and v["earned"] == v["total"])
    print(f"cached {len(cache)} games -> {a.out}")
    print(f"  with achievements: {with_ach}   100% completed: {done}")


if __name__ == "__main__":
    main()
