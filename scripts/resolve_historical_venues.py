#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlencode

from audit_historical_tournaments import fetch_text
from common import ROOT, load_json, normalize_name, parse_geo, write_json
from historical_config import historical_years


WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
PHOTON_API = "https://photon.komoot.io/api/"
STADIUM_SOURCE_YEARS = (2014, 2018, 2022)
SEARCH_OVERRIDES = {
    "Volksparkstadion, Hamburg": "Volksparkstadion Hamburg stadium",
}
VENUE_OVERRIDES = {
    "Estadio Luis Casanova, Valencia": {
        "name": "Estadio Luis Casanova",
        "city": "Valencia",
        "ground_aliases": ["Estadio Luis Casanova, Valencia"],
        "latitude": 39.474656,
        "longitude": -0.358361,
        "coordinate_source": "https://fr.wikipedia.org/wiki/Stade_de_Mestalla",
        "coordinate_source_title": "Stade de Mestalla",
        "coordinate_status": "verified",
    },
    "Estadio Sarriá, Barcelona": {
        "name": "Estadio Sarriá",
        "city": "Barcelona",
        "ground_aliases": ["Estadio Sarriá, Barcelona"],
        "latitude": 41.393111,
        "longitude": 2.133169,
        "coordinate_source": "https://fr.wikipedia.org/wiki/Stade_de_Sarri%C3%A0",
        "coordinate_source_title": "Stade de Sarrià",
        "coordinate_status": "verified",
    },
}


def seed_venues() -> dict[str, dict[str, object]]:
    seeds: dict[str, dict[str, object]] = {}
    for year in (1930, 1934, 1938, 1950):
        path = ROOT / "data" / str(year) / "worldcup.stadiums.json"
        for venue in load_json(path)["venues"]:
            for alias in venue["ground_aliases"]:
                seeds[normalize_name(alias)] = {**venue, "coordinate_status": "verified"}
            seeds[normalize_name(venue["name"])] = {**venue, "coordinate_status": "verified"}
    for year in STADIUM_SOURCE_YEARS:
        path = ROOT / "data" / "historical-sources" / str(year) / "openfootball-stadiums.json"
        if not path.exists():
            continue
        for stadium in load_json(path)["stadiums"]:
            if not stadium.get("coords"):
                continue
            latitude, longitude = parse_geo(stadium["coords"])
            alias = f"{stadium['name']}, {stadium['city']}"
            seeds[normalize_name(alias)] = {
                "name": stadium["name"],
                "city": stadium["city"],
                "ground_aliases": [alias],
                "latitude": latitude,
                "longitude": longitude,
                "coordinate_source": (
                    "https://github.com/openfootball/worldcup.json/"
                    f"blob/master/{year}/worldcup.stadiums.json"
                ),
                "coordinate_status": "source",
            }
            seeds[normalize_name(stadium["name"])] = seeds[normalize_name(alias)]
    return seeds


def title_score(ground: str, title: str) -> int:
    ignored = {"stadium", "stade", "stadio", "estadio", "estadium", "the", "de", "do", "da"}
    tokens = {normalize_name(token) for token in re.findall(r"[^\W_]+", ground)} - ignored
    title_tokens = {normalize_name(token) for token in re.findall(r"[^\W_]+", title)} - ignored
    score = len(tokens & title_tokens) * 10
    if normalize_name(title) in normalize_name(ground):
        score += 5
    if "station" in title.casefold() or title.startswith(("FC ", "TSV ")):
        score -= 20
    return score


