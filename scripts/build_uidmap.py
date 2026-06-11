#!/usr/bin/env python3
from __future__ import annotations

from common import DATA_DIR, load_json, match_key, stage_category, validate_worldcup, write_json


def main() -> None:
    source = load_json(DATA_DIR / "worldcup.json")
    validate_worldcup(source)
    uidmap = {}
    for sequence, match in enumerate(source["matches"], start=1):
        uidmap[match_key(sequence)] = {
            "sequence": sequence,
            "source_index": sequence - 1,
            "stage_category": stage_category(match),
            "initial_date": match["date"],
            "initial_time": match["time"],
            "initial_team1": match["team1"],
            "initial_team2": match["team2"],
            "initial_ground": match["ground"],
        }
    write_json(DATA_DIR / "worldcup.uidmap.json", uidmap)
    print(f"Wrote {len(uidmap)} stable match identifiers")


if __name__ == "__main__":
    main()

