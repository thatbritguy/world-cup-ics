#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from common import ROOT, normalize_name, write_json


WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
PAGES = {
    1930: [
        "1930 FIFA World Cup Group 1",
        "1930 FIFA World Cup Group 2",
        "1930 FIFA World Cup Group 3",
        "1930 FIFA World Cup Group 4",
        "1930 FIFA World Cup knockout stage",
        "1930 FIFA World Cup final",
    ]
}
NAME_ALIASES = {
    normalize_name("United States"): "United States",
    normalize_name("USA"): "United States",
    normalize_name("Kingdom of Yugoslavia"): "Yugoslavia",
    normalize_name("Yugoslavia"): "Yugoslavia",
}
FIFA_KICKOFF_OVERRIDES = {
    (1930, "Uruguay", "Yugoslavia"): "1930-07-27T18:45:00Z",
}


def fetch_wikitext(title: str) -> str:
    query = urlencode(
        {
            "action": "parse",
            "format": "json",
            "page": title,
            "prop": "wikitext",
            "formatversion": 2,
        }
    )
    request = Request(
        f"{WIKIPEDIA_API}?{query}",
        headers={"User-Agent": "world-cup-ics/1.0 (historical calendar builder)"},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)["parse"]["wikitext"]


def canonical_team(value: str) -> str:
    return NAME_ALIASES.get(normalize_name(value), value)


def clean_wikilinks(value: str) -> str:
    value = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", value)
    return re.sub(r"\[\[([^\]]+)\]\]", r"\1", value).strip()


def parse_page(title: str, wikitext: str, starting_order: int) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    current: dict[str, str] | None = None
    for line in wikitext.splitlines():
        if line.startswith("|date="):
            current = {"date": line.removeprefix("|date=")}
        elif current is not None and line.startswith("|time="):
            current["time"] = line.removeprefix("|time=")
        elif current is not None and line.startswith("|stadium="):
            current["stadium"] = line.removeprefix("|stadium=")
        elif current is not None and line.startswith("|report="):
            current["report"] = line.removeprefix("|report=")
            records.append(parse_match(title, current, starting_order + len(records)))
            current = None
    return records


def parse_match(title: str, fields: dict[str, str], source_order: int) -> dict[str, object]:
    date_match = re.search(
        r"\{\{Start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})", fields["date"]
    )
    time_match = re.search(r"(\d{1,2}):(\d{2})\s+UYT", fields["time"])
    report_title = re.search(r"\|title=([^|]+?)\s*\{\{!\}\}", fields["report"])
    fifa_url = re.search(
        r"https://www\.fifa\.com/en/match-centre/match/[^\s|}]+", fields["report"]
    )
    if not all((date_match, time_match, report_title, fifa_url)):
        raise ValueError(f"Could not parse match data on {title}: {fields}")

    teams = re.split(r"\s+vs\s+", report_title.group(1).strip(), maxsplit=1)
    if len(teams) != 2:
        raise ValueError(f"Could not parse teams from report title: {report_title.group(1)}")

    year, month, day = map(int, date_match.groups())
    hour, minute = map(int, time_match.groups())
    offset = timezone(-timedelta(hours=3, minutes=30))
    local = datetime(year, month, day, hour, minute, tzinfo=offset)
    page_url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
    kickoff_utc = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    override = FIFA_KICKOFF_OVERRIDES.get((year, canonical_team(teams[0]), canonical_team(teams[1])))
    if override:
        kickoff_utc = override
        local = datetime.strptime(override, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        ).astimezone(offset)
    return {
        "date": local.date().isoformat(),
        "team1": canonical_team(teams[0]),
        "team2": canonical_team(teams[1]),
        "local_time": local.strftime("%H:%M"),
        "utc_offset": "-03:30",
        "kickoff_utc": kickoff_utc,
        "kickoff_source": "FIFA" if override else "Wikipedia",
        "stadium": clean_wikilinks(fields.get("stadium", "")),
        "fifa_url": fifa_url.group(0),
        "wikipedia_url": page_url,
        "source_order": source_order,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("year", type=int)
    args = parser.parse_args()
    if args.year not in PAGES:
        raise ValueError(f"No Wikipedia page map configured for {args.year}")

    records: list[dict[str, object]] = []
    for title in PAGES[args.year]:
        records.extend(parse_page(title, fetch_wikitext(title), len(records)))
    records.sort(key=lambda item: (item["kickoff_utc"], item["source_order"]))
    if len(records) != 18:
        raise ValueError(f"Expected 18 matches for 1930, found {len(records)}")

    destination = ROOT / "data" / str(args.year) / "worldcup.enrichment.json"
    write_json(
        destination,
        {
            "year": args.year,
            "source": "English Wikipedia match boxes, with linked FIFA reports",
            "matches": records,
        },
    )
    print(f"Wrote {destination.relative_to(ROOT)} with {len(records)} kickoff times")


if __name__ == "__main__":
    main()
