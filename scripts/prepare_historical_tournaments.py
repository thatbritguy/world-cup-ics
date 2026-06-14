#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from audit_historical_tournaments import fifa_team_codes, identity, parse_fifa_records
from common import ROOT, write_json
from historical_config import TOURNAMENTS, historical_years


SKIP_VALIDATED = {1930, 1934, 1938, 1950}
FIXED_OFFSETS = {
    2002: 9,
    2022: 3,
}


def fifa_records(year: int) -> dict[tuple[str, frozenset[str]], dict[str, object]]:
    path = ROOT / "data" / "historical-sources" / str(year) / "fifa-match-centre.html"
    return parse_fifa_records(path.read_text(encoding="utf-8"), fifa_team_codes()) if path.exists() else {}


def kickoff_utc(year: int, match: dict[str, object], fifa: dict[str, object] | None) -> str:
    if year == 1994 and fifa:
        return str(fifa["utc"])
    hour, minute = map(int, str(match["selected_local_time"]).split(":"))
    local = datetime.strptime(str(match["date"]), "%Y-%m-%d").replace(
        hour=hour, minute=minute
    )
    offset = match["sources"].get("openfootball_utc_offset")
    if offset:
        aware = local.replace(tzinfo=timezone(timedelta(hours=int(str(offset)))))
    elif year in FIXED_OFFSETS:
        aware = local.replace(tzinfo=timezone(timedelta(hours=FIXED_OFFSETS[year])))
    else:
        zone = str(TOURNAMENTS[year]["timezone"])
        if zone == "multi-zone":
            raise ValueError(f"No timezone offset for {year} {match['ground']}")
        aware = local.replace(tzinfo=ZoneInfo(zone))
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prepare(year: int) -> None:
    source_dir = ROOT / "data" / "historical-sources" / str(year)
    data_dir = ROOT / "data" / str(year)
    worldcup = json.loads((source_dir / "openfootball.json").read_text(encoding="utf-8"))
    report = json.loads((ROOT / "reports" / "historical" / f"{year}.json").read_text(encoding="utf-8"))
    fifa = fifa_records(year)
    enriched: list[dict[str, object]] = []
    provisional: list[tuple[str, dict[str, object], str]] = []
    for item in report["matches"]:
        key = identity(item["date"], item["team1"], item["team2"])
        fifa_item = fifa.get(key)
        utc = kickoff_utc(year, item, fifa_item)
        provisional.append((utc, item, str(fifa_item["match_number"]) if fifa_item else ""))
    chronology = {
        identity(item["date"], item["team1"], item["team2"]): index
        for index, (_, item, _) in enumerate(sorted(provisional, key=lambda row: (row[0], row[1]["team1"])), start=1)
    }
    for utc, item, fifa_number in provisional:
        key = identity(item["date"], item["team1"], item["team2"])
        number = int(fifa_number) if fifa_number else chronology[key]
        match_id = item.get("fifa_match_id")
        enriched.append(
            {
                "date": item["date"],
                "team1": item["team1"],
                "team2": item["team2"],
                "local_time": item["selected_local_time"],
                "local_time_sources": {
                    "selected": item.get("resolution", {}).get("selected_source", item["status"]),
                    "confidence": "resolved" if item["status"] == "resolved" else item["status"],
                    **item["sources"],
                    **(
                        {"resolution_note": item["resolution"]["evidence"]}
                        if item.get("resolution")
                        else {}
                    ),
                },
                "kickoff_utc": utc,
                "official_match_number": number,
                "fifa_match_id": match_id,
                "fifa_url": f"https://en.wikipedia.org/wiki/{year}_FIFA_World_Cup",
                "ground": item["ground"],
            }
        )
    enriched.sort(key=lambda item: int(item["official_match_number"]))
    data_dir.mkdir(parents=True, exist_ok=True)
    write_json(data_dir / "worldcup.json", worldcup)
    write_json(
        data_dir / "worldcup.enrichment.json",
        {
            "year": year,
            "numbering": (
                "FIFA official match numbers"
                if all(item.get("fifa_match_number") for item in report["matches"])
                else "Chronological match numbers where FIFA archive numbering is unavailable"
            ),
            "matches": enriched,
        },
    )
    print(f"Prepared data/{year} with {len(enriched)} matches")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("years", nargs="*", type=int)
    args = parser.parse_args()
    years = args.years or [year for year in historical_years() if year not in SKIP_VALIDATED]
    for year in years:
        prepare(year)


if __name__ == "__main__":
    main()
