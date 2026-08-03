#!/usr/bin/env python3
"""Pull a PlayStation library via the psnawp library into the normalized CSV.

READ BEFORE USING (see references/platforms.md for the full picture):

  * The NPSSO token this needs is PASSWORD-EQUIVALENT for the PSN account —
    psnawp's own docs say never to expose it anywhere. It is read from the
    PSN_NPSSO environment variable and never written to disk, echoed, or
    included in output.
  * psnawp warns that excessive use of the underlying unofficial API can get
    a PSN account temporarily or permanently banned. This script makes one
    paginated pass over the played-titles list and nothing else, which is the
    lightest touch available — but the risk sits with the account owner.
  * After a successful pull, consider signing out of the browser session the
    token came from; that invalidates the token.

Setup:
    pip install PSNAWP

Usage:
    export PSN_NPSSO=...       (or let run.py pass it from config.env)
    python fetch_psn.py --out psn.csv
"""
import argparse
import csv
import os
import sys


def fetch(npsso):
    try:
        from psnawp_api import PSNAWP
    except ImportError:
        sys.exit("psnawp is not installed. Run: pip install PSNAWP")

    client = PSNAWP(npsso).me()
    rows = []
    # title_stats() is the same data the PS5 Game Library shows: play
    # duration, last played, per title, newest first. One paginated pass.
    for t in client.title_stats():
        minutes = 0
        dur = getattr(t, "play_duration", None)
        if dur is not None:
            try:
                minutes = int(dur.total_seconds() // 60)
            except AttributeError:
                pass
        last = getattr(t, "last_played_date_time", None)
        rows.append(
            {
                "platform": "PlayStation",
                "id": getattr(t, "title_id", "") or "",
                "name": getattr(t, "name", None) or "(unknown title)",
                "minutes": minutes,
                "last_played": last.date().isoformat() if last else "",
                "genre": "",
                "note": "",
            }
        )
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="psn.csv")
    a = p.parse_args()

    npsso = os.environ.get("PSN_NPSSO")
    if not npsso:
        sys.exit(
            "Set PSN_NPSSO first (or put it in config.env and use run.py).\n"
            "Sign in at playstation.com, then copy the npsso value from\n"
            "https://ca.account.sony.com/api/v1/ssocookie\n"
            "Never paste the token into a chat or commit it to a repo - it is\n"
            "equivalent to your account password."
        )

    rows = fetch(npsso)
    if not rows:
        sys.exit(
            "PSN returned no titles. The token may be expired (they last about "
            "two months, and logging out of the browser session kills them) - "
            "grab a fresh one and retry."
        )
    rows.sort(key=lambda r: -r["minutes"])
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["platform", "id", "name", "minutes", "last_played", "genre", "note"],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} titles -> {a.out}")
    print(f"  with playtime: {sum(1 for r in rows if r['minutes'] > 0)}")
    print(f"  total hours:   {sum(r['minutes'] for r in rows) / 60:,.0f}")
    print("Note: PSN only reports titles actually played - unplayed purchases")
    print("do not appear, so there is no PSN backlog view.")
    print("Consider logging out of the browser session the NPSSO came from.")


if __name__ == "__main__":
    main()
