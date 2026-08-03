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
             s2="#eb6834", border="rgba(11,11,11,0.10)")
DARK = dict(surface="#1a1a19", page="#0d0d0d", ink="#ffffff", ink2="#c3c2b7",
            muted="#898781", grid="#2c2c2a", axis="#383835", s1="#3987e5",
            s2="#d95926", border="rgba(255,255,255,0.10)")

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
                        lookup[n] = genre
    for r in rows:
        r["minutes"] = int(r["minutes"] or 0)
        r["genre"] = r.get("genre") or lookup.get(r["name"], "")
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


def scatter_chart(pts, y_max):
    """Recency scatter: [(date, hours, name)]. One series, hover per point."""
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

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" style="width:100%;height:auto">']
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
    for d, h, name in pts:
        if h > y_max:
            clipped.append((h, name))
        out.append(
            f'<circle cx="{X(d):.1f}" cy="{Y(h):.1f}" r="4.5" fill="var(--s1)" '
            f'fill-opacity="0.55" stroke="var(--surface)" stroke-width="1" class="mark" '
            f'data-tip="{esc(name)} — {h:,.0f}h, last played {d}"/>')
    out.append(f'<line x1="{L}" y1="{T+ph}" x2="{W-R}" y2="{T+ph}" '
               f'stroke="var(--axis)" stroke-width="1"/>')
    out.append("</svg>")
    if clipped:
        names = ", ".join(f"{esc(n)} {h:,.0f}h" for h, n in sorted(clipped, reverse=True))
        out.append(f"<p class='desc' style='margin-top:8px'>Pinned at the top edge "
                   f"(beyond the {y_max:.0f}h axis): {names}.</p>")
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


def build(rows, out_path, src_name):
    played = [r for r in rows if r["minutes"] > 0]
    never = [r for r in rows if r["minutes"] == 0 and r["note"] != UNTRACKED]
    untracked = [r for r in rows if r["note"] == UNTRACKED]
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
                pts.append((d, r["minutes"] / 60, r["name"]))
            except ValueError:
                pass
    pts.sort()
    hours_sorted = sorted((h for _, h, _ in pts), reverse=True)
    y_max = (hours_sorted[3] * 1.1) if len(hours_sorted) > 8 else (hours_sorted[0] if hours_sorted else 1)
    y_max = max(round(y_max / 25) * 25, 25)
    recency = scatter_chart(pts, y_max)

    backlog = stacked_chart(sorted(
        ((g, sum(1 for r in rs if r["minutes"] > 0),
          sum(1 for r in rs if r["minutes"] == 0 and r["note"] != UNTRACKED))
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
        tile(f"{len(rows):,}", "titles owned"),
        tile(f"{total_h:,.0f}", "hours logged"),
        tile(f"{len(played):,}", "ever launched"),
        tile(f"{len(never):,}", "never launched", "excludes pre-2009 titles"),
        tile(f"{len(untracked):,}", "untracked (pre-2009)", "0h is a data artifact"),
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
.legend span::before {{ content: ""; display: inline-block; width: 10px; height: 10px;
  border-radius: 2px; margin-right: 6px }}
.legend .l1::before {{ background: var(--s1) }} .legend .l2::before {{ background: var(--s2) }}
#tip {{ position: fixed; pointer-events: none; background: var(--ink); color: var(--page);
  padding: 6px 10px; border-radius: 6px; font-size: 12.5px; max-width: 320px;
  opacity: 0; transition: opacity .08s; z-index: 9 }}
details {{ margin-top: 6px }} summary {{ cursor: pointer; color: var(--ink2); font-size: 13.5px }}
table {{ border-collapse: collapse; width: 100%; font-size: 12.5px; margin-top: 10px }}
th, td {{ text-align: left; padding: 4px 10px 4px 0; border-bottom: 1px solid var(--grid) }}
th {{ color: var(--ink2); font-weight: 600 }}
td.num {{ font-variant-numeric: tabular-nums }}
.tablewrap {{ overflow-x: auto; max-height: 480px; overflow-y: auto }}
</style></head><body><main>
<h1>Game Library Report</h1>
<p class="sub">{esc(', '.join(platforms))} · {len(rows):,} titles · generated {today}
 from {esc(src_name)} · analysis conventions: hours are the ground truth</p>

<div class="tiles">{tiles}</div>

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

<section><h2>Backlog by genre</h2>
<p class="desc">Played vs never-launched, tagged genres only. Never-launched
titles in a high hours-per-game genre are the best recommendations available —
already owned, evidence overwhelming. Pre-2009 untracked titles excluded.</p>
<div class="legend"><span class="l1">Played</span><span class="l2">Never launched</span></div>
{backlog}</section>

<section><h2>Full library</h2>
<details><summary>Show table ({len(rows):,} rows)</summary>
<div class="tablewrap"><table>
<tr><th>Game</th><th>Platform</th><th>Hours</th><th>Last played</th><th>Genre</th><th>Note</th></tr>
{table_rows}</table></div></details></section>

<div id="tip" role="status"></div>
<script>
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
    a = p.parse_args()
    rows = load(a.csv_path, a.genres)
    build(rows, a.out, os.path.basename(a.csv_path))
    print(f"{len(rows)} titles -> {a.out}")


if __name__ == "__main__":
    main()
