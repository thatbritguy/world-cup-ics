#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from common import ROOT, load_json, normalize_name, write_json
from historical_config import (
    EXCLUDED_OPENFOOTBALL_YEARS,
    FIFA_ARCHIVE_YEARS,
    RSSSF_FULL_YEARS,
    TOURNAMENTS,
    historical_years,
)
from import_historical_times import RSSSF_CODES


OPENFOOTBALL_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/"
    "master/{year}/worldcup.json"
)
RSSSF_URL = (
    "https://raw.githubusercontent.com/rsssf/worldcup/master/pages/{short}full.txt"
)
FIFA_ARCHIVE_URL = (
    "https://web.archive.org/web/20221003182345id_/"
    "https://www.fifa.com/en/tournaments/mens/worldcup/{slug}/match-center"
)
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_SCHEDULE_PAGES = {
    1994: [
        *(f"1994 FIFA World Cup Group {group}" for group in "ABCDEF"),
        "1994 FIFA World Cup knockout stage",
        "1994 FIFA World Cup final",
    ],
    1998: [
        *(f"1998 FIFA World Cup Group {group}" for group in "ABCDEFGH"),
        "1998 FIFA World Cup knockout stage",
        "United States v Iran (1998 FIFA World Cup)",
        "1998 FIFA World Cup final",
    ],
}


def fetch_text(url: str) -> str:
    for attempt in range(5):
        request = Request(
            url,
            headers={"User-Agent": "world-cup-ics/1.0 (historical source auditor)"},
        )
        try:
            with urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8")
        except HTTPError as error:
            if error.code != 429 or attempt == 4:
                raise
            retry_after = error.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
            time.sleep(delay)
    raise RuntimeError(f"Could not fetch {url}")


def fifa_team_codes() -> dict[str, str]:
    """Map official FIFA abbreviations to canonical names."""
    codes: dict[str, str] = {}
    for country in load_json(ROOT / "data" / "countries.json"):
        codes[country["fifa_code"]] = country["name"]
    codes.update(
        {
            # Historical FIFA archive abbreviations not represented by a current
            # member code are still translated to canonical repository names.
            "FRG": "West Germany",
            "GDR": "East Germany",
            "TCH": "Czechoslovakia",
            "URS": "Soviet Union",
            "ZAI": "Zaire",
        }
    )
    return codes


def rsssf_team_codes() -> dict[str, str]:
    """Translate RSSSF's private abbreviations; never emit them as team codes."""
    codes = dict(RSSSF_CODES)
    codes.update(
        {
            "ALG": "Algeria",
            "ARS": "Saudi Arabia",
            "AUS": "Australia",
            "BUL": "Bulgaria",
            "CAM": "Cameroon",
            "CAN": "Canada",
            "CIV": "Ivory Coast",
            "COL": "Colombia",
            "COS": "Costa Rica",
            "CRO": "Croatia",
            "DAN": "Denmark",
            "DDR": "East Germany",
            "ECU": "Ecuador",
            "EMI": "United Arab Emirates",
            "FRG": "West Germany",
            "GDR": "East Germany",
            "GHA": "Ghana",
            "GRE": "Greece",
            "HAI": "Haiti",
            "HON": "Honduras",
            "IRK": "Iraq",
            "IRL": "Republic of Ireland",
            "IRN": "Iran",
            "ISR": "Israel",
            "JAM": "Jamaica",
            "JAP": "Japan",
            "KLD": "North Korea",
            "KOR": "South Korea",
            "KUW": "Kuwait",
            "MAR": "Morocco",
            "NGA": "Nigeria",
            "NIR": "Northern Ireland",
            "NZL": "New Zealand",
            "POR": "Portugal",
            "RSA": "South Africa",
            "RUS": "Russia",
            "SAF": "South Africa",
            "SAL": "El Salvador",
            "SCO": "Scotland",
            "SEN": "Senegal",
            "TCH": "Czechoslovakia",
            "TUN": "Tunisia",
            "TUR": "Turkey",
            "UAE": "United Arab Emirates",
            "URS": "Soviet Union",
            "WAL": "Wales",
            "ZAI": "Zaire",
            "ZSR": "Soviet Union",
        }
    )
    return codes


