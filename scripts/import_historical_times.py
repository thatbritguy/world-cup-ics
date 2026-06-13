#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
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
        "rsssf_url": (
            "https://raw.githubusercontent.com/rsssf/worldcup/"
            "master/pages/30full.txt"
        ),
        "timezone": "America/Montevideo",
        "expected_matches": 18,
        "local_time_overrides": {
            "1087": {
                "time": "15:30",
                "selected_source": (
                    "Uruguayan Football Association match archive, "
                    "corroborated by RSSSF"
                ),
                "evidence_url": (
                    "https://www.auf.org.uy/copa-mundial-uruguay-1930"
                    "uruguay-vs-argentina1930-07-30/"
                ),
                "reported_alternatives": {
                    "rsssf": "15:30",
                },
            }
        },
        "conflict_notes": {
            "1087": (
                "Selected the Uruguayan Football Association's 15:30 local "
                "time, independently matched by RSSSF. FIFA's archive reports "
                "14:15 and Wikipedia reports 12:45; neither conflicting value "
                "has equivalent corroboration."
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
        "rsssf_url": (
            "https://raw.githubusercontent.com/rsssf/worldcup/"
            "master/pages/34full.txt"
        ),
        "timezone": "Europe/Rome",
        "expected_matches": 17,
        "local_time_overrides": {
            "1134": {
                "time": "17:00",
                "selected_source": (
                    "Contemporary Radiocorriere EIAR broadcast schedule, "
                    "corroborated by RSSSF"
                ),
                "evidence_url": (
                    "https://www.worldradiohistory.com/INTERNATIONAL/"
                    "Radiocorriere/30s/1934/RC-1934-24.pdf"
                ),
                "reported_alternatives": {
                    "wikipedia": "15:30",
                    "rsssf": "17:00",
                },
            }
        },
        "conflict_notes": {
            "1134": (
                "Selected 17:00 CET from the contemporary Radiocorriere EIAR "
                "schedule for 10 June 1934, which lists the live final broadcast "
                "from Stadio del Littorio at 17:00; RSSSF independently reports "
                "17:00. The following week's Radiocorriere poem places the teams' "
                "entrance at 16:30 and listeners absorbed in the commentary at "
                "17:03. Wikipedia reports 15:30 and FIFA's archive reports 17:30."
            ),
        },
    },
    1938: {
        "pages": [
            "1938 FIFA World Cup final tournament",
            "Brazil v Poland (1938 FIFA World Cup)",
            "Battle of Bordeaux (1938 FIFA World Cup)",
            "1938 FIFA World Cup final",
        ],
        "archive_url": (
            "https://web.archive.org/web/20221003182345id_/"
            "https://www.fifa.com/en/tournaments/mens/worldcup/"
            "1938france/match-center"
        ),
        "rsssf_url": (
            "https://raw.githubusercontent.com/rsssf/worldcup/"
            "master/pages/38full.txt"
        ),
        "timezone": "Europe/Paris",
        "expected_matches": 18,
        "local_time_overrides": {
            "1165": {
                "time": "17:00",
                "selected_source": (
                    "Contemporary Tribune de Lausanne match report, "
                    "corroborated by the German Football Association"
                ),
                "confidence": "confirmed",
                "evidence_url": (
                    "https://datencenter.dfb.de/datencenter/weltmeisterschaft/"
                    "1938-in-frankreich/achtelfinale/"
                    "schweiz-deutschland-136812"
                ),
                "evidence_reference": (
                    "Tribune de Lausanne, 5 June 1938: both teams entered "
                    "the pitch shortly before 17:00"
                ),
                "reported_alternatives": {},
            }
        },
        "conflict_notes": {
            "1165": (
                "Selected 17:00 WEST from the Tribune de Lausanne report of "
                "5 June 1938, which states that both teams entered the pitch "
                "shortly before 17:00. The German Football Association records "
                "17:00, agreeing with Wikipedia and FIFA; RSSSF reports 18:00."
            )
        },
    },
    1950: {
        "pages": [
            "1950 FIFA World Cup Group 1",
            "1950 FIFA World Cup Group 2",
            "United States v England (1950 FIFA World Cup)",
            "1950 FIFA World Cup Group 3",
            "1950 FIFA World Cup Group 4",
            "1950 FIFA World Cup final round",
            "Uruguay v Brazil (1950 FIFA World Cup)",
        ],
        "archive_url": (
            "https://web.archive.org/web/20221003182345id_/"
            "https://www.fifa.com/en/tournaments/mens/worldcup/"
            "1950brazil/match-center"
        ),
        "rsssf_url": (
            "https://raw.githubusercontent.com/rsssf/worldcup/"
            "master/pages/50full.txt"
        ),
        "rsssf_date_corrections": {
            ("1950-06-29", frozenset(("Yugoslavia", "Mexico"))): "1950-06-28",
            ("1950-07-03", frozenset(("Brazil", "Sweden"))): "1950-07-09",
        },
        "source_notes": [
            "RSSSF dates Yugoslavia-Mexico as 29 June; FIFA, Wikipedia and the "
            "openfootball result record place it on 28 June.",
            "RSSSF dates Brazil-Sweden as 3 July; FIFA, Wikipedia and the "
            "openfootball result record place it on 9 July.",
        ],
        "timezone": "America/Sao_Paulo",
        "expected_matches": 22,
        "local_time_overrides": {
            "1208": {
                "time": "15:00",
                "selected_source": (
                    "O Preço de uma Copa Curitiba venue history, corroborated "
                    "by FIFA and Wikipedia"
                ),
                "confidence": "corroborated",
                "evidence_url": "https://oprecodeumacopa.com/curitiba.html",
                "reported_alternatives": {},
            },
            "1230": {
                "time": "15:00",
                "selected_source": (
                    "O Preço de uma Copa Belo Horizonte venue history, "
                    "corroborated by FIFA and Wikipedia"
                ),
                "confidence": "corroborated",
                "evidence_url": "https://oprecodeumacopa.com/belohorizonte.html",
                "reported_alternatives": {},
            },
            "1202": {
                "time": "15:00",
                "selected_source": (
                    "O Preço de uma Copa Belo Horizonte venue history, "
                    "corroborated by FIFA and Wikipedia"
                ),
                "confidence": "corroborated",
                "evidence_url": "https://oprecodeumacopa.com/belohorizonte.html",
                "reported_alternatives": {},
            },
            "1194": {
                "time": "15:00",
                "selected_source": (
                    "O Preço de uma Copa Recife venue history, corroborated "
                    "by FIFA and Wikipedia"
                ),
                "confidence": "corroborated",
                "evidence_url": "https://oprecodeumacopa.com/recife.html",
                "reported_alternatives": {},
            },
        },
        "conflict_notes": {
            "1208": (
                "Selected 15:00 from the Curitiba venue history, which states "
                "that both local World Cup matches began at 15:00. FIFA and "
                "Wikipedia agree; RSSSF reports 15:30."
            ),
            "1230": (
                "Selected 15:00 from the Belo Horizonte venue history, which "
                "states that its World Cup matches began punctually at 15:00. "
                "FIFA and Wikipedia agree; RSSSF reports 18:00."
            ),
            "1202": (
                "Selected 15:00 from the Belo Horizonte venue history, which "
                "states that its World Cup matches began punctually at 15:00. "
                "FIFA and Wikipedia agree; RSSSF reports 18:00."
            ),
            "1194": (
                "Selected 15:00 from the Recife venue history, which explicitly "
                "states that Chile-United States began at 15:00. FIFA and "
                "Wikipedia agree; RSSSF reports 18:00."
            ),
        },
        "event_notes": {
            "1190": "Decisive match of the final group; Uruguay won the World Cup."
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
RSSSF_CODES = {
    "ARG": "Argentina",
    "AUT": "Austria",
    "BEL": "Belgium",
    "BOL": "Bolivia",
    "BRA": "Brazil",
    "CHI": "Chile",
    "CUB": "Cuba",
    "CZE": "Czechoslovakia",
    "EGY": "Egypt",
    "ENG": "England",
    "ESP": "Spain",
    "FRA": "France",
    "GER": "Germany",
    "HOL": "Netherlands",
    "HUN": "Hungary",
    "IHO": "Dutch East Indies",
    "ITA": "Italy",
    "JUG": "Yugoslavia",
    "MEX": "Mexico",
    "NOR": "Norway",
    "PAR": "Paraguay",
    "PER": "Peru",
    "POL": "Poland",
    "ROM": "Romania",
    "SUI": "Switzerland",
    "SWE": "Sweden",
    "URU": "Uruguay",
    "USA": "United States",
}


def fetch_text(url: str) -> str:
    for attempt in range(5):
        request = Request(
            url,
            headers={"User-Agent": "world-cup-ics/1.0 (historical calendar builder)"},
        )
        try:
            with urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8")
        except HTTPError as error:
            if error.code != 429 or attempt == 4:
                raise
            retry_after = error.headers.get("Retry-After")
            delay = (
                int(retry_after)
                if retry_after and retry_after.isdigit()
                else 2**attempt
            )
            time.sleep(delay)
    raise RuntimeError(f"Could not fetch {url}")


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
            if not current.get("time") or not current["report"]:
                current = None
                continue
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


def match_key(date: str, team1: str, team2: str) -> tuple[str, frozenset[str]]:
    return date, frozenset((canonical_team(team1), canonical_team(team2)))


def parse_rsssf(text: str, year: int) -> dict[tuple[str, frozenset[str]], str | None]:
    lines = text.splitlines()
    matches: dict[tuple[str, frozenset[str]], str | None] = {}
    date_pattern = re.compile(
        r"^(\d{2})\.(\d{2})\.\d{2}(?:\s+\((\d{2})\.(\d{2})\))?"
    )
    teams_pattern = re.compile(r"^([A-Z]{3}) - ([A-Z]{3})(?:\s|$)")
    for index, line in enumerate(lines):
        date_match = date_pattern.match(line)
        if not date_match:
            continue
        day, month, hour, minute = date_match.groups()
        teams_match = None
        for candidate in lines[index + 1 : index + 8]:
            teams_match = teams_pattern.match(candidate)
            if teams_match:
                break
        if not teams_match:
            continue
        nearby = "\n".join(lines[index + 1 : index + 12]).lower()
        if "match cancelled" in nearby:
            continue
        codes = teams_match.groups()
        if any(code not in RSSSF_CODES for code in codes):
            raise ValueError(f"Unknown RSSSF team code in {teams_match.group(0)}")
        date = f"{year:04d}-{month}-{day}"
        time = f"{hour}:{minute}" if hour and minute else None
        key = match_key(date, RSSSF_CODES[codes[0]], RSSSF_CODES[codes[1]])
        if key in matches:
            raise ValueError(f"Duplicate RSSSF match identity for {date} {codes}")
        matches[key] = time
    return matches


def source_selection(
    item: dict[str, object],
    fifa_item: dict[str, object],
    rsssf_time: str | None,
    override: dict[str, object] | None,
    note: str | None,
) -> tuple[str, str, str, str | None]:
    wikipedia_time = str(item["wikipedia_local_time"])
    fifa_time = str(fifa_item["fifa_local_time"])
    if override:
        selected = str(override["time"])
        source = str(override["selected_source"])
        confidence = str(
            override.get(
                "confidence",
                "confirmed" if rsssf_time == selected else "corroborated",
            )
        )
        return selected, source, confidence, note
    if rsssf_time:
        comparisons = (("Wikipedia", wikipedia_time), ("FIFA", fifa_time))
        agreeing = [
            name
            for name, value in comparisons
            if value == rsssf_time
        ]
        disagreeing = [
            f"{name} reports {value}"
            for name, value in comparisons
            if value != rsssf_time
        ]
        source = "RSSSF full tournament record"
        confidence = "corroborated" if agreeing else "provisional"
        if not note and agreeing:
            note = f"RSSSF {rsssf_time} agrees with {' and '.join(agreeing)}"
            if disagreeing:
                note += f"; {' and '.join(disagreeing)}"
            note += "."
        elif not note:
            note = (
                f"Selected RSSSF {rsssf_time} as the historical baseline; "
                f"Wikipedia reports {wikipedia_time} and FIFA reports {fifa_time}."
            )
        return rsssf_time, source, confidence, note
    if wikipedia_time != fifa_time:
        raise ValueError(
            f"RSSSF has no time and fallback sources conflict for "
            f"{item['fifa_match_id']}: Wikipedia={wikipedia_time}, FIFA={fifa_time}"
        )
    return (
        fifa_time,
        "Archived FIFA tournament match centre, corroborated by Wikipedia",
        "corroborated",
        note or f"RSSSF has no recorded kickoff; FIFA and Wikipedia agree on {fifa_time}.",
    )


def reconcile(year: int) -> dict[str, object]:
    config = TOURNAMENTS[year]
    wikipedia: list[dict[str, object]] = []
    for title in config["pages"]:
        wikipedia.extend(parse_wikipedia_page(title, len(wikipedia)))
    fifa = parse_fifa_archive(fetch_text(config["archive_url"]))
    rsssf = parse_rsssf(fetch_text(config["rsssf_url"]), year)
    for old_key, corrected_date in config.get("rsssf_date_corrections", {}).items():
        if old_key not in rsssf:
            raise ValueError(f"RSSSF correction source identity not found: {old_key}")
        corrected_key = (corrected_date, old_key[1])
        if corrected_key in rsssf:
            raise ValueError(f"RSSSF correction would duplicate {corrected_key}")
        rsssf[corrected_key] = rsssf.pop(old_key)
    expected = config["expected_matches"]
    if len(wikipedia) != expected or len(fifa) != expected or len(rsssf) != expected:
        raise ValueError(
            f"Expected {expected} matches for {year}; found "
            f"Wikipedia={len(wikipedia)}, FIFA={len(fifa)}, RSSSF={len(rsssf)}"
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
        rsssf_key = match_key(
            str(item["date"]), str(item["team1"]), str(item["team2"])
        )
        if rsssf_key not in rsssf:
            raise ValueError(f"No RSSSF match for {rsssf_key}")
        rsssf_time = rsssf[rsssf_key]
        note = config["conflict_notes"].get(match_id)
        local_time, selected_source, confidence, note = source_selection(
            item, fifa_item, rsssf_time, override, note
        )
        hour, minute = map(int, local_time.split(":"))
        date = datetime.strptime(str(item["date"]), "%Y-%m-%d")
        local = date.replace(hour=hour, minute=minute, tzinfo=timezone_info)
        wikipedia_time = str(item["wikipedia_local_time"])
        fifa_time = str(fifa_item["fifa_local_time"])
        source_values = {
            "rsssf": rsssf_time,
            "wikipedia": wikipedia_time,
            "fifa_archive": fifa_time,
        }
        if override:
            source_values.update(override.get("reported_alternatives", {}))
        records.append(
            {
                **item,
                **(
                    {"event_note": config["event_notes"][match_id]}
                    if match_id in config.get("event_notes", {})
                    else {}
                ),
                "local_time": local_time,
                "local_time_sources": {
                    "selected": selected_source,
                    "confidence": confidence,
                    **source_values,
                    **(
                        {
                            "evidence_url": override["evidence_url"],
                            **(
                                {"evidence_reference": override["evidence_reference"]}
                                if override.get("evidence_reference")
                                else {}
                            ),
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
            "Local clock times use RSSSF full tournament records as the baseline, "
            "with documented primary-evidence overrides and an explicit fallback "
            "when RSSSF omits a time. Wikipedia and archived FIFA values are "
            "retained for comparison; official match numbers come from FIFA and "
            "UTC conversion uses historical IANA timezone rules."
        ),
        "timezone_note": (
            "RSSSF and other source values are interpreted as local clock times. "
            "FIFA's derived UTC fields are retained for audit but are not used. "
            "The selected time is converted with the historical IANA host timezone."
        ),
        **({"source_notes": config["source_notes"]} if config.get("source_notes") else {}),
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
