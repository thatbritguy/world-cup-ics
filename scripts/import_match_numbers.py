#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import (
    DATA_DIR,
    display_city,
    load_json,
    match_key,
    normalize_name,
    parse_kickoff,
    utc_stamp,
    validate_worldcup,
    write_json,
)


def reference_events(path: Path) -> list[tuple[int, str, str]]:
    events = []
    for block in path.read_text(encoding="utf-8").split("BEGIN:VEVENT")[1:]:
        kickoff = re.search(r"^DTSTART:(.*)$", block, re.MULTILINE)
        location = re.search(r"^LOCATION:(.*)$", block, re.MULTILINE)
        description = re.search(r"^DESCRIPTION:(.*)$", block, re.MULTILINE)
        match_number = (
            re.search(r"Match (\d+)", description.group(1)) if description else None
        )
        if not kickoff or not location or not match_number:
            raise ValueError("Reference calendar event is missing match metadata")
        events.append(
            (
                int(match_number.group(1)),
                kickoff.group(1).strip(),
                normalize_name(location.group(1).strip()),
            )
        )
    return events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_ics", type=Path)
    args = parser.parse_args()

    source = load_json(DATA_DIR / "worldcup.json")
    uidmap = load_json(DATA_DIR / "worldcup.uidmap.json")
    stadium_data = load_json(DATA_DIR / "worldcup.stadiums.json")
    stadiums = {item["city"]: item for item in stadium_data["stadiums"]}
    validate_worldcup(source, uidmap)

    fixture_lookup: dict[tuple[str, str], list[int]] = {}
    for source_index, match in enumerate(source["matches"]):
        stadium = stadiums[match["ground"]]
        location = f"{stadium['name']}, {display_city(stadium['city'])}"
        key = (utc_stamp(parse_kickoff(match)), normalize_name(location))
        fixture_lookup.setdefault(key, []).append(source_index)

    assigned: set[int] = set()
    for official_number, kickoff, location in reference_events(args.reference_ics):
        candidates = fixture_lookup.get((kickoff, location), [])
        if len(candidates) != 1:
            raise ValueError(
                f"Match {official_number} did not resolve uniquely: {candidates}"
            )
        source_index = candidates[0]
        key = match_key(source_index + 1)
        uidmap[key]["official_match_number"] = official_number
        assigned.add(official_number)

    if assigned != set(range(1, 105)):
        raise ValueError("Official match numbering is incomplete")
    write_json(DATA_DIR / "worldcup.uidmap.json", uidmap)
    print("Imported official match numbers 1-104 without changing event UIDs")


if __name__ == "__main__":
    main()
