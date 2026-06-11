#!/usr/bin/env python3
from __future__ import annotations

from common import DATA_DIR, load_json, match_key, stage_category, validate_worldcup, write_json


def main() -> None:
    source = load_json(DATA_DIR / "worldcup.json")
    validate_worldcup(source)
    target = DATA_DIR / "worldcup.uidmap.json"
    existing = load_json(target) if target.exists() else {}
    uidmap = {}
    for sequence, match in enumerate(source["matches"], start=1):
        key = match_key(sequence)
        uidmap[key] = {
            "sequence": sequence,
            "source_index": sequence - 1,
            "stage_category": stage_category(match),
            "initial_date": match["date"],
            "initial_time": match["time"],
            "initial_team1": match["team1"],
            "initial_team2": match["team2"],
            "initial_ground": match["ground"],
        }
        if existing.get(key, {}).get("official_match_number") is not None:
            uidmap[key]["official_match_number"] = existing[key][
                "official_match_number"
            ]
    write_json(target, uidmap)
    print(f"Wrote {len(uidmap)} stable match identifiers")


if __name__ == "__main__":
    main()
