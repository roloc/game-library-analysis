#!/usr/bin/env python3
"""Turn a normalized library CSV into a self-contained interactive HTML report.

    python build_report.py data/library.csv --out data/report.html

Everything is inlined - no CDNs, no network - so the file can be opened
anywhere, mailed to someone, or published as-is. Charts are SVG with hover
tooltips; light and dark mode both supported.

Views (they mirror references/analysis.md):
    stat tiles          the headline numbers
    hours by genre      where the time went
    hours per game      whether a genre *holds* attention, not just owns titles
    top 20 games        the outlier check, at a glance
    recency scatter     every played title by last-played date vs hours
    backlog by genre    played vs never-launched counts - the gold seam
"""
import argparse
import csv
import datetime
import html
import json
import os

# Palette: the dataviz reference instance (validated; do not eyeball-tweak).
# Categorical slots 1-2 only; text/chrome roles come from the same reference.
LIGHT = dict(surface="#fcfcfb", page="#f9f9f7", ink="#0b0b0b", ink2="#52514e",
             muted="#898781", grid="#e1e0d9", axis="#c3c2b7", s1="#2a78d6",
             s2="#eb6834", s3="#1baf7a", border="rgba(11,11,11,0.10)")
DARK = dict(surface="#1a1a19", page="#0d0d0d", ink="#ffffff", ink2="#c3c2b7",
            muted="#898781", grid="#2c2c2a", axis="#383835", s1="#3987e5",
            s2="#d95926", s3="#199e70", border="rgba(255,255,255,0.10)")

UNTRACKED = "Playtime untracked (pre-2009)"


def load(csv_path, genres_path):
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    lookup = {}
    if os.path.exists(genres_path):
        with open(genres_path) as f:
            for genre, names in json.load(f).items():
                if not genre.startswith("_"):
                    for n in names:
                        lookup[_norm(n)] = genre
    for r in rows:
        r["minutes"] = int(r["minutes"] or 0)
        r["genre"] = r.get("genre") or lookup.get(_norm(r["name"]), "")
        r["note"] = r.get("note", "")
    return rows


def esc(s):
    return html.escape(str(s), quote=True)


def hbar_chart(items, color_var, value_fmt, unit=""):
    """Horizontal bars: [(label, value, hover_extra)]. Flat baseline, rounded
    data end, direct value labels, hover tooltip per bar."""
    if not items:
        return "<p class='empty'>No data.</p>"
    W, ROW, LAB, PAD_R = 720, 30, 190, 84
    plot_w = W - LAB - PAD_R
    vmax = max(v for _, v, _ in items) or 1
    H = len(items) * ROW + 8
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" style="width:100%;height:auto">']
    for gx in range(1, 5):
        x = LAB + plot_w * gx / 4
        out.append(f'<line x1="{x:.0f}" y1="0" x2="{x:.0f}" y2="{H-6}" '
                   f'stroke="var(--grid)" stroke-width="1"/>')
    for i, (label, v, extra) in enumerate(items):
        y = i * ROW + 5
        bw = max(plot_w * v / vmax, 2)
        r = min(4, bw / 2)
        short = label if len(label) <= 26 else label[:25] + "…"
        out.append(f'<text x="{LAB-8}" y="{y+14}" text-anchor="end" class="lab">'
                   f'{esc(short)}</text>')
        out.append(
            f'<path d="M{LAB} {y} h{bw - r:.1f} a{r:.1f} {r:.1f} 0 0 1 {r:.1f} {r:.1f} '
            f'v{20 - 2 * r:.1f} a{r:.1f} {r:.1f} 0 0 1 {-r:.1f} {r:.1f} h{-(bw - r):.1f} z" '
            f'fill="var({color_var})" class="mark" data-tip="{esc(label)} — {esc(extra)}"/>')
        out.append(f'<text x="{LAB+bw+6}" y="{y+14}" class="val">'
                   f'{value_fmt(v)}{unit}</text>')
    out.append(f'<line x1="{LAB}" y1="0" x2="{LAB}" y2="{H-6}" '
               f'stroke="var(--axis)" stroke-width="1"/>')
    out.append("</svg>")
    return "".join(out)


