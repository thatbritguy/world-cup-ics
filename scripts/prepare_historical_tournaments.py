#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
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
FIFA_URL_OVERRIDES = {
    identity("1954-06-23", "Switzerland", "Italy"): "https://www.fifa.com/en/match-centre/match/17/9/211/1301",
    identity("1954-06-26", "Austria", "Switzerland"): "https://www.fifa.com/en/match-centre/match/17/9/212/1237",
    identity("2014-06-15", "Argentina", "Bosnia-Herzegovina"): "https://www.fifa.com/en/match-centre/match/17/251164/255931/300186477",
    identity("2014-06-21", "Nigeria", "Bosnia-Herzegovina"): "https://www.fifa.com/en/match-centre/match/17/251164/255931/300186464",
    identity("2014-06-25", "Bosnia-Herzegovina", "Iran"): "https://www.fifa.com/en/match-centre/match/17/251164/255931/300186511",
    identity("2018-07-15", "France", "Croatia"): "https://www.fifa.com/en/match-centre/match/17/254645/275101/300331552",
    identity("2022-11-23", "Spain", "Costa Rica"): "https://www.fifa.com/en/match-centre/match/17/255711/285063/400235472",
    identity("2022-11-27", "Spain", "Germany"): "https://www.fifa.com/en/match-centre/match/17/255711/285063/400235474",
    identity("2022-12-01", "Japan", "Spain"): "https://www.fifa.com/en/match-centre/match/17/255711/285063/400235475",
    identity("2022-12-09", "Netherlands", "Argentina"): "https://www.fifa.com/en/match-centre/match/17/255711/285074/400128139",
    identity("2022-12-18", "Argentina", "France"): "https://www.fifa.com/en/match-centre/match/17/255711/285077/400128145",
}


def fifa_records(year: int) -> dict[tuple[str, frozenset[str]], dict[str, object]]:
    path = ROOT / "data" / "historical-sources" / str(year) / "fifa-match-centre.html"
    return parse_fifa_records(path.read_text(encoding="utf-8"), fifa_team_codes()) if path.exists() else {}


def wikipedia_fifa_records(year: int) -> dict[tuple[str, frozenset[str]], dict[str, object]]:
    path = ROOT / "data" / "historical-sources" / str(year) / "wikipedia-matches.txt"
    if not path.exists():
        return {}
    codes = fifa_team_codes()
    records: dict[tuple[str, frozenset[str]], dict[str, object]] = {}
    current: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        date = re.match(r"\|date=\{\{Start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})", line)
        team1 = re.match(r"\|team1=(?:\{\{fb(?:-rt)?\|([A-Z]{3})|.*\|([A-Z]{3})\}\})", line)
        team2 = re.match(r"\|team2=(?:\{\{fb(?:-rt)?\|([A-Z]{3})|.*\|([A-Z]{3})\}\})", line)
        url = re.search(r"https://www\.fifa\.com/en/match-centre/match/([0-9/]+)", line)
        if date:
            current = {"date": f"{int(date.group(1)):04d}-{int(date.group(2)):02d}-{int(date.group(3)):02d}"}
        elif team1:
            current["team1"] = team1.group(1) or team1.group(2)
        elif team2:
            current["team2"] = team2.group(1) or team2.group(2)
        elif url and all(field in current for field in ("date", "team1", "team2")):
            parts = url.group(1).split("/")
            if current["team1"] in codes and current["team2"] in codes and len(parts) == 4:
                records[identity(current["date"], codes[current["team1"]], codes[current["team2"]])] = {
                    "competition_id": parts[0], "season_id": parts[1], "stage_id": parts[2],
                    "match_id": parts[3], "match_number": None,
                }
            current = {}
    return records


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
    for key, value in wikipedia_fifa_records(year).items():
        fifa.setdefault(key, value)
    enriched: list[dict[str, object]] = []
    provisional: list[tuple[str, dict[str, object], str]] = []
    for item in report["matches"]:
        key = identity(item["date"], item["team1"], item["team2"])
        fifa_item = fifa.get(key)
        utc = kickoff_utc(year, item, fifa_item)
        provisional.append(
            (utc, item, str(fifa_item["match_number"]) if fifa_item and fifa_item.get("match_number") else "")
        )
    used_numbers = {int(number) for _, _, number in provisional if number}
    available_numbers = iter(
        number for number in range(1, len(provisional) + 1) if number not in used_numbers
    )
    fallback_numbers = {
        identity(item["date"], item["team1"], item["team2"]): next(available_numbers)
        for _, item, number in sorted(provisional, key=lambda row: (row[0], row[1]["team1"]))
        if not number
    }
    for utc, item, fifa_number in provisional:
        key = identity(item["date"], item["team1"], item["team2"])
        fifa_item = fifa.get(key)
        number = int(fifa_number) if fifa_number else fallback_numbers[key]
        match_id = fifa_item.get("match_id") if fifa_item else item.get("fifa_match_id")
        if fifa_item and all(fifa_item.get(field) for field in ("competition_id", "season_id", "stage_id")):
            fifa_url = (
                "https://www.fifa.com/en/match-centre/match/"
                f"{fifa_item['competition_id']}/{fifa_item['season_id']}/"
                f"{fifa_item['stage_id']}/{match_id}"
            )
        else:
            fifa_url = f"https://en.wikipedia.org/wiki/{year}_FIFA_World_Cup"
        fifa_url = FIFA_URL_OVERRIDES.get(key, fifa_url)
        if fifa_url.startswith("https://www.fifa.com/"):
            match_id = fifa_url.rsplit("/", 1)[-1]
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
                "fifa_url": fifa_url,
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
                else "FIFA official match numbers with deterministic fallback numbers where archive records are unavailable"
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
