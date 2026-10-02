#!/usr/bin/env python3
"""Entry point for a cloned checkout: `python run.py` from the repository root.

The pipeline itself lives with the skill, in
skills/game-library-analysis/scripts/run.py, so that installing the plugin
ships it. config.env and data/ are read from and written to the directory you
run this from.
"""
import os
import runpy
import sys

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "skills", "game-library-analysis", "scripts", "run.py")

if __name__ == "__main__":
    sys.argv[0] = TARGET
    runpy.run_path(TARGET, run_name="__main__")