def genre_chips(chart_id, pts_genres):
    """Filter chips for a scatter: up to 3 genres colorable at once, top 3
    pre-selected. pts_genres: iterable of genre strings (one per dot)."""
    counts = {}
    for g in pts_genres:
        g = g or "Untagged"
        counts[g] = counts.get(g, 0) + 1
    chips = "".join(
        f'<button class="chip" data-genre="{esc(g)}">{esc(g)} '
        f'<span class="chip-n">{n}</span></button>'
        for g, n in sorted(counts.items(), key=lambda kv: -kv[1]))
    return (f'<div class="chips genre-filter" data-target="{chart_id}">{chips}</div>'
            f'<p class="desc" style="margin:4px 0 10px">Pick up to three genres '
            f'to color their dots; everything else grays out. The three biggest '
            f'start selected.</p>')


def scatter_chart(pts, y_max, svg_id):
    """Recency scatter: [(date, hours, name, genre)]. Hover per point;
    genre-colorable via chips."""
    if not pts:
        return "<p class='empty'>No dated plays.</p>"
    W, H, L, B, T, R = 720, 340, 52, 30, 12, 16
    d0 = min(p[0] for p in pts)
    d1 = max(p[0] for p in pts)
    span = max((d1 - d0).days, 1)
    pw, ph = W - L - R, H - T - B

    def X(d):
        return L + pw * (d - d0).days / span

    def Y(h):
        return T + ph * (1 - min(h, y_max) / y_max)

    out = [f'<svg id="{svg_id}" viewBox="0 0 {W} {H}" role="img" style="width:100%;height:auto">']
    for gy in range(5):
        y = T + ph * gy / 4
        val = y_max * (4 - gy) / 4
        out.append(f'<line x1="{L}" y1="{y:.0f}" x2="{W-R}" y2="{y:.0f}" '
                   f'stroke="var(--grid)" stroke-width="1"/>')
        out.append(f'<text x="{L-8}" y="{y+4:.0f}" text-anchor="end" class="tick">'
                   f'{val:.0f}h</text>')
    for yr in range(d0.year + 1, d1.year + 1, 2):
        x = X(datetime.date(yr, 1, 1))
        out.append(f'<text x="{x:.0f}" y="{H-8}" text-anchor="middle" class="tick">{yr}</text>')
    clipped = []
    for d, h, name, genre in pts:
        if h > y_max:
            clipped.append((h, name))
        out.append(
            f'<circle cx="{X(d):.1f}" cy="{Y(h):.1f}" r="4.5" fill="var(--s1)" '
            f'fill-opacity="0.55" stroke="var(--surface)" stroke-width="1" class="mark" '
            f'data-genre="{esc(genre or "Untagged")}" '
            f'data-tip="{esc(name)} — {h:,.0f}h, last played {d}'
            + (f" [{esc(genre)}]" if genre else "") + '"/>')
    out.append(f'<line x1="{L}" y1="{T+ph}" x2="{W-R}" y2="{T+ph}" '
               f'stroke="var(--axis)" stroke-width="1"/>')
    out.append("</svg>")
    if clipped:
        names = ", ".join(f"{esc(n)} {h:,.0f}h" for h, n in sorted(clipped, reverse=True))
        out.append(f"<p class='desc' style='margin-top:8px'>Pinned at the top edge "
                   f"(beyond the {y_max:.0f}h axis): {names}.</p>")
    return "".join(out)


