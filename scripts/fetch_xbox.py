#!/usr/bin/env python3
"""Pull an Xbox library via OpenXBL (xbl.io) into the normalized CSV.

The API key is read from the OPENXBL_API_KEY environment variable and is never
written to disk, echoed, or included in output. Get one free at https://xbl.io
by signing in with the Microsoft account whose library you want.

Usage:
    export OPENXBL_API_KEY=...
    python fetch_xbox.py --out xbox.csv

If you already have the raw title-history JSON saved:

    python fetch_xbox.py --from-json titles.json --out xbox.csv

How it works: one call to player/titleHistory for the title list and
last-played dates, then batched calls to player/stats for MinutesPlayed.
Not every title exposes that stat (see references/platforms.md - Xbox
playtime coverage is patchier than Steam's); rows without it carry 0 minutes
and a note saying playtime was unavailable rather than implying the game was
never touched.
"""
import argparse
import csv
import json
import os
import sys
import urllib.request

API = "https://xbl.io/api/v2"
# xbl.io sits behind Cloudflare, which 403s Python's default user agent.
UA = "game-library-analysis/1.0"
PLAYTIME_UNAVAILABLE = "Playtime not exposed by Xbox API"
STATS_BATCH = 40


def _call(path, key, body=None):
    headers = {"X-Authorization": key, "Accept": "application/json", "User-Agent": UA}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(f"{API}/{path}", headers=headers, data=data)
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    # responses arrive wrapped in a "content" envelope
    return d.get("content", d)


def title_history(key):
    d = _call("player/titleHistory", key)
    titles = d.get("titles")
    if not titles:
        sys.exit(
            "OpenXBL returned no titles. Check that the API key is valid and "
            "the account has played games on this profile."
        )
    return d.get("xuid"), titles


def minutes_played(key, xuid, title_ids):
    """Batched MinutesPlayed lookups. Returns {titleId: minutes}. Titles
    missing from the response simply don't expose the stat."""
    out = {}
    for i in range(0, len(title_ids), STATS_BATCH):
        chunk = title_ids[i:i + STATS_BATCH]
        body = {
            "xuids": [str(xuid)],
            "stats": [{"name": "MinutesPlayed", "titleId": str(t)} for t in chunk],
        }
        try:
            d = _call("player/stats", key, body)
        except Exception as e:
            print(f"  stats batch {i//STATS_BATCH + 1} failed ({e}); "
                  f"those titles will show playtime unavailable", file=sys.stderr)
            continue
        for coll in d.get("statlistscollection", []):
            for s in coll.get("stats", []):
                if s.get("name") == "MinutesPlayed" and s.get("value") is not None:
                    try:
                        out[str(s["titleid"])] = int(s["value"])
                    except (KeyError, ValueError, TypeError):
                        pass
    return out


def to_rows(titles, minutes_map):
    rows = []
    for t in titles:
        if t.get("type") and t["type"] != "Game":
            continue
        hist = t.get("titleHistory") or {}
        last = (hist.get("lastTimePlayed") or "")[:10]  # ISO datetime -> YYYY-MM-DD
        tid = str(t.get("titleId", ""))
        mins = minutes_map.get(tid)
        # the titleHistory response carries achievement progress for free
        ach = t.get("achievement") or {}
        earned = ach.get("currentAchievements")
        total = ach.get("totalAchievements")
        pct = ach.get("progressPercentage")
        if pct is None and earned is not None and total:
            pct = round(100 * earned / total, 1)
        rows.append(
            {
                "platform": "Xbox",
                "id": tid,
                "name": t.get("name", "(unknown title)"),
                "minutes": mins or 0,
                "last_played": last,
                "genre": "",
                "note": "" if mins is not None else PLAYTIME_UNAVAILABLE,
                "ach_earned": earned if earned is not None else "",
                "ach_total": total if total is not None else "",
                "ach_pct": pct if pct is not None else "",
                "platinum": "",
            }
        )
    rows.sort(key=lambda r: (-r["minutes"], r["name"].lower()))
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--from-json", help="Skip the network; read a saved API response")
    p.add_argument("--out", default="xbox.csv")
    a = p.parse_args()

    if a.from_json:
        with open(a.from_json) as f:
            d = json.load(f)
        d = d.get("content", d)
        titles = d.get("titles") or d
        minutes_map = {}
    else:
        key = os.environ.get("OPENXBL_API_KEY")
        if not key:
            sys.exit(
                "Set OPENXBL_API_KEY first: export OPENXBL_API_KEY=...\n"
                "Never paste the key into a chat or commit it to a repo."
            )
        xuid, titles = title_history(key)
        ids = [str(t["titleId"]) for t in titles if t.get("titleId")]
        minutes_map = minutes_played(key, xuid, ids) if xuid else {}

    rows = to_rows(titles, minutes_map)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["platform", "id", "name", "minutes", "last_played", "genre",
                        "note", "ach_earned", "ach_total", "ach_pct", "platinum"],
        )
        w.writeheader()
        w.writerows(rows)

    with_time = sum(1 for r in rows if r["minutes"] > 0)
    print(f"{len(rows)} titles -> {a.out}")
    print(f"  with playtime data:    {with_time}")
    print(f"  playtime unavailable:  {sum(1 for r in rows if r['note'] == PLAYTIME_UNAVAILABLE)}")
    if with_time:
        print(f"  total tracked hours:   {sum(r['minutes'] for r in rows) / 60:,.0f}")


if __name__ == "__main__":
    main()
