#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATE_END_DATE = date(2026, 7, 31)


def run(*arguments: str) -> None:
    subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Ignore update cutoffs")
    args = parser.parse_args()

    if not args.force and date.today() > UPDATE_END_DATE:
        print("World Cup 2026 automatic update window has ended")
        run("scripts/validate_calendar.py")
        return

    force = ("--force",) if args.force else ()
    run("scripts/fetch_worldcup.py", *force)
    run("scripts/scrape_broadcasters.py", *force)
    run("scripts/generate_calendar.py")
    run("scripts/validate_calendar.py")


if __name__ == "__main__":
    main()