def quadrant_chart(pts, svg_id):
    """Completion % (x) vs hours (y, log scale). pts: (pct, hours, name,
    platinum, genre). The chart that keeps hours honest: finished finite
    games live bottom-right, endless loops top-left."""
    if not pts:
        return ("<p class='desc'>No completion data yet. Steam achievements "
                "need the profile's base <em>\"My profile\"</em> privacy set "
                "to Public while pulling — Game Details alone (enough for the "
                "library) is not enough, and Steam blocks even your own API "
                "key without it. Flip it, re-run <code>python run.py</code>, "
                "and flip it back if you like; the cache persists. Xbox and "
                "PlayStation completion data arrives automatically with "
                "their pulls.</p>")
    import math
    W, H, L, B, T, R = 720, 380, 52, 30, 16, 16
    pw, ph = W - L - R, H - T - B
    y_max = max(h for _, h, _, _, _ in pts)
    log_max = math.log10(max(y_max, 10) * 1.3)

    def X(p):
        return L + pw * p / 100

    def Y(h):
        return T + ph * (1 - math.log10(max(h, 0.5) + 1) / log_max)

    out = [f'<svg id="{svg_id}" viewBox="0 0 {W} {H}" role="img" style="width:100%;height:auto">']
    for tick in (1, 10, 100, 1000):
        if tick > y_max * 1.3:
            break
        y = Y(tick)
        out.append(f'<line x1="{L}" y1="{y:.0f}" x2="{W-R}" y2="{y:.0f}" '
                   f'stroke="var(--grid)" stroke-width="1"/>')
        out.append(f'<text x="{L-8}" y="{y+4:.0f}" text-anchor="end" class="tick">'
                   f'{tick:,}h</text>')
    for p in (0, 25, 50, 75, 100):
        x = X(p)
        out.append(f'<text x="{x:.0f}" y="{H-8}" text-anchor="middle" class="tick">{p}%</text>')
    # quadrant divider at 50%
    out.append(f'<line x1="{X(50):.0f}" y1="{T}" x2="{X(50):.0f}" y2="{T+ph}" '
               f'stroke="var(--axis)" stroke-width="1" stroke-dasharray="4 4"/>')
    for label, x, y, anchor in (
            ("the loops", X(2), T + 14, "start"),
            ("100%'d obsessions", X(98), T + 14, "end"),
            ("sampled / early", X(2), T + ph - 8, "start"),
            ("finished campaigns", X(98), T + ph - 8, "end")):
        out.append(f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" '
                   f'class="tick" font-style="italic">{label}</text>')
    for pct, h, name, plat, genre in pts:
        tip = (f"{name} — {pct:.0f}% complete, {h:,.0f}h"
               + (", PLATINUM" if plat else "")
               + (f" [{genre}]" if genre else ""))
        # platinum reads as an inked ring so fill color stays free for genres
        ring = ('stroke="var(--ink)" stroke-width="1.5" r="6"' if plat
                else 'stroke="var(--surface)" stroke-width="1" r="4.5"')
        out.append(
            f'<circle cx="{X(pct):.1f}" cy="{Y(h):.1f}" {ring} fill="var(--s1)" '
            f'fill-opacity="0.6" class="mark" '
            f'data-genre="{esc(genre or "Untagged")}" data-tip="{esc(tip)}"/>')
    out.append(f'<line x1="{L}" y1="{T+ph}" x2="{W-R}" y2="{T+ph}" '
               f'stroke="var(--axis)" stroke-width="1"/>')
    out.append("</svg>")
    return "".join(out)


def stacked_chart(items):
    """Per genre: played vs never-launched counts. Two series, legend, 2px
    surface gap between segments."""
    if not items:
        return "<p class='empty'>No data.</p>"
    W, ROW, LAB, PAD_R = 720, 30, 190, 60
    plot_w = W - LAB - PAD_R
    vmax = max(p + n for _, p, n in items) or 1
    H = len(items) * ROW + 8
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" style="width:100%;height:auto">']
    for i, (label, played, never) in enumerate(items):
        y = i * ROW + 5
        short = label if len(label) <= 26 else label[:25] + "…"
        out.append(f'<text x="{LAB-8}" y="{y+14}" text-anchor="end" class="lab">{esc(short)}</text>')
        pw_ = plot_w * played / vmax
        nw = plot_w * never / vmax
        out.append(f'<rect x="{LAB}" y="{y}" width="{max(pw_,1):.1f}" height="20" '
                   f'fill="var(--s1)" stroke="var(--surface)" stroke-width="2" class="mark" '
                   f'data-tip="{esc(label)} — {played} played"/>')
        if never:
            out.append(f'<rect x="{LAB+pw_:.1f}" y="{y}" width="{max(nw,1):.1f}" height="20" '
                       f'fill="var(--s2)" stroke="var(--surface)" stroke-width="2" class="mark" '
                       f'data-tip="{esc(label)} — {never} never launched"/>')
        out.append(f'<text x="{LAB+pw_+nw+6:.1f}" y="{y+14}" class="val">{played+never}</text>')
    out.append("</svg>")
    return "".join(out)


