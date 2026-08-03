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

Caveats (see references/platforms.md):
  - Xbox playtime coverage is patchier than Steam's. Last-played dates and the
    title list itself are reliable; minutes-played frequently is not exposed,
    in which case rows carry 0 minutes and a note saying playtime was
    unavailable rather than implying the game was never touched.
  - OpenXBL is a third-party service and its response shapes drift. This
    script parses defensively and skips fields it cannot find rather than
    crashing; check the printed summary against your console's own library.
"""
import argparse
import csv
import json
import os
import sys
import urllib.request

API = "https://xbl.io/api/v2"
PLAYTIME_UNAVAILABLE = "Playtime not exposed by Xbox API"


def _get(path, key):
    req = urllib.request.Request(
        f"{API}/{path}",
        headers={"X-Authorization": key, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def title_history(key):
    d = _get("player/titleHistory", key)
    titles = d.get("titles")
    if not titles:
        sys.exit(
            "OpenXBL returned no titles. Check that the API key is valid and "
            "the account has played games on this profile."
        )
    return titles


def to_rows(titles):
    rows = []
    for t in titles:
        # Skip non-game entries (apps, system software) when the API labels them
        if t.get("type") and t["type"] != "Game":
            continue
        hist = t.get("titleHistory") or {}
        last = (hist.get("lastTimePlayed") or "")[:10]  # ISO datetime -> YYYY-MM-DD

        # Minutes played appears under different keys depending on endpoint
        # vintage; take whatever is present, else mark it unavailable.
        mins = 0
        note = PLAYTIME_UNAVAILABLE
        for source in (t, hist, t.get("stats") or {}):
            for k in ("minutesPlayed", "minutes_played", "playTime"):
                v = source.get(k)
                if v not in (None, ""):
                    try:
                        mins = int(v)
                        note = ""
                    except (TypeError, ValueError):
                        pass
        rows.append(
            {
                "platform": "Xbox",
                "id": t.get("titleId", ""),
                "name": t.get("name", "(unknown title)"),
                "minutes": mins,
                "last_played": last,
                "genre": "",
                "note": note,
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
        titles = d.get("titles") or d
    else:
        key = os.environ.get("OPENXBL_API_KEY")
        if not key:
            sys.exit(
                "Set OPENXBL_API_KEY first: export OPENXBL_API_KEY=...\n"
                "Never paste the key into a chat or commit it to a repo."
            )
        titles = title_history(key)

    rows = to_rows(titles)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["platform", "id", "name", "minutes", "last_played", "genre", "note"],
        )
        w.writeheader()
        w.writerows(rows)

    with_time = sum(1 for r in rows if r["minutes"] > 0)
    print(f"{len(rows)} titles -> {a.out}")
    print(f"  with playtime data:    {with_time}")
    print(f"  playtime unavailable:  {sum(1 for r in rows if r['note'] == PLAYTIME_UNAVAILABLE)}")
    if with_time:
        print(f"  total tracked hours:   {sum(r['minutes'] for r in rows) / 60:,.0f}")
    print("Merge with other platforms by concatenating CSVs (keep one header row),")
    print("then rebuild: python scripts/build_workbook.py merged.csv --out library.xlsx")


if __name__ == "__main__":
    main()