TEAM_IDENTITY_ALIASES = {
    normalize_name("USA"): normalize_name("United States"),
    normalize_name("Ireland"): normalize_name("Republic of Ireland"),
    normalize_name("Côte d'Ivoire"): normalize_name("Ivory Coast"),
    normalize_name("Cote d'Ivoire"): normalize_name("Ivory Coast"),
    normalize_name("Czechia"): normalize_name("Czech Republic"),
    normalize_name("Korea Republic"): normalize_name("South Korea"),
    normalize_name("FR Yugoslavia"): normalize_name("Yugoslavia"),
    normalize_name("IR Iran"): normalize_name("Iran"),
}


def team_identity(value: str) -> str:
    normalized = normalize_name(value)
    return TEAM_IDENTITY_ALIASES.get(normalized, normalized)


def identity(date: str, team1: str, team2: str) -> tuple[str, frozenset[str]]:
    return date, frozenset((team_identity(team1), team_identity(team2)))


AUDIT_RESOLUTIONS = {
    identity("1954-06-23", "Switzerland", "Italy"): {
        "time": "18:00",
        "selected_source": "RSSSF scheduled kickoff",
        "evidence": "RSSSF records 18:00 and Wikipedia's tournament schedule agrees.",
        "rejected_value": "The archived FIFA dataset omits this playoff fixture.",
    },
    identity("1954-06-26", "Austria", "Switzerland"): {
        "time": "17:00",
        "selected_source": "RSSSF scheduled kickoff",
        "evidence": "RSSSF records 17:00 and Wikipedia's tournament schedule agrees.",
        "rejected_value": "The archived FIFA dataset omits this quarter-final fixture.",
    },
    identity("1958-06-11", "Yugoslavia", "France"): {
        "time": "19:00",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "RSSSF omits the time; FIFA and Wikipedia give 19:00, consistent "
            "with the tournament schedule."
        ),
        "rejected_value": "RSSSF records the fixture but omits its kickoff time.",
    },
    identity("1958-06-17", "Wales", "Hungary"): {
        "time": "19:00",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "RSSSF omits the time; FIFA and Wikipedia give 19:00, consistent "
            "with the tournament schedule."
        ),
        "rejected_value": "RSSSF omits the fixture's kickoff time.",
    },
    identity("1958-06-19", "Sweden", "Soviet Union"): {
        "time": "19:00",
        "selected_source": "Official match programme",
        "evidence": (
            "The official match programme confirms a scheduled 19:00 local "
            "kickoff. FIFA/Wikipedia agree."
        ),
        "rejected_value": "RSSSF reports 14:00.",
    },
    identity("1962-06-03", "Soviet Union", "Colombia"): {
        "time": "15:00",
        "selected_source": "Contemporary and federation evidence",
        "evidence": (
            "The German FA data centre records 15:00; contemporary Chilean "
            "reporting describes Arica group matches at 15:00, and an interview "
            "with the son of Colombian scorer Marcos Coll also refers to 15:00."
        ),
        "evidence_url": (
            "https://www.aldia.co/deportes/ese-gol-olimpico-sirvio-para-que-"
            "el-mundo-conociera-que-habia-un-pais-llamado-colombia"
        ),
        "rejected_value": "RSSSF reports 18:00.",
    },
    identity("1962-06-03", "Hungary", "Bulgaria"): {
        "time": "15:00",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "RSSSF omits the time; FIFA and Wikipedia give 15:00, consistent "
            "with the tournament schedule."
        ),
        "rejected_value": "RSSSF records the fixture but omits its kickoff time.",
    },
    identity("1962-06-06", "Hungary", "Argentina"): {
        "time": "15:00",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "RSSSF omits the time; FIFA and Wikipedia give 15:00, consistent "
            "with the tournament schedule."
        ),
        "rejected_value": "RSSSF records the fixture but omits its kickoff time.",
    },
    identity("1962-06-07", "Mexico", "Czechoslovakia"): {
        "time": "15:00",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "RSSSF omits the time; FIFA and Wikipedia give 15:00, consistent "
            "with the tournament schedule."
        ),
        "rejected_value": "RSSSF records the fixture but omits its kickoff time.",
    },
    identity("1962-06-07", "England", "Bulgaria"): {
        "time": "15:00",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "RSSSF omits the time; FIFA and Wikipedia give 15:00, consistent "
            "with the tournament schedule."
        ),
        "rejected_value": "RSSSF records the fixture but omits its kickoff time.",
    },
    identity("1962-06-17", "Brazil", "Czechoslovakia"): {
        "time": "14:30",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "RSSSF omits the time; FIFA and Wikipedia give 14:30, consistent "
            "with the tournament schedule."
        ),
        "rejected_value": "RSSSF records the fixture but omits its kickoff time.",
    },
    identity("1966-07-16", "England", "Mexico"): {
        "time": "19:30",
        "selected_source": "BBC schedule and German FA data centre",
        "evidence": (
            "BBC television coverage began at 19:00 and the German FA data "
            "centre records a scheduled 19:30 BST kickoff."
        ),
        "evidence_url": "https://genome.ch.bbc.co.uk/651869fb65874e0d82d11b1b8ba1baeb",
        "rejected_value": "RSSSF reports 15:00.",
    },
    identity("1966-07-12", "Brazil", "Bulgaria"): {
        "time": "19:30",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "RSSSF omits the time; FIFA and Wikipedia give 19:30, consistent "
            "with the tournament schedule."
        ),
        "rejected_value": "RSSSF records the fixture but omits its kickoff time.",
    },
    identity("1966-07-23", "England", "Argentina"): {
        "time": "15:00",
        "selected_source": "Contemporary tournament schedule",
        "evidence": (
            "All four quarter-finals on 23 July were scheduled for 15:00, as "
            "documented by The Guardian's review of the 1966 tournament."
        ),
        "evidence_url": (
            "https://www.theguardian.com/football/blog/2016/jul/24/"
            "1966-world-cup-final-conspiracy-refereeing-50-years"
        ),
        "rejected_value": "RSSSF reports 19:30.",
    },
    identity("1974-06-14", "West Germany", "Chile"): {
        "time": "16:00",
        "selected_source": "Contemporary The Times fixture listing",
        "evidence": (
            "The Times, 14 June 1974, lists West Germany-Chile in Berlin at "
            "16:00. Britain and West Germany were both UTC+1 on the match date."
        ),
        "rejected_value": "RSSSF reports 16:30 rather than the scheduled kickoff.",
    },
    identity("1970-06-02", "Uruguay", "Israel"): {
        "time": "16:00",
        "selected_source": "Scheduled kickoff",
        "evidence": (
            "FIFA and Wikipedia record the scheduled 16:00 kickoff. Calendar "
            "events use scheduled times rather than the exact whistle time."
        ),
        "rejected_value": "RSSSF's 16:09 appears to record the actual start.",
    },
    identity("1974-06-15", "Uruguay", "Netherlands"): {
        "time": "16:00",
        "selected_source": "Contemporary The Times fixture listing",
        "evidence": (
            "The Times, 15 June 1974, lists Uruguay-Netherlands in Hanover at "
            "16:00. Britain and West Germany were both UTC+1 on the match date."
        ),
        "rejected_value": "RSSSF reports 18:00 rather than the scheduled kickoff.",
    },
    identity("1974-06-22", "Scotland", "Yugoslavia"): {
        "time": "16:00",
        "selected_source": "Contemporary The Times fixture listing",
        "evidence": (
            "The Times, 22 June 1974, lists Scotland-Yugoslavia in Frankfurt "
            "at 16:00."
        ),
        "rejected_value": "RSSSF reports 18:00 rather than the scheduled kickoff.",
    },
    identity("1974-06-22", "Zaire", "Brazil"): {
        "time": "16:00",
        "selected_source": "Contemporary The Times fixture listing",
        "evidence": (
            "The Times, 22 June 1974, lists Brazil-Zaire in Gelsenkirchen at "
            "16:00."
        ),
        "rejected_value": "RSSSF reports 18:00 rather than the scheduled kickoff.",
    },
    identity("1974-06-26", "Yugoslavia", "West Germany"): {
        "time": "16:00",
        "selected_source": "Contemporary The Times fixture listing",
        "evidence": (
            "The Times, 26 June 1974, lists West Germany-Yugoslavia in "
            "Dusseldorf at 16:00."
        ),
        "rejected_value": "RSSSF reports 18:00 rather than the scheduled kickoff.",
    },
    identity("1974-06-30", "Poland", "Yugoslavia"): {
        "time": "16:00",
        "selected_source": "Contemporary The Times fixture listing",
        "evidence": (
            "The Times, 29 June 1974, lists Yugoslavia-Poland in Frankfurt at "
            "16:00 the following day."
        ),
        "rejected_value": "RSSSF reports 18:00 rather than the scheduled kickoff.",
    },
    identity("1974-06-30", "Argentina", "Brazil"): {
        "time": "16:00",
        "selected_source": "Contemporary fixture schedule and FIFA/Wikipedia",
        "evidence": (
            "Contemporary The Times fixture listings use a 16:00 scheduled "
            "kickoff, agreeing with FIFA and Wikipedia."
        ),
        "rejected_value": "RSSSF records the fixture but omits its kickoff time.",
    },
    identity("1974-07-03", "Poland", "West Germany"): {
        "time": "16:00",
        "selected_source": "Originally scheduled kickoff",
        "evidence": (
            "FIFA's archived match report and Wikipedia record a scheduled "
            "16:00 kickoff delayed by 35 minutes because the pitch was "
            "waterlogged. Calendar events use the scheduled time."
        ),
        "rejected_value": (
            "RSSSF reports the delayed 16:30 start and FIFA archive data reports "
            "17:00; neither is the originally scheduled kickoff."
        ),
    },
    identity("1974-07-06", "Brazil", "Poland"): {
        "time": "16:00",
        "selected_source": "Contemporary fixture schedule and FIFA/Wikipedia",
        "evidence": (
            "Contemporary The Times fixture listings use a 16:00 scheduled "
            "kickoff for the third-place match, agreeing with FIFA and Wikipedia."
        ),
        "rejected_value": "RSSSF omits this fixture's kickoff time.",
    },
    identity("1978-06-10", "France", "Hungary"): {
        "time": "13:45",
        "selected_source": "Originally scheduled kickoff",
        "evidence": (
            "The match was scheduled for 13:45 ART but delayed by a kit clash. "
            "The teams eventually started at 14:30; calendar events use the "
            "scheduled kickoff."
        ),
        "evidence_url": (
            "https://web.archive.org/web/20210727224101/"
            "https://www.fifamuseum.com/en/stories/blog/"
            "when-les-bleus-went-green-and-white-2609859/"
        ),
        "rejected_value": (
            "RSSSF reports the delayed 14:30 start and FIFA archive data "
            "reports 15:10; neither is the scheduled kickoff."
        ),
    },
    identity("1982-06-17", "Czechoslovakia", "Kuwait"): {
        "time": "17:15",
        "selected_source": "Official FIFA guide and contemporary TV listing",
        "evidence": (
            "The official contemporary FIFA tournament guide and a Catalan "
            "television listing both give a scheduled 17:15 local kickoff."
        ),
        "evidence_url": (
            "https://www.catalunyacristiana.cat/hemeroteca2/"
            "Catalunya_Cristiana_0142_19820619_cat.pdf"
        ),
        "rejected_value": "FIFA archive data reports 17:45; RSSSF records 17:15.",
    },
    identity("1982-06-19", "Poland", "Cameroon"): {
        "time": "17:15",
        "selected_source": "Official contemporary FIFA tournament guide",
        "evidence": "FIFA's official 1982 match calendar lists a 17:15 kickoff.",
        "rejected_value": "FIFA archive data reports 19:15; RSSSF records 17:15.",
    },
    identity("1982-06-21", "Algeria", "Austria"): {
        "time": "17:15",
        "selected_source": "Official contemporary FIFA tournament guide",
        "evidence": "FIFA's official 1982 match calendar lists a 17:15 kickoff.",
        "rejected_value": "RSSSF omits the kickoff time.",
    },
    identity("1982-06-25", "West Germany", "Austria"): {
        "time": "17:15",
        "selected_source": "Official contemporary FIFA tournament guide",
        "evidence": "FIFA's official 1982 match calendar lists a 17:15 kickoff.",
        "rejected_value": "RSSSF omits the kickoff time.",
    },
    identity("1982-07-11", "Italy", "West Germany"): {
        "time": "20:00",
        "selected_source": "Official contemporary FIFA tournament guide",
        "evidence": "FIFA's official 1982 match calendar lists the final at 20:00.",
        "rejected_value": "RSSSF omits the kickoff time.",
    },
    identity("1986-06-11", "Paraguay", "Belgium"): {
        "time": "12:00",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "FIFA and Wikipedia record 12:00. It matches Mexico-Iraq, the "
            "simultaneous final Group B fixture played the same day."
        ),
        "rejected_value": "RSSSF records the fixture but omits its kickoff time.",
    },
    identity("1990-06-16", "England", "Netherlands"): {
        "time": "21:00",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "Contemporary UK television listing begins coverage at 19:30 BST; "
            "the scheduled 20:00 BST kickoff equals 21:00 CEST in Italy."
        ),
        "rejected_value": (
            "RSSSF records malformed '17..00'; both punctuation and value are "
            "inconsistent with the contemporary broadcast schedule."
        ),
    },
    identity("1990-06-17", "Republic of Ireland", "Egypt"): {
        "time": "17:00",
        "selected_source": "FIFA/Wikipedia scheduled kickoff",
        "evidence": (
            "The Times day-by-day World Cup schedule published 6 June 1990 "
            "lists a 16:00 UK kickoff; this equals 17:00 CEST in Italy and "
            "agrees with FIFA and Wikipedia."
        ),
        "rejected_value": (
            "RSSSF reverses the fixture order as EGY-IRL and omits the kickoff "
            "time; the unordered team matcher still identifies the fixture."
        ),
    },
}

