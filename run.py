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


def merge(csvs, out):
    rows = []
    for path in csvs:
        with open(path, encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    rows.sort(key=lambda r: -int(r["minutes"] or 0))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["platform", "id", "name", "minutes", "last_played", "genre", "note"]
        )
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

    if not a.no_fetch and not a.report_only:
        pulls = []
        if cfg.get("STEAM_API_KEY") and (cfg.get("STEAM_VANITY") or cfg.get("STEAM_ID")):
            dest = os.path.join(out_dir, "steam.csv")
            args = ["--out", dest]
            if cfg.get("STEAM_ID"):
                args += ["--steamid", cfg["STEAM_ID"]]
            else:
                args += ["--vanity", cfg["STEAM_VANITY"]]
            run("fetch_steam.py", args, {"STEAM_API_KEY": cfg["STEAM_API_KEY"]})
            pulls.append(dest)
        if cfg.get("OPENXBL_API_KEY"):
            dest = os.path.join(out_dir, "xbox.csv")
            run("fetch_xbox.py", ["--out", dest], {"OPENXBL_API_KEY": cfg["OPENXBL_API_KEY"]})
            pulls.append(dest)
        if cfg.get("PSN_NPSSO"):
            dest = os.path.join(out_dir, "psn.csv")
            run("fetch_psn.py", ["--out", dest], {"PSN_NPSSO": cfg["PSN_NPSSO"]})
            pulls.append(dest)
        # Manual entries cover platforms with no API at all - Battle.net,
        # Epic, GOG, EA App, hours read off a console screen. Same CSV
        # schema; see manual.example.csv.
        manual = os.path.join(out_dir, "manual.csv")
        if os.path.exists(manual):
            pulls.append(manual)
            print(f"including manual entries from {manual}")
        if not pulls:
            sys.exit(
                "No platform credentials found in config.env.\n"
                "Copy config.example.env to config.env and fill in at least "
                "STEAM_API_KEY + STEAM_VANITY, or run with --no-fetch to use "
                "the existing data/library.csv."
            )
        n = merge(pulls, merged)
        print(f"merged {len(pulls)} platform pull(s) -> {merged} ({n} titles)")

    if not os.path.exists(merged):
        sys.exit(f"{merged} does not exist - run without --no-fetch first.")

    if not a.report_only:
        run("build_workbook.py", [merged, "--out", workbook])
    run("build_report.py", [merged, "--out", report])
    print("\nDone.")
    print(f"  workbook: {os.path.relpath(workbook, ROOT)}")
    print(f"  report:   {os.path.relpath(report, ROOT)}")


if __name__ == "__main__":
    main()
