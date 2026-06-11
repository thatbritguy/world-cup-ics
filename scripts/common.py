from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "2026"
CALENDAR_PATH = ROOT / "ics" / "world-cup-2026.ics"
MATCH_COUNT = 104
UID_DOMAIN = "world-cup-ics"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(content, encoding="utf-8")


def match_key(sequence: int) -> str:
    return f"wc2026-match-{sequence:03d}"


def event_uid(sequence: int) -> str:
    return f"{match_key(sequence)}@{UID_DOMAIN}"


def normalize_name(value: str) -> str:
    value = value.replace("&", " and ")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def country_index(countries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for country in countries:
        names = [country["name"], *country.get("aliases", [])]
        if country.get("name_normalised"):
            names.append(country["name_normalised"])
        for name in names:
            index[normalize_name(name)] = country
    return index


def parse_kickoff(match: dict[str, Any]) -> datetime:
    parsed = re.fullmatch(r"(\d{2}):(\d{2}) UTC([+-]\d{1,2})", match["time"])
    if not parsed:
        raise ValueError(f"Unsupported kickoff time: {match['time']}")
    hour, minute, offset = parsed.groups()
    tz = timezone(timedelta(hours=int(offset)))
    date = datetime.strptime(match["date"], "%Y-%m-%d")
    return date.replace(hour=int(hour), minute=int(minute), tzinfo=tz)


def utc_stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def stage_category(match: dict[str, Any]) -> str:
    round_name = match["round"]
    if round_name.startswith("Matchday"):
        return f"group:{match.get('group', '')}"
    return {
        "Round of 32": "r32",
        "Round of 16": "r16",
        "Quarter-final": "qf",
        "Semi-final": "sf",
        "Match for third place": "third",
        "Final": "final",
    }[round_name]


def stage_label(matches: list[dict[str, Any]], index: int) -> str:
    match = matches[index]
    round_name = match["round"]
    if round_name.startswith("Matchday"):
        return match["group"].removeprefix("Group ")
    if round_name == "Round of 32":
        return "R32"
    if round_name == "Round of 16":
        return "R16"
    if round_name == "Quarter-final":
        number = sum(item["round"] == round_name for item in matches[: index + 1])
        return f"QF{number}"
    if round_name == "Semi-final":
        number = sum(item["round"] == round_name for item in matches[: index + 1])
        return f"SF{number}"
    if round_name == "Match for third place":
        return "3RD"
    if round_name == "Final":
        return "FINAL"
    raise ValueError(f"Unsupported round: {round_name}")


def validate_worldcup(data: dict[str, Any], uidmap: dict[str, Any] | None = None) -> None:
    matches = data.get("matches")
    if not isinstance(matches, list) or len(matches) != MATCH_COUNT:
        raise ValueError(f"Expected {MATCH_COUNT} matches, found {len(matches or [])}")
    required = {"round", "date", "time", "team1", "team2", "ground"}
    for sequence, match in enumerate(matches, start=1):
        missing = required - match.keys()
        if missing:
            raise ValueError(f"Match {sequence} is missing fields: {sorted(missing)}")
        parse_kickoff(match)
        if uidmap:
            saved = uidmap.get(match_key(sequence))
            if not saved:
                raise ValueError(f"UID map has no entry for match {sequence}")
            if saved["sequence"] != sequence:
                raise ValueError(f"UID map sequence mismatch for match {sequence}")
            if saved["stage_category"] != stage_category(match):
                raise ValueError(
                    f"Match order changed at {sequence}: expected "
                    f"{saved['stage_category']}, found {stage_category(match)}"
                )


def semantic_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def fold_ics_line(line: str, limit: int = 75) -> list[str]:
    encoded = line.encode("utf-8")
    if len(encoded) <= limit:
        return [line]

    folded: list[str] = []
    prefix = ""
    remaining = line
    while remaining:
        available = limit - len(prefix.encode("utf-8"))
        used = 0
        cut = 0
        for cut, char in enumerate(remaining, start=1):
            size = len(char.encode("utf-8"))
            if used + size > available:
                cut -= 1
                break
            used += size
        else:
            cut = len(remaining)
        if cut == 0:
            raise ValueError(f"Unable to fold iCalendar line: {line}")
        folded.append(prefix + remaining[:cut])
        remaining = remaining[cut:]
        prefix = " "
    return folded


def display_city(city: str) -> str:
    parenthetical = re.search(r"\(([^()]*)\)$", city)
    return parenthetical.group(1) if parenthetical else city


def parse_geo(coords: str) -> tuple[float, float]:
    pattern = re.compile(
        r"(?P<degrees>\d+(?:\.\d+)?)°"
        r"(?:(?P<minutes>\d+(?:\.\d+)?)')?"
        r'(?:(?P<seconds>\d+(?:\.\d+)?)")?'
        r"(?P<direction>[NSEW])"
    )
    values: list[float] = []
    for match in pattern.finditer(coords):
        decimal = float(match.group("degrees"))
        decimal += float(match.group("minutes") or 0) / 60
        decimal += float(match.group("seconds") or 0) / 3600
        if match.group("direction") in {"S", "W"}:
            decimal *= -1
        values.append(decimal)
    if len(values) != 2:
        raise ValueError(f"Unsupported stadium coordinates: {coords}")
    return values[0], values[1]


def format_geo(coords: str) -> str:
    latitude, longitude = parse_geo(coords)
    return f"{latitude:.6f};{longitude:.6f}"
