#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unicodedata
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from common import ROOT, normalize_name, write_json


WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
FIFA_CODES_PAGE = "List of FIFA country codes"
CONFEDERATIONS_PAGE = "List of men's national association football teams"
FLAGS_URL = (
    "https://gist.githubusercontent.com/filipemeneses/"
    "5a7d04a8198bfb1a756060c08d081805/raw"
)
CONFEDERATION_CONTINENTS = {
    "AFC": "Asia",
    "CAF": "Africa",
    "CONCACAF": "North America",
    "CONMEBOL": "South America",
    "OFC": "Oceania",
    "UEFA": "Europe",
}

# FIFA team names do not always match ISO's English short names.
ISO_OVERRIDES = {
    "British Virgin Islands": "VG",
    "Brunei": "BN",
    "Chinese Taipei": "TW",
    "DR Congo": "CD",
    "Eswatini": "SZ",
    "Ivory Coast": "CI",
    "Laos": "LA",
    "Macau": "MO",
    "North Macedonia": "MK",
    "Northern Ireland": "GB-NIR",
    "Palestine": "PS",
    "Republic of Ireland": "IE",
    "Syria": "SY",
    "Tahiti": "PF",
    "U.S. Virgin Islands": "VI",
}

# These preserve established calendar display names while indexing official and
# commonly encountered variants as aliases.
DISPLAY_OVERRIDES: dict[str, dict[str, Any]] = {
    "BIH": {
        "name": "Bosnia & Herzegovina",
        "aliases": ["Bosnia and Herzegovina", "Bosnia-Herzegovina"],
    },
    "CPV": {"name": "Cape Verde", "aliases": ["Cabo Verde"]},
    "CIV": {
        "name": "Ivory Coast",
        "aliases": ["Côte d'Ivoire", "Cote d'Ivoire"],
    },
    "COD": {
        "name": "DR Congo",
        "aliases": ["Congo DR", "Democratic Republic of the Congo"],
    },
    "CZE": {
        "name": "Czech Republic",
        "aliases": ["Czechia"],
    },
    "CUW": {"aliases": ["Curacao"]},
    "HKG": {"aliases": ["Hong Kong, China"]},
    "IRN": {
        "aliases": ["IR Iran", "Islamic Republic of Iran"],
    },
    "IRL": {"aliases": ["Ireland"]},
    "KOR": {
        "name": "South Korea",
        "aliases": ["Korea Republic", "Republic of Korea"],
    },
    "PRK": {
        "name": "North Korea",
        "aliases": ["Korea DPR", "DPR Korea", "Democratic People's Republic of Korea"],
    },
    "TUR": {
        "name": "Turkey",
        "aliases": ["Türkiye", "Turkiye"],
    },
    "USA": {
        "name": "USA",
        "aliases": ["United States", "United States of America"],
    },
}

HISTORICAL_WORLD_CUP_TEAMS = [
    {
        "name": "Czechoslovakia",
        "fifa_code": "TCH",
        "confed": "UEFA",
        "flag_iso": "CZ",
        "aliases": [],
    },
    {
        "name": "Dutch East Indies",
        "fifa_code": "INH",
        "confed": "AFC",
        "flag_iso": "NL",
        "aliases": ["Netherlands East Indies"],
    },
    {
        "name": "East Germany",
        "fifa_code": "GDR",
        "confed": "UEFA",
        "aliases": ["German Democratic Republic", "Germany DR"],
    },
    {
        "name": "Serbia and Montenegro",
        "fifa_code": "SCG",
        "confed": "UEFA",
        "aliases": [],
    },
    {
        "name": "Soviet Union",
        "fifa_code": "URS",
        "confed": "UEFA",
        "aliases": ["USSR"],
    },
    {
        "name": "West Germany",
        "fifa_code": "FRG",
        "confed": "UEFA",
        "flag_iso": "DE",
        "aliases": ["Federal Republic of Germany", "Germany FR"],
    },
    {
        "name": "Yugoslavia",
        "fifa_code": "YUG",
        "confed": "UEFA",
        "aliases": ["Kingdom of Yugoslavia"],
    },
    {
        "name": "Zaire",
        "fifa_code": "ZAI",
        "confed": "CAF",
        "aliases": [],
    },
]


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_cell = False
        self.cell: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.row = []
        elif tag == "td":
            self.in_cell = True
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            self.in_cell = False
            self.row.append(" ".join("".join(self.cell).split()))
        elif tag == "tr" and self.row:
            self.rows.append(self.row)


