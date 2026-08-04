#!/usr/bin/env python3
"""Turn a normalized library CSV into the analysis workbook.

Input CSV columns: platform, id, name, minutes, last_played, genre, note
(genre may be blank - this script fills it from assets/genres.json)

Usage:
    python build_workbook.py library.csv --out steam-library.xlsx

Sheets produced:
    Summary          counts and hours by genre, all live formulas
    Recommendations  written by hand afterwards - see SKILL.md
    Library          every title, sorted by hours, with a Status column
    Backlog          zero-playtime titles, split from untracked pre-2009 ones

Every derived number is a formula against the Library sheet rather than a
hardcoded value, so editing a genre tag or a Status re-drives the Summary.
"""
import argparse
import csv
import json
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

FONT = "Arial"
UNTRACKED = "Playtime untracked (pre-2009)"

HDR = Font(name=FONT, bold=True, color="FFFFFF", size=11)
HDR_FILL = PatternFill("solid", fgColor="2F4858")
BODY = Font(name=FONT, size=10)
BOLD = Font(name=FONT, bold=True, size=10)
ITAL = Font(name=FONT, size=9, italic=True)
INPUT_FONT = Font(name=FONT, size=10, color="0000FF")
INPUT_FILL = PatternFill("solid", fgColor="FFFF99")
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", wrap_text=True)


def load_genres(path):
    with open(path) as f:
        data = json.load(f)
    lookup, order = {}, []
    for genre, names in data.items():
        if genre.startswith("_"):
            continue
        order.append(genre)
        for n in names:
            lookup[n] = genre
    return lookup, sorted(order)


def header(ws, row, labels):
    for i, label in enumerate(labels, 1):
        c = ws.cell(row, i, label)
        c.font, c.fill, c.alignment = HDR, HDR_FILL, CENTER