DATE_RESOLUTIONS = {
    identity("1958-06-28", "West Germany", "France"): {
        "source_date": "1958-06-26",
        "resolution": "RSSSF date typo; contemporary reporting confirms 28 June.",
    },
    identity("1962-05-31", "Hungary", "England"): {
        "source_date": "1962-06-31",
        "resolution": "RSSSF contains the impossible date 31 June; correct date is 31 May.",
    },
    identity("1974-06-26", "Netherlands", "Argentina"): {
        "source_date": "1974-06-22",
        "resolution": "RSSSF date typo; 22 June predates the second group stage fixture.",
    },
    identity("1990-07-07", "Italy", "England"): {
        "source_date": "1990-06-07",
        "resolution": "RSSSF month typo; the third-place match was played 7 July.",
    },
}


def parse_openfootball_time(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    match = re.fullmatch(r"(\d{2}:\d{2})(?: UTC([+-]\d{1,2}))?", value)
    if not match:
        raise ValueError(f"Unsupported openfootball kickoff: {value}")
    return match.group(1), match.group(2)


def parse_rsssf_records(
    text: str, year: int, codes: dict[str, str]
) -> dict[tuple[str, frozenset[str]], str | None]:
    tournament_codes = dict(codes)
    if 1954 <= year <= 1990:
        tournament_codes["GER"] = "West Germany"
    if year <= 1990:
        tournament_codes["CZE"] = "Czechoslovakia"
    lines = text.splitlines()
    records: dict[tuple[str, frozenset[str]], str | None] = {}
    date_pattern = re.compile(
        r"^(\d{2})\.(\d{2})\.\d{2}(?:\s+\((\d{2})\.+(\d{2})\))?"
    )
    teams_pattern = re.compile(r"^([A-Z]{3}) - ([A-Z]{3})(?:\s|$)", re.IGNORECASE)
    lineup_pattern = re.compile(r"^([A-Z]{3}):", re.IGNORECASE)
    for index, line in enumerate(lines):
        date_match = date_pattern.match(line)
        if not date_match:
            continue
        day, month, hour, minute = date_match.groups()
        teams_match = next(
            (
                teams_pattern.match(candidate)
                for candidate in lines[index + 1 : index + 8]
                if teams_pattern.match(candidate)
            ),
            None,
        )
        if teams_match:
            team_codes = tuple(code.upper() for code in teams_match.groups())
        else:
            lineup_codes: list[str] = []
            for candidate in lines[index + 1 : index + 35]:
                lineup_match = lineup_pattern.match(candidate)
                if lineup_match:
                    code = lineup_match.group(1).upper()
                    if code not in lineup_codes:
                        lineup_codes.append(code)
                if len(lineup_codes) == 2:
                    break
            if len(lineup_codes) != 2:
                continue
            team_codes = tuple(lineup_codes)
        nearby = "\n".join(lines[index + 1 : index + 12]).lower()
        if "match cancelled" in nearby:
            continue
        unknown = [code for code in team_codes if code not in tournament_codes]
        if unknown:
            raise ValueError(f"Unknown RSSSF team codes: {', '.join(unknown)}")
        key = identity(
            f"{year:04d}-{month}-{day}",
            tournament_codes[team_codes[0]],
            tournament_codes[team_codes[1]],
        )
        if key in records:
            raise ValueError(f"Duplicate RSSSF match identity: {key}")
        records[key] = f"{hour}:{minute}" if hour and minute else None
    return records


def parse_fifa_records(html: str, codes: dict[str, str]) -> dict[tuple[str, frozenset[str]], dict[str, object]]:
    pattern = re.compile(
        r'"idMatch":"(?P<id>\d+)","idCompetition":"(?P<competition>\d+)",'
        r'"idSeason":"(?P<season>\d+)","idStage":"(?P<stage>\d+)".*?'
        r'"date":"(?P<utc>[^"]+)".*?'
        r'"localDate":"(?P<local>[^"]+)".*?'
        r'"awayTeam":\{"abbreviation":"(?P<away>[^"]+)".*?'
        r'"homeTeam":\{"abbreviation":"(?P<home>[^"]+)".*?'
        r'"matchNumber":(?P<number>\d+)',
        re.DOTALL,
    )
    records: dict[tuple[str, frozenset[str]], dict[str, object]] = {}
    for match in pattern.finditer(html):
        home_code = match.group("home")
        away_code = match.group("away")
        if home_code not in codes or away_code not in codes:
            continue
        local = match.group("local")
        key = identity(local[:10], codes[home_code], codes[away_code])
        records[key] = {
            "time": local[11:16],
            "utc": match.group("utc"),
            "match_id": match.group("id"),
            "match_number": int(match.group("number")),
            "competition_id": match.group("competition") if "competition" in match.groupdict() else None,
            "season_id": match.group("season") if "season" in match.groupdict() else None,
            "stage_id": match.group("stage") if "stage" in match.groupdict() else None,
        }
    return records


def parse_wikipedia_schedule(wikitext: str) -> dict[tuple[str, frozenset[str]], str]:
    records: dict[tuple[str, frozenset[str]], str] = {}
    current: dict[str, str] = {}
    for line in wikitext.splitlines():
        if line.startswith("|date="):
            current = {"date": line.removeprefix("|date=")}
        elif current and line.startswith("|time="):
            current["time"] = line.removeprefix("|time=")
        elif current and line.startswith("|report="):
            report = line.removeprefix("|report=")
            date_match = re.search(
                r"\{\{Start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})", current["date"]
            )
            time_match = re.search(
                r"(\d{1,2}):(\d{2})(?:&nbsp;|\s)*(a\.m\.|p\.m\.)?",
                current.get("time", ""),
            )
            title_match = re.search(r"\|title=([^|]+?)\s*\{\{!\}\}", report)
            if date_match and time_match and title_match:
                teams = re.split(
                    r"\s+(?:vs|v)\s+", title_match.group(1).strip(), maxsplit=1
                )
                if len(teams) == 2:
                    hour = int(time_match.group(1))
                    period = time_match.group(3)
                    if period == "p.m." and hour < 12:
                        hour += 12
                    elif period == "a.m." and hour == 12:
                        hour = 0
                    year, month, day = map(int, date_match.groups())
                    records[
                        identity(
                            f"{year:04d}-{month:02d}-{day:02d}", teams[0], teams[1]
                        )
                    ] = f"{hour:02d}:{time_match.group(2)}"
            current = {}
    return records


def wikipedia_schedule(year: int, cache_dir: Path) -> dict[tuple[str, frozenset[str]], str]:
    records: dict[tuple[str, frozenset[str]], str] = {}
    for index, title in enumerate(WIKIPEDIA_SCHEDULE_PAGES.get(year, []), start=1):
        path = cache_dir / f"wikipedia-{index}.txt"
        if path.exists():
            text = path.read_text(encoding="utf-8")
        else:
            query = urlencode(
                {
                    "action": "parse",
                    "format": "json",
                    "page": title,
                    "prop": "wikitext",
                    "formatversion": 2,
                }
            )
            text = json.loads(fetch_text(f"{WIKIPEDIA_API}?{query}"))["parse"]["wikitext"]
            path.write_text(text, encoding="utf-8")
        records.update(parse_wikipedia_schedule(text))
    return records


def source_value(
    records: dict[tuple[str, frozenset[str]], object],
    key: tuple[str, frozenset[str]],
    pair_occurrences: Counter[frozenset[str]],
) -> tuple[object | None, str | None]:
    if key in records:
        return records[key], key[0]
    if pair_occurrences[key[1]] != 1:
        return None, None
    same_teams = [
        (candidate[0], value)
        for candidate, value in records.items()
        if candidate[1] == key[1]
    ]
    return (same_teams[0][1], same_teams[0][0]) if len(same_teams) == 1 else (None, None)


def classify(year: int, times: dict[str, str | None]) -> tuple[str, str | None]:
    available = [value for value in times.values() if value]
    if not available:
        return "missing", None
    counts = Counter(available)
    selected, count = counts.most_common(1)[0]
    if count >= 2:
        return "corroborated", selected
    if len(available) == 1:
        if year >= 2002 and (times.get("fifa_archive") or times.get("openfootball")):
            return "accepted-modern-source", selected
        return "single-source", selected
    return "conflict", times.get("rsssf") or selected


def audit_year(year: int, cache_dir: Path) -> dict[str, object]:
    if year in EXCLUDED_OPENFOOTBALL_YEARS or year not in TOURNAMENTS:
        raise ValueError(f"{year} is not an allowed men's FIFA World Cup finals year")
    cache_dir.mkdir(parents=True, exist_ok=True)
    config = TOURNAMENTS[year]

    openfootball_path = cache_dir / "openfootball.json"
    openfootball_text = (
        openfootball_path.read_text(encoding="utf-8")
        if openfootball_path.exists()
        else fetch_text(OPENFOOTBALL_URL.format(year=year))
    )
    openfootball_path.write_text(openfootball_text, encoding="utf-8")
    openfootball = json.loads(openfootball_text)

    rsssf: dict[tuple[str, frozenset[str]], str | None] = {}
    if year in RSSSF_FULL_YEARS:
        rsssf_path = cache_dir / "rsssf-full.txt"
        text = (
            rsssf_path.read_text(encoding="utf-8")
            if rsssf_path.exists()
            else fetch_text(RSSSF_URL.format(short=str(year)[2:]))
        )
        rsssf_path.write_text(text, encoding="utf-8")
        rsssf = parse_rsssf_records(text, year, rsssf_team_codes())

    fifa: dict[tuple[str, frozenset[str]], dict[str, object]] = {}
    if year in FIFA_ARCHIVE_YEARS:
        fifa_path = cache_dir / "fifa-match-centre.html"
        text = (
            fifa_path.read_text(encoding="utf-8")
            if fifa_path.exists()
            else fetch_text(FIFA_ARCHIVE_URL.format(slug=config["slug"]))
        )
        fifa_path.write_text(text, encoding="utf-8")
        fifa = parse_fifa_records(text, fifa_team_codes())

    wikipedia = wikipedia_schedule(year, cache_dir)

    matches: list[dict[str, object]] = []
    pair_occurrences = Counter(
        identity(match["date"], match["team1"], match["team2"])[1]
        for match in openfootball["matches"]
        if match.get("score")
    )
    for match in openfootball["matches"]:
        if not match.get("score"):
            continue
        key = identity(match["date"], match["team1"], match["team2"])
        openfootball_time, openfootball_offset = parse_openfootball_time(match.get("time"))
        rsssf_time, rsssf_date = source_value(rsssf, key, pair_occurrences)
        fifa_item, fifa_date = source_value(fifa, key, pair_occurrences)
        wikipedia_time, wikipedia_date = source_value(
            wikipedia, key, pair_occurrences
        )
        fifa_time = fifa_item.get("time") if isinstance(fifa_item, dict) else None
        status, selected = classify(
            year,
            {
                "rsssf": rsssf_time if isinstance(rsssf_time, str) else None,
                "fifa_archive": fifa_time if isinstance(fifa_time, str) else None,
                "openfootball": openfootball_time,
                "wikipedia": (
                    wikipedia_time if isinstance(wikipedia_time, str) else None
                ),
            }
        )
        resolution = AUDIT_RESOLUTIONS.get(key)
        if year in WIKIPEDIA_SCHEDULE_PAGES and isinstance(wikipedia_time, str):
            resolution = {
                "time": wikipedia_time,
                "selected_source": (
                    "Contemporary LA Times schedule corroborated by Wikipedia"
                    if year == 1994
                    else "FIFA/Wikipedia scheduled kickoff"
                ),
                "evidence": (
                    "The venue-local scheduled kickoff is used. RSSSF's 1994 "
                    "values often record actual starts or inconsistent zones."
                    if year == 1994
                    else "France observed CEST (UTC+2); the scheduled French "
                    "local time is used rather than RSSSF's mostly UK-time values."
                ),
                "rejected_value": (
                    f"RSSSF reports {rsssf_time}." if rsssf_time else "RSSSF omits the time."
                ),
            }
        date_resolution = DATE_RESOLUTIONS.get(key)
        if resolution:
            status = "resolved"
            selected = str(resolution["time"])
        matches.append(
            {
                "date": match["date"],
                "team1": match["team1"],
                "team2": match["team2"],
                "ground": match["ground"],
                "sources": {
                    "rsssf": rsssf_time,
                    "rsssf_date": rsssf_date,
                    "fifa_archive": fifa_time,
                    "fifa_archive_date": fifa_date,
                    "openfootball": openfootball_time,
                    "openfootball_utc_offset": openfootball_offset,
                    **(
                        {
                            "wikipedia": wikipedia_time,
                            "wikipedia_date": wikipedia_date,
                        }
                        if year in WIKIPEDIA_SCHEDULE_PAGES
                        else {}
                    ),
                },
                "selected_local_time": selected,
                "status": status,
                **({"resolution": resolution} if resolution else {}),
                **({"date_resolution": date_resolution} if date_resolution else {}),
                "date_mismatch": any(
                    source_date and source_date != match["date"]
                    for source_date in (rsssf_date, fifa_date)
                )
                and not date_resolution,
                "fifa_match_id": fifa_item.get("match_id") if isinstance(fifa_item, dict) else None,
                "fifa_match_number": fifa_item.get("match_number") if isinstance(fifa_item, dict) else None,
            }
        )

    counts = Counter(item["status"] for item in matches)
    manifest_path = ROOT / "data" / str(year) / "worldcup.manifest.json"
    existing_manifest = load_json(manifest_path) if manifest_path.exists() else None
    already_validated = bool(
        existing_manifest and existing_manifest.get("status") == "validated"
    )
    unresolved_source_issue = any(
        item["status"] in {"conflict", "missing", "single-source"}
        or item["date_mismatch"]
        for item in matches
    )
    return {
        "year": year,
        "allowed_world_cup": True,
        "host_timezone": config["timezone"],
        "source_availability": {
            "openfootball": True,
            "rsssf_full": bool(rsssf),
            "fifa_archive": bool(fifa),
            **(
                {"wikipedia_schedule": bool(wikipedia)}
                if year in WIKIPEDIA_SCHEDULE_PAGES
                else {}
            ),
        },
        "match_count": len(matches),
        "status_counts": dict(sorted(counts.items())),
        "existing_calendar_status": (
            existing_manifest.get("status") if existing_manifest else None
        ),
        "source_issues_resolved_in_enrichment": already_validated
        and unresolved_source_issue,
        "requires_review": unresolved_source_issue and not already_validated,
        "matches": matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("years", nargs="*", type=int)
    args = parser.parse_args()
    years = tuple(args.years) if args.years else historical_years()
    reports_dir = ROOT / "reports" / "historical"
    cache_root = ROOT / "data" / "historical-sources"
    summary: list[dict[str, object]] = []
    for year in years:
        if year in EXCLUDED_OPENFOOTBALL_YEARS:
            raise ValueError("2025 is explicitly excluded: it is the FIFA Club World Cup")
        try:
            report = audit_year(year, cache_root / str(year))
            write_json(reports_dir / f"{year}.json", report)
            summary.append(
                {
                    "year": year,
                    "match_count": report["match_count"],
                    "status_counts": report["status_counts"],
                    "requires_review": report["requires_review"],
                    "error": None,
                }
            )
            print(f"Audited {year}: {report['status_counts']}")
        except Exception as error:
            summary.append(
                {
                    "year": year,
                    "match_count": 0,
                    "status_counts": {},
                    "requires_review": True,
                    "error": str(error),
                }
            )
            print(f"Audit failed for {year}: {error}")
    totals = Counter()
    for item in summary:
        totals.update(item["status_counts"])
    write_json(
        reports_dir / "summary.json",
        {
            "years": list(years),
            "excluded_openfootball_years": sorted(EXCLUDED_OPENFOOTBALL_YEARS),
            "status_totals": dict(sorted(totals.items())),
            "tournaments": summary,
        },
    )


if __name__ == "__main__":
    main()
