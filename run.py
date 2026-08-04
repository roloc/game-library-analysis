#!/usr/bin/env python3
"""One-command pipeline: fetch every platform with credentials in config.env,
merge into one normalized CSV, build the Excel workbook and the HTML report.

    python run.py                 # fetch + merge + workbook + report
    python run.py --no-fetch      # rebuild outputs from the existing data/library.csv
    python run.py --report-only   # just regenerate the HTML report

Credentials live in config.env (copy config.example.env), which is gitignored.
This script passes them to the fetchers through the environment and never
prints them.
"""
import argparse
import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(ROOT, "scripts")


def load_config(path):
    cfg = {}
    if not os.path.exists(path):
        return cfg
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def run(script, args, extra_env=None):
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script), *args], env=env, cwd=ROOT
    )
    if r.returncode != 0:
        sys.exit(f"{script} failed (exit {r.returncode})")


FIELDS = ["platform", "id", "name", "minutes", "last_played", "genre", "note",
          "ach_earned", "ach_total", "ach_pct", "platinum"]


def _norm(name):
    return "".join(c for c in name.lower() if c.isalnum())


def enrich(rows, out_dir):
    """Join the completion caches onto merged rows: Steam achievements by
    appid, PSN trophies by normalized name. Xbox columns arrive pre-filled
    from fetch_xbox.py."""
    import json
    steam_path = os.path.join(out_dir, "achievements_steam.json")
    if os.path.exists(steam_path):
        with open(steam_path) as f:
            cache = json.load(f)
        hit = 0
        for r in rows:
            v = cache.get(str(r.get("id", "")))
            if r["platform"] == "Steam" and v and v.get("total"):
                r["ach_earned"] = v["earned"]
                r["ach_total"] = v["total"]
                r["ach_pct"] = round(100 * v["earned"] / v["total"], 1)
                hit += 1
        print(f"steam achievements: {hit} rows enriched")

    psn_path = os.path.join(out_dir, "psn_trophies.json")
    if os.path.exists(psn_path):
        with open(psn_path) as f:
            trophies = {_norm(t["name"]): t for t in json.load(f)["titles"] if t["name"]}
        hit = 0
        for r in rows:
            t = trophies.get(_norm(r["name"])) if r["platform"] == "PlayStation" else None
            if not t:
                continue
            e, d = t.get("earned", {}), t.get("defined", {})
            if sum(d.values()):
                r["ach_earned"] = sum(e.values())
                r["ach_total"] = sum(d.values())
                r["ach_pct"] = t.get("progress",
                                     round(100 * sum(e.values()) / sum(d.values()), 1))
                r["platinum"] = "yes" if e.get("platinum") else ""
                hit += 1
        print(f"psn trophies: {hit} rows enriched")


def merge(csvs, out, out_dir):
    rows = []
    for path in csvs:
        with open(path, encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    for r in rows:
        for k in FIELDS:
            r.setdefault(k, "")
    enrich(rows, out_dir)
    rows.sort(key=lambda r: -int(r["minutes"] or 0))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=os.path.join(ROOT, "config.env"))
    p.add_argument("--no-fetch", action="store_true",
                   help="skip the network; rebuild from the existing merged CSV")
    p.add_argument("--report-only", action="store_true",
                   help="only regenerate the HTML report")
    a = p.parse_args()

    cfg = load_config(a.config)
    out_dir = os.path.join(ROOT, cfg.get("OUT_DIR", "data"))
    os.makedirs(out_dir, exist_ok=True)
    merged = os.path.join(out_dir, "library.csv")
    workbook = os.path.join(ROOT, cfg.get("WORKBOOK", "data/library.xlsx"))
    report = os.path.join(ROOT, cfg.get("REPORT", "data/report.html"))

    if not a.report_only:
        pulls = []
        if not a.no_fetch:
            steam_key = cfg.get("STEAM_API_KEY")
            if steam_key and (cfg.get("STEAM_VANITY") or cfg.get("STEAM_ID")):
                dest = os.path.join(out_dir, "steam.csv")
                ident = (["--steamid", cfg["STEAM_ID"]] if cfg.get("STEAM_ID")
                         else ["--vanity", cfg["STEAM_VANITY"]])
                run("fetch_steam.py", ["--out", dest, *ident],
                    {"STEAM_API_KEY": steam_key})
                run("fetch_achievements_steam.py",
                    ["--library", dest, *ident,
                     "--out", os.path.join(out_dir, "achievements_steam.json")],
                    {"STEAM_API_KEY": steam_key})
                pulls.append(dest)
            if cfg.get("OPENXBL_API_KEY"):
                dest = os.path.join(out_dir, "xbox.csv")
                run("fetch_xbox.py", ["--out", dest],
                    {"OPENXBL_API_KEY": cfg["OPENXBL_API_KEY"]})
                pulls.append(dest)
            # PSN is CACHE-FIRST by request: one pull, then the local files
            # are the source of truth. Delete them (or run fetch_psn.py by
            # hand) to force a refresh - run.py never re-hits Sony on its own.
            psn_csv = os.path.join(out_dir, "psn.csv")
            psn_trophies = os.path.join(out_dir, "psn_trophies.json")
            if cfg.get("PSN_NPSSO"):
                if not os.path.exists(psn_csv):
                    run("fetch_psn.py", ["--out", psn_csv],
                        {"PSN_NPSSO": cfg["PSN_NPSSO"]})
                else:
                    print(f"PSN library: using cached {psn_csv} (delete to re-pull)")
                if not os.path.exists(psn_trophies):
                    run("fetch_psn.py", ["--trophies", psn_trophies],
                        {"PSN_NPSSO": cfg["PSN_NPSSO"]})
                else:
                    print(f"PSN trophies: using cached {psn_trophies} (delete to re-pull)")
        # with --no-fetch, re-merge from whatever per-platform pulls exist
        for name in ("steam.csv", "xbox.csv", "psn.csv", "manual.csv"):
            path = os.path.join(out_dir, name)
            if path not in pulls and os.path.exists(path):
                pulls.append(path)
        if not pulls:
            sys.exit(
                "No platform credentials found in config.env and no cached "
                "pulls in data/.\nCopy config.example.env to config.env and "
                "fill in at least STEAM_API_KEY + STEAM_VANITY."
            )
        n = merge(pulls, merged, out_dir)
        print(f"merged {len(pulls)} source(s) -> {merged} ({n} titles)")

    if not os.path.exists(merged):
        sys.exit(f"{merged} does not exist - nothing to build from.")

    recs = os.path.join(out_dir, "recommendations.json")
    recs_args = ["--recs", recs] if os.path.exists(recs) else []
    if not a.report_only:
        run("build_workbook.py", [merged, "--out", workbook, *recs_args])
    run("build_report.py", [merged, "--out", report, *recs_args])
    print("\nDone.")
    print(f"  workbook: {os.path.relpath(workbook, ROOT)}")
    print(f"  report:   {os.path.relpath(report, ROOT)}")


if __name__ == "__main__":
    main()