def build(rows, genre_lookup, genre_order, out, recs=None):
    for r in rows:
        if not r["genre"]:
            r["genre"] = genre_lookup.get(r["name"], "")
    rows.sort(key=lambda r: -r["minutes"])
    multi = len({r["platform"] for r in rows}) > 1

    wb = Workbook()
    lib = wb.active
    lib.title = "Library"

    cols = ["Game", "Hours", "Minutes", "Last Played", "Genre", "Status (fill in)", "Note"]
    if multi:
        cols.insert(1, "Platform")
    header(lib, 1, cols)
    ix = {name: i + 1 for i, name in enumerate(cols)}

    for i, r in enumerate(rows, 2):
        lib.cell(i, ix["Game"], r["name"]).font = BODY
        if multi:
            lib.cell(i, ix["Platform"], r["platform"]).font = BODY
        mcol = lib.cell(i, ix["Minutes"], r["minutes"])
        mcol.font = BODY
        h = lib.cell(i, ix["Hours"], f"={mcol.coordinate}/60")
        h.font, h.number_format = BODY, "0.0"
        lib.cell(i, ix["Last Played"], r["last_played"]).font = BODY
        lib.cell(i, ix["Genre"], r["genre"]).font = BODY
        s = lib.cell(i, ix["Status (fill in)"], "")
        s.font, s.fill = INPUT_FONT, INPUT_FILL
        lib.cell(i, ix["Note"], r["note"]).font = ITAL

    last = len(rows) + 1
    lib.freeze_panes = "A2"
    lib.auto_filter.ref = f"A1:{chr(64 + len(cols))}{last}"
    widths = {"Game": 46, "Platform": 11, "Hours": 9, "Minutes": 10,
              "Last Played": 13, "Genre": 22, "Status (fill in)": 20, "Note": 32}
    for name, i in ix.items():
        lib.column_dimensions[chr(64 + i)].width = widths[name]
    lib.cell(last + 2, 1, "Status column is yours: Loved it / Finished / Bounced / "
                          "Never launched / On deck.").font = ITAL

    MIN = f"Library!${chr(64 + ix['Minutes'])}$2:${chr(64 + ix['Minutes'])}${last}"
    GEN = f"Library!${chr(64 + ix['Genre'])}$2:${chr(64 + ix['Genre'])}${last}"
    NOTE = f"Library!${chr(64 + ix['Note'])}$2:${chr(64 + ix['Note'])}${last}"
    NAME = f"Library!${chr(64 + ix['Game'])}$2:${chr(64 + ix['Game'])}${last}"

    # ---- Backlog ----
    bl = wb.create_sheet("Backlog")
    zeros = [r for r in rows if r["minutes"] == 0]
    # A note on a zero-minute row always means "the data is missing", never
    # "never played" - pre-2009 Steam titles, Xbox titles without a
    # MinutesPlayed stat, etc. Only unannotated zeros are a real backlog.
    never = sorted([r for r in zeros if not r["note"]],
                   key=lambda r: (r["genre"], r["name"].lower()))
    untracked = sorted([r for r in zeros if r["note"] == UNTRACKED],
                       key=lambda r: r["name"].lower())

    bl.cell(1, 1, "Never launched").font = Font(name=FONT, bold=True, size=14)
    bl.cell(2, 1, f"{len(never)} titles with zero recorded playtime, excluding those "
                  f"that predate playtime tracking. Those are listed separately below.").font = ITAL
    header(bl, 4, ["Game", "Genre", "Status (fill in)"])
    row = 5
    for r in never:
        bl.cell(row, 1, r["name"]).font = BODY
        bl.cell(row, 2, r["genre"]).font = BODY
        c = bl.cell(row, 3, "")
        c.font, c.fill = INPUT_FONT, INPUT_FILL
        row += 1
    bl.freeze_panes = "A5"
    if never:
        bl.auto_filter.ref = f"A4:C{row - 1}"

    if untracked:
        row += 2
        bl.cell(row, 1, "Unverifiable - playtime predates tracking").font = Font(
            name=FONT, bold=True, size=12)
        row += 1
        c = bl.cell(row, 1, "Steam began recording playtime in March 2009. A 0 on an "
                            "older title means the data does not exist, not that the "
                            "game was never played. Excluded from the count above.")
        c.font, c.alignment = ITAL, WRAP
        row += 2
        header(bl, row, ["Game", "Genre", "Status (fill in)"])
        row += 1
        for r in untracked:
            bl.cell(row, 1, r["name"]).font = BODY
            bl.cell(row, 2, r["genre"]).font = BODY
            c = bl.cell(row, 3, "")
            c.font, c.fill = INPUT_FONT, INPUT_FILL
            row += 1
    for col, w in zip("ABC", [46, 22, 20]):
        bl.column_dimensions[col].width = w

    # ---- Recommendations ----
    if recs:
        rc = wb.create_sheet("Recommendations", 1)
        rc.cell(1, 1, f"Recommendations — {recs.get('generated', '')}").font = Font(
            name=FONT, bold=True, size=14)
        c = rc.cell(2, 1, recs.get("frame", ""))
        c.font, c.alignment = ITAL, WRAP
        rc.merge_cells(start_row=2, start_column=1, end_row=2, end_column=7)
        rc.row_dimensions[2].height = 42

        row = 4
        header(rc, row, ["Rank", "Game", "Release status", "Why it fits",
                         "Supporting hours in your library", "Watch out for",
                         "Status (fill in)"])
        row += 1
        for p in recs.get("picks", []):
            rc.cell(row, 1, p["rank"]).font = BOLD
            rc.cell(row, 2, p["game"]).font = BOLD
            for col, key in ((3, "status"), (4, "why"), (5, "evidence"), (6, "watch")):
                c = rc.cell(row, col, p.get(key, ""))
                c.font, c.alignment = BODY, WRAP
            c = rc.cell(row, 7, "")
            c.font, c.fill = INPUT_FONT, INPUT_FILL
            rc.row_dimensions[row].height = 64
            row += 1

        for title, items, cols in (
            ("Skip list — what the data rules out", recs.get("skips", []),
             [("game", "Game"), ("verdict", "Verdict"), ("evidence", "The evidence")]),
            ("On hold — early-access rule", recs.get("on_hold", []),
             [("game", "Game"), ("status", "Status"), ("note", "Note")]),
        ):
            if not items:
                continue
            row += 2
            rc.cell(row, 1, title).font = Font(name=FONT, bold=True, size=12)
            row += 1
            header(rc, row, [label for _, label in cols])
            row += 1
            for it in items:
                for col, (key, _) in enumerate(cols, 1):
                    c = rc.cell(row, col, it.get(key, ""))
                    c.font, c.alignment = BODY, WRAP
                rc.row_dimensions[row].height = 42
                row += 1

        row += 2
        c = rc.cell(row, 1, recs.get("attribution", ""))
        c.font, c.alignment = ITAL, WRAP
        for col, w in zip("ABCDEFG", [6, 26, 30, 52, 42, 52, 16]):
            rc.column_dimensions[col].width = w

    # ---- Summary ----
    s = wb.create_sheet("Summary", 0)
    s.cell(1, 1, "Game Library Summary").font = Font(name=FONT, bold=True, size=14)
    stats = [
        ("Total games", f"=COUNTA({NAME})", ""),
        ("Games ever launched", f'=COUNTIF({MIN},">0")', ""),
        ("Never launched (verified)",
         f'=COUNTIFS({MIN},0,{NOTE},"")', "excludes rows whose playtime data is missing"),
        ("Playtime untracked (pre-2009)",
         f'=COUNTIF({NOTE},"{UNTRACKED}")', "0 hours is a data artifact, not a verdict"),
        ("Playtime data missing (other)",
         f'=COUNTIFS({MIN},0,{NOTE},"<>")-COUNTIF({NOTE},"{UNTRACKED}")',
         "e.g. Xbox titles without a MinutesPlayed stat - played, hours unknown"),
        ("Total hours", f"=SUM({MIN})/60", ""),
        ("Games over 100 hours", f'=COUNTIF({MIN},">=6000")', ""),
    ]
    r = 3
    for label, formula, note in stats:
        s.cell(r, 1, label).font = BOLD
        c = s.cell(r, 2, formula)
        c.font = BODY
        if "hours" in label.lower():
            c.number_format = "#,##0"
        if note:
            s.cell(r, 3, note).font = ITAL
        r += 1

    r += 1
    s.cell(r, 1, "Hours by genre").font = Font(name=FONT, bold=True, size=12)
    r += 1
    header(s, r, ["Genre", "Hours", "Games owned", "Never launched (verified)"])
    first = r + 1
    r = first
    for g in genre_order + ["Untagged"]:
        key = '""' if g == "Untagged" else f"$A{r}"
        s.cell(r, 1, g).font = BODY
        c = s.cell(r, 2, f"=SUMIF({GEN},{key},{MIN})/60")
        c.font, c.number_format = BODY, "#,##0"
        s.cell(r, 3, f"=COUNTIF({GEN},{key})").font = BODY
        s.cell(r, 4, f'=COUNTIFS({GEN},{key},{MIN},0,{NOTE},"")').font = BODY
        r += 1
    s.cell(r, 1, "TOTAL").font = BOLD
    for col in (2, 3, 4):
        c = s.cell(r, col, f"=SUM({chr(64 + col)}{first}:{chr(64 + col)}{r - 1})")
        c.font = BOLD
        if col == 2:
            c.number_format = "#,##0"
    for col, w in zip("ABCD", [26, 12, 14, 24]):
        s.column_dimensions[col].width = w
    s.cell(r + 2, 1, "One genre per game, so a title sits in exactly one bucket. "
                     "Untagged is mostly bundle filler, sports and one-offs.").font = ITAL

    wb.save(out)
    return len(rows), len(never), len(untracked)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv_path")
    p.add_argument("--out", default="library.xlsx")
    p.add_argument("--genres", default=os.path.join(
        os.path.dirname(__file__), "..", "assets", "genres.json"))
    p.add_argument("--recs", help="recommendations JSON (see SKILL.md); "
                                  "renders the Recommendations sheet")
    a = p.parse_args()

    with open(a.csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["minutes"] = int(r["minutes"] or 0)
        r.setdefault("note", "")
        r.setdefault("genre", "")
        r.setdefault("platform", "Steam")

    lookup, order = load_genres(a.genres)
    recs = None
    if a.recs and os.path.exists(a.recs):
        with open(a.recs, encoding="utf-8") as f:
            recs = json.load(f)
    total, never, untracked = build(rows, lookup, order, a.out, recs)
    print(f"{total} titles -> {a.out}")
    print(f"  never launched: {never}   untracked pre-2009: {untracked}")
    print("All derived numbers are formulas; Excel/LibreOffice recalculate on open.")
    print("If a program will read this file before a human opens it, recalc first")
    print("(e.g. the xlsx skill's recalc.py in a claude.ai session, or soffice).")


if __name__ == "__main__":
    main()