def recs_html(recs):
    if not recs:
        # The pipeline measures; recommendations are the judgment pass.
        # Render the absence as instructions rather than silence.
        return """<section><h2>Recommendations</h2>
<p class="desc">Not generated yet — and <code>run.py</code> alone never will:
the charts above are measurements, but recommendations are a judgment pass.
Have Claude read <code>SKILL.md</code> and run the analysis pass over your
data — it studies the library, verifies release statuses and known issues,
and writes <code>data/recommendations.json</code>. The next
<code>python run.py --no-fetch</code> renders ranked picks with cited hours,
a skip list, and a scoreboard right here.</p></section>"""
    cards = []
    for p in recs.get("picks", []):
        cards.append(f"""<div class="pick">
<div class="pick-head"><span class="pick-rank">#{p['rank']}</span>
<span class="pick-name">{esc(p['game'])}</span>
<span class="pick-status">{esc(p['status'])}</span></div>
<p class="pick-why">{esc(p['why'])}</p>
<p class="pick-ev">Evidence: {esc(p['evidence'])}</p>
<p class="pick-watch">Watch out for: {esc(p['watch'])}</p></div>""")

    def mini_table(title, items, cols):
        if not items:
            return ""
        rows_html = "".join(
            "<tr>" + "".join(f"<td>{esc(it.get(k, ''))}</td>" for k, _ in cols) + "</tr>"
            for it in items)
        head = "".join(f"<th>{h}</th>" for _, h in cols)
        return (f"<h3>{esc(title)}</h3><div class='tablewrap'><table>"
                f"<tr>{head}</tr>{rows_html}</table></div>")

    return f"""<section><h2>Recommendations</h2>
<p class="desc">{esc(recs.get('frame', ''))}</p>
{mini_table('Scoreboard — picks that got played', recs.get('outcomes', []),
            [('game', 'Game'), ('recommended', 'The pick'), ('result', 'What happened'),
             ('verdict', 'Verdict')])}
{''.join(cards)}
{mini_table('Skip list — what the data rules out', recs.get('skips', []),
            [('game', 'Game'), ('verdict', 'Verdict'), ('evidence', 'The evidence')])}
{mini_table('On hold — early-access rule', recs.get('on_hold', []),
            [('game', 'Game'), ('status', 'Status'), ('note', 'Note')])}
<p class="desc" style="margin-top:12px">{esc(recs.get('attribution', ''))}</p>
</section>"""


BOUNCE_MAX_MIN = 240        # "briefly played" ceiling, total across platforms
BOUNCE_GRACE_DAYS = 180     # newer than this = too early to judge
BOUNCE_DONE_PCT = 50        # completion above this = short game finished, not a bounce


def _norm(name):
    return "".join(c for c in name.lower() if c.isalnum())


def compute_bounces(rows):
    """Games opened, briefly played, never returned to — judged per game
    across platforms, not per store copy. Returns (bounced, too_early_count).
    Rows with data-gap notes are never judged (their zeros are artifacts)."""
    groups = {}
    for r in rows:
        g = groups.setdefault(_norm(r["name"]), {
            "name": r["name"], "platforms": [], "minutes": 0, "last": "",
            "genre": "", "pct": None})
        g["platforms"].append(r["platform"])
        g["genre"] = g["genre"] or r.get("genre", "")
        if not r["note"]:
            g["minutes"] += r["minutes"]
            g["last"] = max(g["last"], r["last_played"] or "")
            if r.get("ach_pct") not in (None, ""):
                p = float(r["ach_pct"])
                g["pct"] = p if g["pct"] is None else max(g["pct"], p)
        else:
            # a data-gap note poisons the judgement: hours exist somewhere
            # we can't see (pre-2009 Steam, Xbox stat gaps), so never judge
            g["unjudgeable"] = True

    cutoff = (datetime.date.today()
              - datetime.timedelta(days=BOUNCE_GRACE_DAYS)).isoformat()
    bounced, too_early = [], 0
    for g in groups.values():
        launched = g["minutes"] > 0 or g["last"]
        if g.get("unjudgeable") or not launched or g["minutes"] > BOUNCE_MAX_MIN:
            continue
        if g["pct"] is not None and g["pct"] >= BOUNCE_DONE_PCT:
            continue  # short and finished - it clicked, it just ended
        if g["last"] and g["last"] > cutoff:
            too_early += 1
            continue
        bounced.append(g)
    bounced.sort(key=lambda g: g["last"], reverse=True)
    return bounced, too_early


