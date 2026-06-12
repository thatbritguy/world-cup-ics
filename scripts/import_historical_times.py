#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from common import ROOT, normalize_name, write_json


WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
TOURNAMENTS = {
    1930: {
        "pages": [
            "1930 FIFA World Cup Group 1",
            "1930 FIFA World Cup Group 2",
            "1930 FIFA World Cup Group 3",
            "1930 FIFA World Cup Group 4",
            "1930 FIFA World Cup knockout stage",
            "1930 FIFA World Cup final",
        ],
        "archive_url": (
            "https://web.archive.org/web/20220808074418id_/"
            "https://www.fifa.com/en/tournaments/mens/worldcup/"
            "1930uruguay/match-center"
        ),
        "timezone": "America/Montevideo",
        "expected_matches": 18,
        "conflict_notes": {
            "1087": (
                "Selected FIFA's archived 14:15 local time over Wikipedia's "
                "12:45 match-box value."
            )
        },
    },
    1934: {
        "pages": [
            "1934 FIFA World Cup final tournament",
            "1934 FIFA World Cup final",
        ],
        "archive_url": (
            "https://web.archive.org/web/20220819172410id_/"
            "https://www.fifa.com/en/tournaments/mens/worldcup/1934italy/match-center"
        ),
        "timezone": "Europe/Rome",
        "expected_matches": 17,
        "local_time_overrides": {
            "1134": {
                "time": "15:30",
                "selected_source": (
                    "English Wikipedia, corroborated by a contemporary "
                    "Radiocorriere account"
                ),
                "evidence_url": (
                    "https://www.worldradiohistory.com/INTERNATIONAL/"
                    "Radiocorriere/30s/1934/RC-1934-25.pdf"
                ),
                "reported_alternatives": {
                    "rsssf": "17:00",
                },
            }
        },
        "conflict_notes": {
            **{
                match_id: (
                    "Selected FIFA's archived 16:30 local time, corroborated "
                    "by RSSSF, over Wikipedia's 16:00 match-box value."
                )
                for match_id in (
                    "1102",
                    "1104",
                    "1108",
                    "1111",
                    "1119",
                    "1133",
                    "1135",
                    "1141",
                )
            },
            "1105": (
                "Selected FIFA and Wikipedia's 18:00 local time over RSSSF's 17:30."
            ),
            "1134": (
                "Selected Wikipedia's 15:30 CET value. A contemporary "
                "Radiocorriere account places one hour of regulation remaining "
                "at 16:00, the teams entering for the second half at 16:30, and "
                "play continuing at 17:03. This sequence supports a 15:30 kickoff "
                "and rejects FIFA's archived 17:30 value; RSSSF reports 17:00."
            ),
        },
    },
}
NAME_ALIASES = {
    normalize_name("USA"): "United States",
    normalize_name("United States"): "United States",
    normalize_name("Kingdom of Yugoslavia"): "Yugoslavia",
    normalize_name("Yugoslavia"): "Yugoslavia",
    normalize_name("Czech Republic"): "Czechoslovakia",
    normalize_name("Czechoslovakia"): "Czechoslovakia",
}


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={"User-Agent": "world-cup-ics/1.0 (historical calendar builder)"},
    )
    with urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8")


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
    return json.loads(fetch_text(f"{WIKIPEDIA_API}?{query}"))["parse"]["wikitext"]


def canonical_team(value: str) -> str:
    return NAME_ALIASES.get(normalize_name(value), value)


def clean_wikilinks(value: str) -> str:
    value = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", value)
    return re.sub(r"\[\[([^\]]+)\]\]", r"\1", value).strip()


def parse_wikipedia_page(title: str, starting_order: int) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    current: dict[str, str] | None = None
    for line in fetch_wikitext(title).splitlines():
        if line.startswith("|date="):
            current = {"date": line.removeprefix("|date=")}
        elif current is not None and line.startswith("|time="):
            current["time"] = line.removeprefix("|time=")
        elif current is not None and line.startswith("|stadium="):
            current["stadium"] = line.removeprefix("|stadium=")
        elif current is not None and line.startswith("|report="):
            current["report"] = line.removeprefix("|report=")
            records.append(
                parse_wikipedia_match(title, current, starting_order + len(records))
            )
            current = None
    return records


def parse_wikipedia_match(
    title: str, fields: dict[str, str], source_order: int
) -> dict[str, object]:
    date_match = re.search(
        r"\{\{Start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})", fields["date"]
    )
    time_match = re.search(r"(\d{1,2}):(\d{2})", fields["time"])
    report_title = re.search(r"\|title=([^|]+?)\s*\{\{!\}\}", fields["report"])
    fifa_url = re.search(
        r"https://www\.fifa\.com/en/match-centre/match/[^\s|}]+", fields["report"]
    )
    if not all((date_match, time_match, report_title, fifa_url)):
        raise ValueError(f"Could not parse match data on {title}: {fields}")
    teams = re.split(r"\s+vs\s+", report_title.group(1).strip(), maxsplit=1)
    if len(teams) != 2:
        raise ValueError(f"Could not parse teams from {report_title.group(1)}")
    fifa_match_id = fifa_url.group(0).rstrip("/").split("/")[-1]
    year, month, day = map(int, date_match.groups())
    return {
        "date": f"{year:04d}-{month:02d}-{day:02d}",
        "team1": canonical_team(teams[0]),
        "team2": canonical_team(teams[1]),
        "wikipedia_local_time": f"{int(time_match.group(1)):02d}:{time_match.group(2)}",
        "stadium": clean_wikilinks(fields.get("stadium", "")),
        "fifa_url": fifa_url.group(0),
        "fifa_match_id": fifa_match_id,
        "wikipedia_url": (
            f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
        ),
        "source_order": source_order,
    }


