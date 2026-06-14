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
    "AOL Arena, Hamburg": {
        "name": "AOL Arena", "city": "Hamburg", "ground_aliases": ["AOL Arena, Hamburg"],
        "latitude": 53.587222, "longitude": 9.898611,
        "coordinate_source": "https://en.wikipedia.org/wiki/Volksparkstadion", "coordinate_source_title": "Volksparkstadion",
        "coordinate_status": "verified",
    },
    "AWD-Arena, Hannover": {
        "name": "AWD-Arena", "city": "Hannover", "ground_aliases": ["AWD-Arena, Hannover"],
        "latitude": 52.36, "longitude": 9.731111,
        "coordinate_source": "https://en.wikipedia.org/wiki/Heinz_von_Heiden_Arena", "coordinate_source_title": "Heinz von Heiden Arena",
        "coordinate_status": "verified",
    },
    "Fritz-Walter-Stadion, Kaiserslautern": {
        "name": "Fritz-Walter-Stadion", "city": "Kaiserslautern", "ground_aliases": ["Fritz-Walter-Stadion, Kaiserslautern"],
        "latitude": 49.434722, "longitude": 7.776667,
        "coordinate_source": "https://en.wikipedia.org/wiki/Fritz-Walter-Stadion", "coordinate_source_title": "Fritz-Walter-Stadion",
        "coordinate_status": "verified",
    },
    "Signal Iduna Park, Dortmund": {
        "name": "Signal Iduna Park", "city": "Dortmund", "ground_aliases": ["Signal Iduna Park, Dortmund"],
        "latitude": 51.4925, "longitude": 7.451667,
        "coordinate_source": "https://en.wikipedia.org/wiki/Westfalenstadion", "coordinate_source_title": "Westfalenstadion",
        "coordinate_status": "verified",
    },
    "Cape Town Stadium, Cape Town": {
        "name": "Cape Town Stadium", "city": "Cape Town", "ground_aliases": ["Cape Town Stadium, Cape Town"],
        "latitude": -33.903611, "longitude": 18.411111,
        "coordinate_source": "https://en.wikipedia.org/wiki/Cape_Town_Stadium", "coordinate_source_title": "Cape Town Stadium",
        "coordinate_status": "verified",
    },
    "Mbombela Stadium, Nelspruit": {
        "name": "Mbombela Stadium", "city": "Nelspruit", "ground_aliases": ["Mbombela Stadium, Nelspruit"],
        "latitude": -25.461944, "longitude": 30.929722,
        "coordinate_source": "https://en.wikipedia.org/wiki/Mbombela_Stadium", "coordinate_source_title": "Mbombela Stadium",
        "coordinate_status": "verified",
    },
    "Soccer City, Johannesburg": {
        "name": "Soccer City", "city": "Johannesburg", "ground_aliases": ["Soccer City, Johannesburg"],
        "latitude": -26.234797, "longitude": 27.982667,
        "coordinate_source": "https://en.wikipedia.org/wiki/FNB_Stadium", "coordinate_source_title": "FNB Stadium",
        "coordinate_status": "verified",
    },
    "Arena Pantanal, Cuiabá": {
        "name": "Arena Pantanal", "city": "Cuiabá", "ground_aliases": ["Arena Pantanal, Cuiabá"],
        "latitude": -15.603056, "longitude": -56.120556,
        "coordinate_source": "https://en.wikipedia.org/wiki/Arena_Pantanal", "coordinate_source_title": "Arena Pantanal",
        "coordinate_status": "verified",
    },
    "Arena de São Paulo, São Paulo": {
        "name": "Arena de São Paulo", "city": "São Paulo", "ground_aliases": ["Arena de São Paulo, São Paulo"],
        "latitude": -23.54525, "longitude": -46.474278,
        "coordinate_source": "https://github.com/openfootball/worldcup.json/blob/master/2014/worldcup.stadiums.json", "coordinate_source_title": "Arena Corinthians",
        "coordinate_status": "source",
    },
    "Ryavallen, Borås": {
        "name": "Ryavallen", "city": "Borås", "ground_aliases": ["Ryavallen, Borås"],
        "latitude": 57.734167, "longitude": 12.934444,
        "coordinate_source": "https://en.wikipedia.org/wiki/Ryavallen", "coordinate_source_title": "Ryavallen",
        "coordinate_status": "verified",
    },
    "Tunavallen, Eskilstuna": {
        "name": "Tunavallen", "city": "Eskilstuna", "ground_aliases": ["Tunavallen, Eskilstuna"],
        "latitude": 59.366667, "longitude": 16.500556,
        "coordinate_source": "https://en.wikipedia.org/wiki/Tunavallen", "coordinate_source_title": "Tunavallen",
        "coordinate_status": "verified",
    },
    "Hillsborough Stadium, Sheffield": {
        "name": "Hillsborough Stadium", "city": "Sheffield", "ground_aliases": ["Hillsborough Stadium, Sheffield"],
        "latitude": 53.411389, "longitude": -1.500833,
        "coordinate_source": "https://en.wikipedia.org/wiki/Hillsborough_Stadium", "coordinate_source_title": "Hillsborough Stadium",
        "coordinate_status": "verified",
    },
    "Wembley Stadium, London": {
        "name": "Wembley Stadium", "city": "London", "ground_aliases": ["Wembley Stadium, London"],
        "latitude": 51.555556, "longitude": -0.279722,
        "coordinate_source": "https://en.wikipedia.org/wiki/Wembley_Stadium_(1923)", "coordinate_source_title": "Wembley Stadium (1923)",
        "coordinate_status": "verified",
    },
    "White City Stadium, London": {
        "name": "White City Stadium", "city": "London", "ground_aliases": ["White City Stadium, London"],
        "latitude": 51.513, "longitude": -0.227,
        "coordinate_source": "https://en.wikipedia.org/wiki/White_City_Stadium", "coordinate_source_title": "White City Stadium",
        "coordinate_status": "verified",
    },
    "Neckarstadion, Stuttgart": {
        "name": "Neckarstadion", "city": "Stuttgart", "ground_aliases": ["Neckarstadion, Stuttgart"],
        "latitude": 48.792222, "longitude": 9.232,
        "coordinate_source": "https://en.wikipedia.org/wiki/MHPArena", "coordinate_source_title": "MHPArena",
        "coordinate_status": "verified",
    },
    "Niedersachsenstadion, Hanover": {
        "name": "Niedersachsenstadion", "city": "Hanover", "ground_aliases": ["Niedersachsenstadion, Hanover"],
        "latitude": 52.36, "longitude": 9.731111,
        "coordinate_source": "https://en.wikipedia.org/wiki/Heinz_von_Heiden_Arena", "coordinate_source_title": "Heinz von Heiden Arena",
        "coordinate_status": "verified",
    },
    "Olympiastadion, München": {
        "name": "Olympiastadion", "city": "München", "ground_aliases": ["Olympiastadion, München"],
        "latitude": 48.173056, "longitude": 11.546667,
        "coordinate_source": "https://en.wikipedia.org/wiki/Olympiastadion_(Munich)", "coordinate_source_title": "Olympiastadion (Munich)",
        "coordinate_status": "verified",
    },
    "Parkstadion, Gelsenkirchen": {
        "name": "Parkstadion", "city": "Gelsenkirchen", "ground_aliases": ["Parkstadion, Gelsenkirchen"],
        "latitude": 51.559167, "longitude": 7.067778,
        "coordinate_source": "https://en.wikipedia.org/wiki/Parkstadion", "coordinate_source_title": "Parkstadion",
        "coordinate_status": "verified",
    },
    "Volksparkstadion, Hamburg": {
        "name": "Volksparkstadion", "city": "Hamburg", "ground_aliases": ["Volksparkstadion, Hamburg"],
        "latitude": 53.587222, "longitude": 9.898611,
        "coordinate_source": "https://en.wikipedia.org/wiki/Volksparkstadion", "coordinate_source_title": "Volksparkstadion",
        "coordinate_status": "verified",
    },
    "Estadio José Amalfitani, Buenos Aires": {
        "name": "Estadio José Amalfitani", "city": "Buenos Aires", "ground_aliases": ["Estadio José Amalfitani, Buenos Aires"],
        "latitude": -34.635278, "longitude": -58.520556,
        "coordinate_source": "https://en.wikipedia.org/wiki/Jos%C3%A9_Amalfitani_Stadium", "coordinate_source_title": "José Amalfitani Stadium",
        "coordinate_status": "verified",
    },
    "Estadio José Zorrilla, Valladolid": {
        "name": "Estadio José Zorrilla", "city": "Valladolid", "ground_aliases": ["Estadio José Zorrilla, Valladolid"],
        "latitude": 41.644444, "longitude": -4.761111,
        "coordinate_source": "https://en.wikipedia.org/wiki/Estadio_Jos%C3%A9_Zorrilla", "coordinate_source_title": "Estadio José Zorrilla",
        "coordinate_status": "verified",
    },
    "Estadio de Riazor, A Coruña": {
        "name": "Estadio de Riazor", "city": "A Coruña", "ground_aliases": ["Estadio de Riazor, A Coruña"],
        "latitude": 43.368611, "longitude": -8.4175,
        "coordinate_source": "https://en.wikipedia.org/wiki/Estadio_Riazor", "coordinate_source_title": "Estadio Riazor",
        "coordinate_status": "verified",
    },
    "San Siro, Milan": {
        "name": "San Siro", "city": "Milan", "ground_aliases": ["San Siro, Milan"],
        "latitude": 45.478056, "longitude": 9.124167,
        "coordinate_source": "https://en.wikipedia.org/wiki/San_Siro", "coordinate_source_title": "San Siro",
        "coordinate_status": "verified",
    },
    "Stadio La Favorita, Palermo": {
        "name": "Stadio La Favorita", "city": "Palermo", "ground_aliases": ["Stadio La Favorita, Palermo"],
        "latitude": 38.152778, "longitude": 13.342222,
        "coordinate_source": "https://en.wikipedia.org/wiki/Stadio_Renzo_Barbera", "coordinate_source_title": "Stadio Renzo Barbera",
        "coordinate_status": "verified",
    },
    "Giants Stadium, East Rutherford": {
        "name": "Giants Stadium", "city": "East Rutherford", "ground_aliases": ["Giants Stadium, East Rutherford"],
        "latitude": 40.812222, "longitude": -74.076944,
        "coordinate_source": "https://en.wikipedia.org/wiki/Giants_Stadium", "coordinate_source_title": "Giants Stadium",
        "coordinate_status": "verified",
    },
    "RFK Stadium, Washington": {
        "name": "RFK Stadium", "city": "Washington", "ground_aliases": ["RFK Stadium, Washington"],
        "latitude": 38.889722, "longitude": -76.971667,
        "coordinate_source": "https://en.wikipedia.org/wiki/Robert_F._Kennedy_Memorial_Stadium", "coordinate_source_title": "Robert F. Kennedy Memorial Stadium",
        "coordinate_status": "verified",
    },
    "Daegu World Cup Stadium, Daegu": {
        "name": "Daegu World Cup Stadium", "city": "Daegu", "ground_aliases": ["Daegu World Cup Stadium, Daegu"],
        "latitude": 35.829722, "longitude": 128.690278,
        "coordinate_source": "https://en.wikipedia.org/wiki/Daegu_Stadium", "coordinate_source_title": "Daegu Stadium",
        "coordinate_status": "verified",
    },
    "International Stadium Yokohama, Yokohama": {
        "name": "International Stadium Yokohama", "city": "Yokohama", "ground_aliases": ["International Stadium Yokohama, Yokohama"],
        "latitude": 35.51, "longitude": 139.606389,
        "coordinate_source": "https://en.wikipedia.org/wiki/International_Stadium_Yokohama", "coordinate_source_title": "International Stadium Yokohama",
        "coordinate_status": "verified",
    },
    "Kobe Wing Stadium, Kobe": {
        "name": "Kobe Wing Stadium", "city": "Kobe", "ground_aliases": ["Kobe Wing Stadium, Kobe"],
        "latitude": 34.656667, "longitude": 135.168889,
        "coordinate_source": "https://en.wikipedia.org/wiki/Noevir_Stadium_Kobe", "coordinate_source_title": "Noevir Stadium Kobe",
        "coordinate_status": "verified",
    },
    "Niigata Stadium, Niigata": {
        "name": "Niigata Stadium", "city": "Niigata", "ground_aliases": ["Niigata Stadium, Niigata"],
        "latitude": 37.8825, "longitude": 139.059167,
        "coordinate_source": "https://en.wikipedia.org/wiki/Denka_Big_Swan_Stadium", "coordinate_source_title": "Denka Big Swan Stadium",
        "coordinate_status": "verified",
    },
    "Saitama Stadium, Saitama": {
        "name": "Saitama Stadium", "city": "Saitama", "ground_aliases": ["Saitama Stadium, Saitama"],
        "latitude": 35.903056, "longitude": 139.717778,
        "coordinate_source": "https://en.wikipedia.org/wiki/Saitama_Stadium_2002", "coordinate_source_title": "Saitama Stadium 2002",
        "coordinate_status": "verified",
    },
    "Stade Félix Bollaert, Lens": {
        "name": "Stade Félix Bollaert", "city": "Lens", "ground_aliases": ["Stade Félix Bollaert, Lens"],
        "latitude": 50.432778, "longitude": 2.815,
        "coordinate_source": "https://en.wikipedia.org/wiki/Stade_Bollaert-Delelis", "coordinate_source_title": "Stade Bollaert-Delelis",
        "coordinate_status": "verified",
    },
    "Stade Gerland, Lyon": {
        "name": "Stade Gerland", "city": "Lyon", "ground_aliases": ["Stade Gerland, Lyon"],
        "latitude": 45.72375, "longitude": 4.8324,
        "coordinate_source": "https://en.wikipedia.org/wiki/Stade_de_Gerland", "coordinate_source_title": "Stade de Gerland",
        "coordinate_status": "verified",
    },
    "Stade de Toulouse, Toulouse": {
        "name": "Stade de Toulouse", "city": "Toulouse", "ground_aliases": ["Stade de Toulouse, Toulouse"],
        "latitude": 43.583333, "longitude": 1.434167,
        "coordinate_source": "https://en.wikipedia.org/wiki/Stadium_de_Toulouse", "coordinate_source_title": "Stadium de Toulouse",
        "coordinate_status": "verified",
    },
    "Stade de la Beaujoire, Nantes": {
        "name": "Stade de la Beaujoire", "city": "Nantes", "ground_aliases": ["Stade de la Beaujoire, Nantes"],
        "latitude": 47.255556, "longitude": -1.525278,
        "coordinate_source": "https://en.wikipedia.org/wiki/Stade_de_la_Beaujoire", "coordinate_source_title": "Stade de la Beaujoire",
        "coordinate_status": "verified",
    },
    "Ekaterinburg Arena, Ekaterinburg": {
        "name": "Ekaterinburg Arena", "city": "Ekaterinburg", "ground_aliases": ["Ekaterinburg Arena, Ekaterinburg"],
        "latitude": 56.8325, "longitude": 60.573611,
        "coordinate_source": "https://github.com/openfootball/worldcup.json/blob/master/2018/worldcup.stadiums.json", "coordinate_source_title": "Central Stadium (Ekaterinburg Arena)",
        "coordinate_status": "source",
    },
    "Fisht Stadium, Sochi": {
        "name": "Fisht Stadium", "city": "Sochi", "ground_aliases": ["Fisht Stadium, Sochi"],
        "latitude": 43.402222, "longitude": 39.956111,
        "coordinate_source": "https://github.com/openfootball/worldcup.json/blob/master/2018/worldcup.stadiums.json", "coordinate_source_title": "Fisht Olympic Stadium (Fisht Stadium)",
        "coordinate_status": "source",
    },
    "Saint Petersburg Stadium, Saint Petersburg": {
        "name": "Saint Petersburg Stadium", "city": "Saint Petersburg", "ground_aliases": ["Saint Petersburg Stadium, Saint Petersburg", "Saint Petersburg Stadium, St. Petersburg"],
        "latitude": 59.973056, "longitude": 30.220556,
        "coordinate_source": "https://github.com/openfootball/worldcup.json/blob/master/2018/worldcup.stadiums.json", "coordinate_source_title": "Krestovsky Stadium (Saint Petersburg Stadium)",
        "coordinate_status": "source",
    },
    "Saint Petersburg Stadium, St. Petersburg": {
        "name": "Saint Petersburg Stadium", "city": "Saint Petersburg", "ground_aliases": ["Saint Petersburg Stadium, Saint Petersburg", "Saint Petersburg Stadium, St. Petersburg"],
        "latitude": 59.973056, "longitude": 30.220556,
        "coordinate_source": "https://github.com/openfootball/worldcup.json/blob/master/2018/worldcup.stadiums.json", "coordinate_source_title": "Krestovsky Stadium (Saint Petersburg Stadium)",
        "coordinate_status": "source",
    },
    "Spartak Stadium, Moscow": {
        "name": "Spartak Stadium", "city": "Moscow", "ground_aliases": ["Spartak Stadium, Moscow"],
        "latitude": 55.817861, "longitude": 37.44025,
        "coordinate_source": "https://github.com/openfootball/worldcup.json/blob/master/2018/worldcup.stadiums.json", "coordinate_source_title": "Otkritie Arena (Spartak Stadium)",
        "coordinate_status": "source",
    },
    "Lusail Iconic Stadium, Lusail": {
        "name": "Lusail Iconic Stadium", "city": "Lusail", "ground_aliases": ["Lusail Iconic Stadium, Lusail"],
        "latitude": 25.420861, "longitude": 51.490389,
        "coordinate_source": "https://github.com/openfootball/worldcup.json/blob/master/2022/worldcup.stadiums.json", "coordinate_source_title": "Lusail Stadium",
        "coordinate_status": "source",
    },
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