def build(rows, out_path, src_name, recs=None):
    played = [r for r in rows if r["minutes"] > 0]
    # a note on a zero-minute row means "data missing", not "never played"
    never = [r for r in rows if r["minutes"] == 0 and not r["note"]]
    nodata = [r for r in rows if r["minutes"] == 0 and r["note"]]
    total_h = sum(r["minutes"] for r in rows) / 60
    platforms = sorted({r["platform"] for r in rows})

    by_genre = {}
    for r in rows:
        g = r["genre"] or "Untagged"
        by_genre.setdefault(g, []).append(r)

    tagged = {g: rs for g, rs in by_genre.items() if g != "Untagged"}
    genre_hours = sorted(
        ((g, sum(r["minutes"] for r in rs) / 60, rs) for g, rs in tagged.items()),
        key=lambda t: -t[1])
    hours_chart = hbar_chart(
        [(g, h, f"{h:,.0f}h across {len(rs)} titles") for g, h, rs in genre_hours],
        "--s1", lambda v: f"{v:,.0f}", "h")

    # concentration: hours per *launched* game - does the genre hold attention?
    conc = sorted(
        ((g, (sum(r['minutes'] for r in rs) / 60) / max(sum(1 for r in rs if r['minutes'] > 0), 1),
          sum(1 for r in rs if r["minutes"] > 0))
         for g, h, rs in genre_hours),
        key=lambda t: -t[1])
    conc_chart = hbar_chart(
        [(g, hpg, f"{hpg:,.0f}h per launched game ({n} launched)") for g, hpg, n in conc],
        "--s2", lambda v: f"{v:,.0f}", "h")

    top = sorted(rows, key=lambda r: -r["minutes"])[:20]
    top_chart = hbar_chart(
        [(r["name"], r["minutes"] / 60,
          f"{r['minutes']/60:,.0f}h — {r['genre'] or 'untagged'}"
          + (f", last played {r['last_played']}" if r["last_played"] else ""))
         for r in top],
        "--s1", lambda v: f"{v:,.0f}", "h")

    pts = []
    for r in played:
        if r["last_played"]:
            try:
                d = datetime.date.fromisoformat(r["last_played"][:10])
                pts.append((d, r["minutes"] / 60, r["name"], r.get("genre", "")))
            except ValueError:
                pass
    pts.sort()
    hours_sorted = sorted((p[1] for p in pts), reverse=True)
    y_max = (hours_sorted[3] * 1.1) if len(hours_sorted) > 8 else (hours_sorted[0] if hours_sorted else 1)
    y_max = max(round(y_max / 25) * 25, 25)
    recency = genre_chips("recency-svg", (p[3] for p in pts)) \
        + scatter_chart(pts, y_max, "recency-svg")

    # completion signal: only rows with real playtime AND achievement data
    qpts = []
    for r in played:
        pct = r.get("ach_pct")
        if pct not in (None, ""):
            qpts.append((float(pct), r["minutes"] / 60, r["name"],
                         r.get("platinum") == "yes", r.get("genre", "")))
    quadrant = genre_chips("quadrant-svg", (p[4] for p in qpts)) \
        + quadrant_chart(qpts, "quadrant-svg")
    credits_rows = sorted(
        [r for r in played
         if r.get("platinum") == "yes"
         or (r.get("ach_pct") not in (None, "") and float(r["ach_pct"]) >= 70)],
        key=lambda r: -float(r.get("ach_pct") or 0))
    credits_html = "".join(
        f"<tr><td>{esc(r['name'])}</td><td>{esc(r['platform'])}</td>"
        f"<td class='num'>{r['minutes']/60:,.0f}</td>"
        f"<td class='num'>{float(r.get('ach_pct') or 0):.0f}%</td>"
        f"<td>{'Platinum' if r.get('platinum') == 'yes' else 'Achievements'}</td></tr>"
        for r in credits_rows)

    bounced, too_early = compute_bounces(rows)
    bounce_by_genre = {}
    for g in bounced:
        key = g["genre"] or "Untagged"
        bounce_by_genre[key] = bounce_by_genre.get(key, 0) + 1
    bounce_chart = hbar_chart(
        sorted(((genre, n, f"{n} bounced") for genre, n in bounce_by_genre.items()),
               key=lambda t: -t[1]),
        "--s2", lambda v: f"{v:.0f}")
    bounce_cells = []
    for g in bounced:
        hours = "&lt;0.1" if g["minutes"] == 0 else f"{g['minutes'] / 60:,.1f}"
        pct = f"{g['pct']:.0f}%" if g["pct"] is not None else ""
        plats = "/".join(sorted(set(g["platforms"])))
        bounce_cells.append(
            f"<tr><td>{esc(g['name'])}</td><td>{esc(plats)}</td>"
            f"<td class='num'>{hours}</td><td>{esc(g['last'] or '—')}</td>"
            f"<td>{esc(g['genre'])}</td><td class='num'>{pct}</td></tr>")
    bounce_rows = "".join(bounce_cells)

    backlog = stacked_chart(sorted(
        ((g, sum(1 for r in rs if r["minutes"] > 0),
          sum(1 for r in rs if r["minutes"] == 0 and not r["note"]))
         for g, rs in tagged.items()),
        key=lambda t: -(t[1] + t[2])))

    table_rows = "".join(
        f"<tr><td>{esc(r['name'])}</td><td>{esc(r['platform'])}</td>"
        f"<td class='num'>{r['minutes']/60:,.1f}</td><td>{esc(r['last_played'])}</td>"
        f"<td>{esc(r['genre'])}</td><td>{esc(r['note'])}</td></tr>"
        for r in sorted(rows, key=lambda r: -r["minutes"]))

    def tile(value, label, note=""):
        n = f"<div class='tile-note'>{esc(note)}</div>" if note else ""
        return (f"<div class='tile'><div class='tile-v'>{value}</div>"
                f"<div class='tile-l'>{esc(label)}</div>{n}</div>")

    tiles = "".join([
        tile(f"{len(rows):,}", "titles"),
        tile(f"{total_h:,.0f}", "hours logged"),
        tile(f"{len(played):,}", "with playtime"),
        tile(f"{len(never):,}", "never launched", "verified - data gaps excluded"),
        tile(f"{len(nodata):,}", "playtime data missing", "pre-2009 Steam, Xbox stat gaps"),
    ])

    today = datetime.date.today().isoformat()
    css_vars = lambda p: ";".join(f"--{k}:{v}" for k, v in p.items())
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Game Library Report</title>
<style>
:root {{ color-scheme: light; {css_vars(LIGHT)} }}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) {{ color-scheme: dark; {css_vars(DARK)} }}
}}
:root[data-theme="dark"] {{ color-scheme: dark; {css_vars(DARK)} }}
* {{ box-sizing: border-box; margin: 0 }}
body {{ background: var(--page); color: var(--ink);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; padding: 28px 20px 60px }}
main {{ max-width: 860px; margin: 0 auto }}
h1 {{ font-size: 22px; font-weight: 650 }}
.sub {{ color: var(--ink2); margin: 4px 0 24px; font-size: 13px }}
section {{ background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 18px 20px 12px; margin-bottom: 18px }}
h2 {{ font-size: 15px; font-weight: 650; margin-bottom: 2px }}
.desc {{ color: var(--ink2); font-size: 13px; margin-bottom: 14px }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px; margin-bottom: 18px }}
.tile {{ background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px }}
.tile-v {{ font-size: 26px; font-weight: 650 }}
.tile-l {{ color: var(--ink2); font-size: 12.5px }}
.tile-note {{ color: var(--muted); font-size: 11px; margin-top: 2px }}
svg {{ overflow: visible }}
.lab {{ font: 12px system-ui, sans-serif; fill: var(--ink2) }}
.val {{ font: 12px system-ui, sans-serif; fill: var(--ink); font-variant-numeric: tabular-nums }}
.tick {{ font: 11px system-ui, sans-serif; fill: var(--muted); font-variant-numeric: tabular-nums }}
.mark {{ cursor: default }} .mark:hover {{ opacity: .85 }}
.legend {{ display: flex; gap: 16px; font-size: 12.5px; color: var(--ink2); margin-bottom: 10px }}
.chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 4px }}
.chip {{ font: 12px system-ui, sans-serif; color: var(--ink2); background: none;
  border: 1px solid var(--border); border-radius: 999px; padding: 3px 10px;
  cursor: pointer; display: inline-flex; align-items: center; gap: 6px }}