def parse_fifa_archive(html: str) -> dict[str, dict[str, object]]:
    pattern = re.compile(
        r'"idMatch":"(?P<id>\d+)".*?'
        r'"date":"(?P<date>[^"]+)".*?'
        r'"localDate":"(?P<local>[^"]+)".*?'
        r'"awayTeam":\{"abbreviation":"(?P<away>[^"]+)".*?'
        r'"homeTeam":\{"abbreviation":"(?P<home>[^"]+)".*?'
        r'"matchNumber":(?P<number>\d+)',
        re.DOTALL,
    )
    matches: dict[str, dict[str, object]] = {}
    for match in pattern.finditer(html):
        matches.setdefault(
            match.group("id"),
            {
                "fifa_local_time": match.group("local")[11:16],
                "fifa_derived_utc": match.group("date"),
                "official_match_number": int(match.group("number")),
            },
        )
    return matches


def reconcile(year: int) -> dict[str, object]:
    config = TOURNAMENTS[year]
    wikipedia: list[dict[str, object]] = []
    for title in config["pages"]:
        wikipedia.extend(parse_wikipedia_page(title, len(wikipedia)))
    fifa = parse_fifa_archive(fetch_text(config["archive_url"]))
    expected = config["expected_matches"]
    if len(wikipedia) != expected or len(fifa) != expected:
        raise ValueError(
            f"Expected {expected} matches for {year}; found "
            f"Wikipedia={len(wikipedia)}, FIFA={len(fifa)}"
        )

    timezone_name = config["timezone"]
    timezone_info = ZoneInfo(timezone_name)
    records: list[dict[str, object]] = []
    for item in wikipedia:
        fifa_item = fifa.get(str(item["fifa_match_id"]))
        if not fifa_item:
            raise ValueError(f"No archived FIFA match for {item['fifa_match_id']}")
        match_id = str(item["fifa_match_id"])
        override = config.get("local_time_overrides", {}).get(match_id)
        local_time = str(
            override["time"] if override else fifa_item["fifa_local_time"]
        )
        hour, minute = map(int, local_time.split(":"))
        date = datetime.strptime(str(item["date"]), "%Y-%m-%d")
        local = date.replace(hour=hour, minute=minute, tzinfo=timezone_info)
        wikipedia_time = str(item["wikipedia_local_time"])
        conflict = wikipedia_time != local_time
        note = config["conflict_notes"].get(match_id)
        if conflict and not note:
            raise ValueError(
                f"Unresolved local-time conflict for {item['fifa_match_id']}: "
                f"Wikipedia={wikipedia_time}, FIFA={local_time}"
            )
        records.append(
            {
                **item,
                "local_time": local_time,
                "local_time_sources": {
                    "selected": (
                        override["selected_source"]
                        if override
                        else "Archived FIFA tournament match centre"
                    ),
                    "wikipedia": wikipedia_time,
                    "fifa_archive": str(fifa_item["fifa_local_time"]),
                    **(
                        {
                            "evidence_url": override["evidence_url"],
                            **override["reported_alternatives"],
                        }
                        if override
                        else {}
                    ),
                    "resolution_note": note,
                },
                "timezone": timezone_name,
                "utc_offset": local.strftime("%z")[:3] + ":" + local.strftime("%z")[3:],
                "timezone_source": "IANA Time Zone Database",
                "kickoff_utc": local.astimezone(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "fifa_derived_utc": fifa_item["fifa_derived_utc"],
                "official_match_number": fifa_item["official_match_number"],
                "fifa_archive_url": str(config["archive_url"]).replace("id_/", ""),
            }
        )
    records.sort(key=lambda item: int(item["official_match_number"]))
    return {
        "year": year,
        "source": (
            "Local clock times from FIFA's archived tournament match centre or "
            "documented match-specific overrides, reconciled against English "
            "Wikipedia match boxes; official match numbers come from FIFA and "
            "UTC conversion uses historical IANA timezone rules"
        ),
        "timezone_note": (
            "FIFA's derived UTC fields are retained for audit but are not used. "
            "Historical local clock time is converted with the IANA host timezone."
        ),
        "matches": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("year", type=int)
    args = parser.parse_args()
    if args.year not in TOURNAMENTS:
        raise ValueError(f"No historical source configuration for {args.year}")
    destination = ROOT / "data" / str(args.year) / "worldcup.enrichment.json"
    value = reconcile(args.year)
    write_json(destination, value)
    print(
        f"Wrote {destination.relative_to(ROOT)} with {len(value['matches'])} reconciled matches"
    )


if __name__ == "__main__":
    main()