def fetch_json(url: str) -> Any:
    request = Request(
        url,
        headers={"User-Agent": "world-cup-ics/1.0 (country metadata builder)"},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def wikipedia_parse(page: str, prop: str) -> str:
    query = urlencode(
        {
            "action": "parse",
            "format": "json",
            "page": page,
            "prop": prop,
            "formatversion": 2,
        }
    )
    return fetch_json(f"{WIKIPEDIA_API}?{query}")["parse"][prop]


def fifa_members() -> list[tuple[str, str]]:
    parser = TableParser()
    parser.feed(wikipedia_parse(FIFA_CODES_PAGE, "text"))
    rows = [
        (row[1], row[0])
        for row in parser.rows
        if len(row) >= 2 and re.fullmatch(r"[A-Z]{3}", row[1])
    ]
    members = rows[:211]
    if len(members) != 211 or len({code for code, _ in members}) != 211:
        raise ValueError("Wikipedia FIFA member table did not contain 211 unique codes")
    return members


def confederation_index() -> dict[str, str]:
    wikitext = wikipedia_parse(CONFEDERATIONS_PAGE, "wikitext")
    index: dict[str, str] = {}
    for section in re.finditer(
        r"^=== (AFC|CAF|CONCACAF|CONMEBOL|OFC|UEFA).*?$(.*?)(?=^===|\Z)",
        wikitext,
        re.MULTILINE | re.DOTALL,
    ):
        confed = section.group(1)
        for team in re.finditer(
            r"\{\{fb\|([^|}]+)(?:\|name=\s*([^}]+))?\}\}", section.group(2)
        ):
            index[normalize_name(team.group(1))] = confed
            if team.group(2):
                index[normalize_name(team.group(2))] = confed
    index[normalize_name("Hong Kong")] = "AFC"
    index[normalize_name("Turkey")] = "UEFA"
    return index


def flag_index() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    flags = fetch_json(FLAGS_URL)
    by_name = {normalize_name(item["name"]): item for item in flags}
    by_iso = {item["iso"]: item for item in flags}
    return by_name, by_iso


def unicode_format(value: str) -> str:
    return "".join(f"\\u{{{part.removeprefix('U+')}}}" for part in value.split())


def current_country(
    code: str,
    source_name: str,
    confederations: dict[str, str],
    flags_by_name: dict[str, dict[str, str]],
    flags_by_iso: dict[str, dict[str, str]],
) -> dict[str, Any]:
    confed = confederations.get(normalize_name(source_name))
    if not confed:
        raise ValueError(f"No confederation for {code} {source_name}")

    iso = ISO_OVERRIDES.get(source_name)
    flag = flags_by_iso.get(iso) if iso else flags_by_name.get(normalize_name(source_name))
    if flag:
        iso = iso or flag["iso"]
    elif source_name != "Northern Ireland":
        raise ValueError(f"No ISO/flag mapping for {code} {source_name}")

    override = DISPLAY_OVERRIDES.get(code, {})
    name = override.get("name", source_name)
    aliases = list(override.get("aliases", []))
    if source_name != name and source_name not in aliases:
        aliases.append(source_name)
    country: dict[str, Any] = {
        "name": name,
        "continent": CONFEDERATION_CONTINENTS[confed],
        "flag_icon": flag["flag"] if flag else "",
        "flag_unicode": unicode_format(flag["unicode"]) if flag else "",
        "fifa_code": code,
        "confed": confed,
        "iso": iso,
        "status": "current",
        "aliases": aliases,
    }
    return country


def historical_country(
    value: dict[str, Any], flags_by_iso: dict[str, dict[str, str]]
) -> dict[str, Any]:
    flag = flags_by_iso.get(value.get("flag_iso", ""))
    country = {
        "name": value["name"],
        "continent": CONFEDERATION_CONTINENTS[value["confed"]],
        "flag_icon": flag["flag"] if flag else "",
        "flag_unicode": unicode_format(flag["unicode"]) if flag else "",
        "fifa_code": value["fifa_code"],
        "confed": value["confed"],
        "iso": None,
        "status": "historical",
        "aliases": value["aliases"],
    }
    if flag:
        country["flag_representation"] = "historical-design-match"
    return country


def validate(countries: list[dict[str, Any]]) -> None:
    current = [item for item in countries if item["status"] == "current"]
    historical = [item for item in countries if item["status"] == "historical"]
    if len(current) != 211 or len(historical) != len(HISTORICAL_WORLD_CUP_TEAMS):
        raise ValueError("Country dataset has an unexpected current/historical count")
    codes = [item["fifa_code"] for item in countries]
    if len(codes) != len(set(codes)):
        raise ValueError("Country dataset contains duplicate FIFA codes")

    names: dict[str, str] = {}
    for country in countries:
        for name in [
            country["name"],
            *country["aliases"],
        ]:
            if not name:
                continue
            normalized = normalize_name(name)
            prior = names.get(normalized)
            if prior and prior != country["fifa_code"]:
                raise ValueError(
                    f"Country alias {name!r} maps to both {prior} and {country['fifa_code']}"
                )
            names[normalized] = country["fifa_code"]


def main() -> None:
    members = fifa_members()
    confederations = confederation_index()
    flags_by_name, flags_by_iso = flag_index()
    countries = [
        current_country(code, name, confederations, flags_by_name, flags_by_iso)
        for code, name in members
    ]
    countries.extend(
        historical_country(item, flags_by_iso) for item in HISTORICAL_WORLD_CUP_TEAMS
    )
    countries.sort(key=lambda item: item["fifa_code"])
    validate(countries)
    write_json(ROOT / "data" / "countries.json", countries)
    print(
        f"Wrote data/countries.json with {len(members)} current FIFA members and "
        f"{len(HISTORICAL_WORLD_CUP_TEAMS)} historical World Cup teams"
    )


if __name__ == "__main__":
    main()