.chip:hover {{ border-color: var(--muted) }}
.chip.on {{ color: var(--ink); font-weight: 600 }}
.chip.on::before {{ content: ""; width: 9px; height: 9px; border-radius: 50%;
  background: var(--chip-c, var(--s1)) }}
.chip-n {{ color: var(--muted); font-variant-numeric: tabular-nums }}
.legend span::before {{ content: ""; display: inline-block; width: 10px; height: 10px;
  border-radius: 2px; margin-right: 6px }}
.legend .l1::before {{ background: var(--s1) }} .legend .l2::before {{ background: var(--s2) }}
#tip {{ position: fixed; pointer-events: none; background: var(--ink); color: var(--page);
  padding: 6px 10px; border-radius: 6px; font-size: 12.5px; max-width: 320px;
  opacity: 0; transition: opacity .08s; z-index: 9 }}
details {{ margin-top: 6px }} summary {{ cursor: pointer; color: var(--ink2); font-size: 13.5px }}
.pick {{ border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; margin-bottom: 10px }}
.pick-head {{ display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap }}
.pick-rank {{ font-weight: 700; color: var(--s1) }}
.pick-name {{ font-weight: 650 }}
.pick-status {{ font-size: 12px; color: var(--ink2); margin-left: auto }}
.pick-why {{ margin-top: 6px; font-size: 14px }}
.pick-ev {{ margin-top: 6px; font-size: 12.5px; color: var(--ink2); font-variant-numeric: tabular-nums }}
.pick-watch {{ margin-top: 4px; font-size: 12.5px; color: var(--ink2) }}
h3 {{ font-size: 13.5px; font-weight: 650; margin: 18px 0 4px }}
table {{ border-collapse: collapse; width: 100%; font-size: 12.5px; margin-top: 10px }}
th, td {{ text-align: left; padding: 4px 10px 4px 0; border-bottom: 1px solid var(--grid) }}
th {{ color: var(--ink2); font-weight: 600 }}
td.num {{ font-variant-numeric: tabular-nums }}
.tablewrap {{ overflow-x: auto; max-height: 480px; overflow-y: auto }}
</style></head><body><main>
<h1>Game Library Report</h1>
<p class="sub">{esc(' · '.join(f"{p} {sum(1 for r in rows if r['platform'] == p):,}" for p in platforms))}
 · {len(rows):,} titles · generated {today} from {esc(src_name)}
 · analysis conventions: hours are the ground truth</p>