def lookup(ground: str, cache: Path) -> dict[str, object]:
    key = normalize_name(ground)
    path = cache / f"{key}.json"
    if path.exists() and load_json(path):
        candidates = load_json(path)
    else:
        candidates = []
        try:
            query = urlencode(
                {
                    "action": "query",
                    "format": "json",
                    "generator": "search",
                    "gsrsearch": SEARCH_OVERRIDES.get(ground, ground),
                    "gsrlimit": 8,
                    "prop": "coordinates|info",
                    "inprop": "url",
                }
            )
            response = json.loads(fetch_text(f"{WIKIPEDIA_API}?{query}"))
            candidates = [
                {
                    "title": page["title"],
                    "url": page.get("fullurl"),
                    "latitude": page.get("coordinates", [{}])[0].get("lat"),
                    "longitude": page.get("coordinates", [{}])[0].get("lon"),
                }
                for page in response.get("query", {}).get("pages", {}).values()
                if page.get("coordinates")
            ]
        except Exception:
            pass
        if not candidates:
            query = urlencode({"q": ground, "limit": 5})
            response = json.loads(fetch_text(f"{PHOTON_API}?{query}"))
            candidates = []
            for feature in response.get("features", []):
                properties = feature.get("properties", {})
                longitude, latitude = feature["geometry"]["coordinates"]
                osm_type = str(properties.get("osm_type", "")).lower()
                osm_id = properties.get("osm_id")
                candidates.append(
                    {
                        "title": properties.get("name") or properties.get("city") or ground,
                        "url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
                        "latitude": latitude,
                        "longitude": longitude,
                    }
                )
        write_json(path, candidates)
        time.sleep(0.05)
    ranked = sorted(candidates, key=lambda item: title_score(ground, item["title"]), reverse=True)
    if not ranked:
        raise ValueError(f"No reliable coordinate result for {ground}")
    selected = ranked[0]
    return {
        "name": ground.split(",")[0],
        "city": ground.split(",", 1)[1].strip() if "," in ground else "",
        "ground_aliases": [ground],
        "latitude": selected["latitude"],
        "longitude": selected["longitude"],
        "coordinate_source": selected["url"],
        "coordinate_source_title": selected["title"],
        "match_score": title_score(ground, selected["title"]),
        "coordinate_status": "candidate",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("years", nargs="*", type=int)
    args = parser.parse_args()
    years = args.years or [year for year in historical_years() if year >= 1954]
    cache = ROOT / "data" / "historical-sources" / "venue-search"
    cache.mkdir(parents=True, exist_ok=True)
    seeds = seed_venues()
    failures: list[dict[str, object]] = []
    for year in years:
        report = load_json(ROOT / "reports" / "historical" / f"{year}.json")
        venues: list[dict[str, object]] = []
        year_failures: list[dict[str, object]] = []
        unresolved: list[str] = []
        for ground in sorted({match["ground"] for match in report["matches"]}):
            venue = VENUE_OVERRIDES.get(ground) or seeds.get(normalize_name(ground)) or seeds.get(
                normalize_name(ground.split(",")[0])
            )
            if venue:
                copied = dict(venue)
                copied["ground_aliases"] = sorted(
                    set([*venue["ground_aliases"], ground])
                )
                venues.append(copied)
            else:
                unresolved.append(ground)
        with ThreadPoolExecutor(max_workers=8) as executor:
            pending = {executor.submit(lookup, ground, cache): ground for ground in unresolved}
            for future in as_completed(pending):
                ground = pending[future]
                try:
                    venues.append(future.result())
                except Exception as error:
                    year_failures.append(
                        {"year": year, "ground": ground, "error": str(error)}
                    )
        venues.sort(key=lambda venue: str(venue["ground_aliases"][0]))
        failures.extend(year_failures)
        if not year_failures:
            write_json(
                ROOT / "data" / str(year) / "worldcup.stadiums.json",
                {"venues": venues},
            )
            print(f"Resolved {year}: {len(venues)} venues")
        else:
            print(f"Incomplete {year}: {len(year_failures)} unresolved venues")
    coverage: list[dict[str, object]] = []
    for year in (year for year in historical_years() if year >= 1954):
        report_path = ROOT / "reports" / "historical" / f"{year}.json"
        stadium_path = ROOT / "data" / str(year) / "worldcup.stadiums.json"
        expected = {
            match["ground"] for match in load_json(report_path)["matches"]
        }
        venues = load_json(stadium_path)["venues"] if stadium_path.exists() else []
        aliases = {
            alias for venue in venues for alias in venue.get("ground_aliases", [])
        }
        coverage.append(
            {
                "year": year,
                "expected_venues": len(expected),
                "resolved_venues": len(expected & aliases),
                "candidate_venues": sum(
                    venue.get("coordinate_status") == "candidate" for venue in venues
                ),
                "unresolved_grounds": sorted(expected - aliases),
            }
        )
    write_json(
        ROOT / "reports" / "historical" / "venue-resolution.json",
        {"coverage": coverage, "latest_run_failures": failures},
    )
    if failures:
        raise ValueError(f"Venue resolution has {len(failures)} unresolved grounds")


if __name__ == "__main__":
    main()
