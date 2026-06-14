#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys

from common import ROOT, load_json, write_json


ACCEPTED_TIME_STATUSES = {"corroborated", "resolved", "accepted-modern-source"}


def promote(year: int) -> None:
    data_dir = ROOT / "data" / str(year)
    manifest_path = data_dir / "worldcup.manifest.json"
    stadium_path = data_dir / "worldcup.stadiums.json"
    report_path = ROOT / "reports" / "historical" / f"{year}.json"
    calendar_path = ROOT / "ics" / f"world-cup-{year}.ics"
    for path in (manifest_path, stadium_path, report_path, calendar_path):
        if not path.exists():
            raise ValueError(f"Missing promotion input: {path.relative_to(ROOT)}")

    report = load_json(report_path)
    rejected = [
        match for match in report["matches"]
        if match.get("status") not in ACCEPTED_TIME_STATUSES
    ]
    if rejected:
        raise ValueError(f"{year} has {len(rejected)} unresolved kickoff records")

    venues = load_json(stadium_path)["venues"]
    aliases = {alias for venue in venues for alias in venue.get("ground_aliases", [])}
    missing = sorted({match["ground"] for match in report["matches"]} - aliases)
    if missing:
        raise ValueError(f"{year} has unresolved venues: {', '.join(missing)}")
    candidates = [
        venue for venue in venues if venue.get("coordinate_status") == "candidate"
    ]
    if candidates:
        raise ValueError(f"{year} has {len(candidates)} unapproved coordinates")

    manifest = load_json(manifest_path)
    numbers = [match["official_match_number"] for match in manifest["matches"]]
    if len(numbers) != len(set(numbers)):
        raise ValueError(f"{year} has duplicate visible match numbers")
    manifest["status"] = "validated"
    write_json(manifest_path, manifest)
    subprocess.run(
        [sys.executable, "scripts/validate_historical_calendar.py", str(year)],
        cwd=ROOT,
        check=True,
    )
    print(f"Promoted {year}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("years", nargs="+", type=int)
    args = parser.parse_args()
    for year in args.years:
        promote(year)


if __name__ == "__main__":
    main()