<div class="tiles">{tiles}</div>

{recs_html(recs)}

<section><h2>Hours by genre</h2>
<p class="desc">Where the time actually went. Untagged titles are excluded.</p>
{hours_chart}</section>

<section><h2>Hours per launched game</h2>
<p class="desc">The concentration signal: whether a genre <em>holds</em> attention
once launched, not how many titles it accumulated. High bar + few titles = home
genre; long ownership list + low bar = a hobby being shopped for.</p>
{conc_chart}</section>

<section><h2>Top 20 games</h2>
<p class="desc">The outlier check — before trusting any genre total, see which
single titles carry it.</p>
{top_chart}</section>

<section><h2>Recency</h2>
<p class="desc">Every played, dated title: when it was last touched vs total
hours (axis clipped; anything beyond it is pinned to the top edge and listed
below). A dense band of low-hour dots on the right edge means sampling, not
playing.</p>
{recency}</section>

<section><h2>The completion signal</h2>
<p class="desc">Hours measure retention, and retention only means something
for games without an ending. This view adds the second axis: achievement /
trophy completion. Endless loops live top-left and are fairly measured in
hours; <em>finished campaigns live bottom-right</em>, and they were being
erased by every hours-only chart above. A ringed dot is a PSN platinum. Only
played titles with achievement data appear.</p>
{quadrant}
<h3>Rolled credits — completed or near-completed ({len(credits_rows)})</h3>
<div class="tablewrap"><table>
<tr><th>Game</th><th>Platform</th><th>Hours</th><th>Completion</th><th>Signal</th></tr>
{credits_html}</table></div>
</section>

