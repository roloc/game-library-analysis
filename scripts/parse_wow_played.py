#!/usr/bin/env python3
"""Extract per-character /played time from WoW SavedVariables written by the
DataStore/Altoholic addon family, and turn it into a manual.csv row.

Where the file lives (on the machine WoW runs on):

    Windows:  C:\\Program Files (x86)\\World of Warcraft\\_retail_\\WTF\\
              Account\\<ACCOUNT>\\SavedVariables\\DataStore_Characters.lua
    Mac:      /Applications/World of Warcraft/_retail_/WTF/
              Account/<ACCOUNT>/SavedVariables/DataStore_Characters.lua

(_classic_ instead of _retail_ for Classic; both can be passed at once.)

The addon only knows characters that have logged in at least once while it
was installed, so a long-running Altoholic install is complete; a fresh one
needs a lap through the alts first.

Usage:
    python parse_wow_played.py DataStore_Characters.lua [more.lua ...]
    python parse_wow_played.py DataStore_Characters.lua --append data/manual.csv

DataStore's file format has changed across expansions, so this parses
defensively: it scans for character table keys ("Default.Realm.Name") and
any played-time-ish numeric fields near them, and falls back to summing
every recognized played field in the file. If it reports nothing sensible,
the format has moved again - open an issue with (a redacted copy of) the
file rather than trusting a zero.
"""
import argparse
import csv
import datetime
import os
import re
import sys

# seconds-valued fields DataStore has used for total /played across versions
PLAYED_KEYS = r"(?:played|timePlayed|totalPlayed)"
CHAR_KEY = re.compile(r'\["Default\.([^."]+)\.([^."]+)"\]')  # realm, name
PLAYED = re.compile(r'\["' + PLAYED_KEYS + r'"\]\s*=\s*(\d+)')
LOGOUT = re.compile(r'\["lastLogoutTimestamp"\]\s*=\s*(\d+)')


def parse(path):
    """Return ([(realm, name, seconds)], latest_logout_unix)."""
    text = open(path, encoding="utf-8", errors="replace").read()
    chars = []
    latest = 0

    # split on character keys; the segment up to the next character key
    # holds that character's fields (good enough for DataStore's layout)
    marks = list(CHAR_KEY.finditer(text))
    for i, m in enumerate(marks):
        seg = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        played = [int(x) for x in PLAYED.findall(seg)]
        logout = [int(x) for x in LOGOUT.findall(seg)]
        if logout:
            latest = max(latest, max(logout))
        if played:
            # fields are cumulative seconds; the largest is total /played
            chars.append((m.group(1), m.group(2), max(played)))

    if not chars:
        # format drifted - last resort, sum every played field in the file
        allp = [int(x) for x in PLAYED.findall(text)]
        if allp:
            chars.append(("unknown", "all characters (flat scan)", sum(allp)))
    return chars, latest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("lua", nargs="+", help="DataStore_Characters.lua file(s)")
    p.add_argument("--append", metavar="MANUAL_CSV",
                   help="write/update a World of Warcraft row in this manual.csv")
    p.add_argument("--name", default="World of Warcraft",
                   help="row name when appending (e.g. 'World of Warcraft Classic')")
    a = p.parse_args()

    chars, latest = [], 0
    for path in a.lua:
        c, l = parse(path)
        chars.extend(c)
        latest = max(latest, l)

    if not chars:
        sys.exit("No played-time fields found - the DataStore format may have "
                 "changed. Nothing written.")

    chars.sort(key=lambda c: -c[2])
    total_sec = sum(c[2] for c in chars)
    print(f"{'Character':<32} {'Realm':<20} {'Played':>12}")
    for realm, name, sec in chars:
        print(f"{name:<32} {realm:<20} {sec/3600:>10,.1f}h")
    print("-" * 66)
    print(f"{'TOTAL':<53} {total_sec/3600:>10,.1f}h  "
          f"({total_sec/86400:,.1f} days)")

    if a.append:
        last = (datetime.datetime.fromtimestamp(latest).date().isoformat()
                if latest > 100000 else "")
        fields = ["platform", "id", "name", "minutes", "last_played", "genre", "note"]
        rows = []
        if os.path.exists(a.append):
            rows = [r for r in csv.DictReader(open(a.append, encoding="utf-8"))
                    if r["name"] != a.name]
        rows.append({
            "platform": "Battle.net", "id": "", "name": a.name,
            "minutes": total_sec // 60, "last_played": last, "genre": "",
            "note": f"/played via DataStore, {len(chars)} characters",
        })
        with open(a.append, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {a.name} row -> {a.append}")
        print("Now rebuild: python run.py --no-fetch  (after re-merging) or python run.py")


if __name__ == "__main__":
    main()
