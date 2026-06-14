#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import ROOT, load_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("years", nargs="+", type=int)
    args = parser.parse_args()
    approved = 0
    for year in args.years:
        path = ROOT / "data" / str(year) / "worldcup.stadiums.json"
        payload = load_json(path)
        for venue in payload["venues"]:
            if venue.get("coordinate_status") != "candidate":
                continue
            venue["coordinate_status"] = "verified"
            venue["coordinate_review"] = "Manual source-title and location review"
            approved += 1
        write_json(path, payload)
    report_path = ROOT / "reports" / "historical" / "venue-resolution.json"
    if report_path.exists():
        report = load_json(report_path)
        selected = set(args.years)
        for item in report["coverage"]:
            if item["year"] in selected:
                venues = load_json(
                    ROOT / "data" / str(item["year"]) / "worldcup.stadiums.json"
                )["venues"]
                item["candidate_venues"] = sum(
                    venue.get("coordinate_status") == "candidate" for venue in venues
                )
        write_json(report_path, report)
    print(f"Approved {approved} reviewed venue coordinates")


if __name__ == "__main__":
    main()