<section><h2>What didn't click</h2>
<p class="desc">Opened, briefly played, never went back: under
{BOUNCE_MAX_MIN // 60} hours total <em>across all platforms</em>, untouched
for {BOUNCE_GRACE_DAYS}+ days, and not simply a short game you finished
(completion ≥ {BOUNCE_DONE_PCT}% is exempt). Games whose playtime data is
missing are never judged. {too_early} recent low-hour starts are excluded as
too early to call. The genre chart is where purchases go to die; the table
is the full honor roll.</p>
{bounce_chart}
<h3>The full list ({len(bounced)})</h3>
<div class="tablewrap"><table>
<tr><th>Game</th><th>Platform</th><th>Hours</th><th>Last touched</th><th>Genre</th><th>Completion</th></tr>
{bounce_rows}</table></div>
</section>

<section><h2>Backlog by genre</h2>
<p class="desc">Played vs never-launched, tagged genres only. Never-launched
titles in a high hours-per-game genre are the best recommendations available —
already owned, evidence overwhelming. Titles whose playtime data is missing
(pre-2009 Steam, Xbox stat gaps) are excluded from both segments.</p>
<div class="legend"><span class="l1">Played</span><span class="l2">Never launched</span></div>
{backlog}</section>

<section><h2>Full library</h2>
<details><summary>Show table ({len(rows):,} rows)</summary>
<div class="tablewrap"><table>
<tr><th>Game</th><th>Platform</th><th>Hours</th><th>Last played</th><th>Genre</th><th>Note</th></tr>
{table_rows}</table></div></details></section>

<div id="tip" role="status"></div>
<script>
// Genre filter: up to 3 genres colored at once (slots keep their color while
// selected; deselecting frees the slot). Everything else drops to gray.
const SLOTS = ['--s1', '--s2', '--s3'];
document.querySelectorAll('.genre-filter').forEach(bar => {{
  const svg = document.getElementById(bar.dataset.target);
  if (!svg) return;
  const chips = [...bar.querySelectorAll('.chip')];
  const active = new Map();  // genre -> slot var
  const paint = () => {{
    svg.querySelectorAll('.mark').forEach(dot => {{
      const slot = active.get(dot.dataset.genre);
      if (active.size === 0) {{
        dot.setAttribute('fill', 'var(--s1)');
        dot.setAttribute('fill-opacity', dot.dataset.dim || '0.55');
      }} else if (slot) {{
        dot.setAttribute('fill', `var(${{slot}})`);
        dot.setAttribute('fill-opacity', '0.85');
      }} else {{
        dot.setAttribute('fill', 'var(--muted)');
        dot.setAttribute('fill-opacity', '0.25');
      }}
    }});
    chips.forEach(ch => {{
      const slot = active.get(ch.dataset.genre);
      ch.classList.toggle('on', !!slot);
      ch.style.setProperty('--chip-c', slot ? `var(${{slot}})` : '');
    }});
  }};
  bar.addEventListener('click', e => {{
    const ch = e.target.closest('.chip');
    if (!ch) return;
    const g = ch.dataset.genre;
    if (active.has(g)) active.delete(g);
    else {{
      if (active.size >= 3) active.delete(active.keys().next().value);
      const used = new Set(active.values());
      active.set(g, SLOTS.find(s => !used.has(s)));
    }}
    paint();
  }});
  chips.slice(0, 3).forEach((ch, i) => active.set(ch.dataset.genre, SLOTS[i]));
  paint();
}});

const tip = document.getElementById('tip');
document.addEventListener('mousemove', e => {{
  const m = e.target.closest('.mark');
  if (m && m.dataset.tip) {{
    tip.textContent = m.dataset.tip;
    tip.style.opacity = 1;
    const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8);
    const y = Math.min(e.clientY + 14, innerHeight - tip.offsetHeight - 8);
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }} else tip.style.opacity = 0;
}});
</script>
</main></body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv_path")
    p.add_argument("--out", default="report.html")
    p.add_argument("--genres", default=os.path.join(
        os.path.dirname(__file__), "..", "assets", "genres.json"))
    p.add_argument("--recs", help="recommendations JSON; renders a section")
    a = p.parse_args()
    rows = load(a.csv_path, a.genres)
    recs = None
    if a.recs and os.path.exists(a.recs):
        with open(a.recs, encoding="utf-8") as f:
            recs = json.load(f)
    build(rows, a.out, os.path.basename(a.csv_path), recs)
    print(f"{len(rows)} titles -> {a.out}")


if __name__ == "__main__":
    main()
