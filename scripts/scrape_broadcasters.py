#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from common import (
    DATA_DIR,
    country_index,
    load_json,
    match_key,
    normalize_name,
    parse_kickoff,
    stage_category,
    validate_worldcup,
    write_json,
)


SOURCE_URL = "https://www.live-footballontv.com/live-world-cup-football-on-tv.html"
ALLOWED_CHANNELS = ("BBC One", "BBC Two", "ITV1", "ITV4")
BROADCAST_END_DATE = date(2026, 7, 19)
LONDON = ZoneInfo("Europe/London")


class FixtureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, str]] = []
        self.capture: tuple[str, int] | None = None
        self.current_date = ""
        self.current: dict[str, Any] | None = None
        self.fixture_depth: int | None = None
        self.fixtures: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        class_name = dict(attrs).get("class") or ""
        self.stack.append((tag, class_name))
        depth = len(self.stack)
        classes = class_name.split()
        if tag == "div" and "fixture-date" in classes:
            self.capture = ("date", depth)
        elif tag == "div" and class_name == "fixture":
            self.current = {
                "date": self.current_date,
                "time": "",
                "teams": "",
                "competition": "",
                "channels": [],
            }
            self.fixture_depth = depth
        elif self.current is not None and tag == "div" and class_name in {
            "fixture__time",
            "fixture__teams",
            "fixture__competition",
        }:
            self.capture = (class_name.removeprefix("fixture__"), depth)
        elif self.current is not None and tag == "span" and "channel-pill" in classes:
            self.capture = ("channel", depth)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            return
        depth = len(self.stack)
        if self.capture and self.capture[1] == depth:
            self.capture = None
        if tag == "div" and self.fixture_depth == depth and self.current is not None:
            self.fixtures.append(self.current)
            self.current = None
            self.fixture_depth = None
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text or not self.capture:
            return
        field = self.capture[0]
        if field == "date":
            self.current_date = text
        elif self.current is not None and field == "channel":
            self.current["channels"].append(text)
        elif self.current is not None:
            self.current[field] += (" " if self.current[field] else "") + text


def parse_page_datetime(date_text: str, time_text: str) -> datetime:
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_text)
    return datetime.strptime(f"{cleaned} {time_text}", "%A %d %B %Y %H:%M").replace(
        tzinfo=LONDON
    )


def page_category(competition: str) -> str:
    suffix = competition.replace("FIFA World Cup 2026", "").strip()
    if suffix.startswith("Group "):
        return f"group:{suffix}"
    normalized = normalize_name(suffix)
    mapping = {
        "roundof32": "r32",
        "roundof16": "r16",
        "quarterfinal": "qf",
        "semifinal": "sf",
        "thirdplaceplayoff": "third",
        "final": "final",
    }
    if normalized not in mapping:
        raise ValueError(f"Unsupported broadcast competition: {competition}")
    return mapping[normalized]


def canonical_team(name: str, countries: dict[str, dict[str, Any]]) -> str:
    country = countries.get(normalize_name(name))
    return country["fifa_code"] if country else normalize_name(name)


def read_page(input_path: Path | None) -> str:
    if input_path:
        return input_path.read_text(encoding="utf-8", errors="replace")
    request = Request(SOURCE_URL, headers={"User-Agent": "world-cup-ics/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="Use downloaded HTML instead of the live page")
    parser.add_argument("--force", action="store_true", help="Ignore date/completion guards")
    args = parser.parse_args()

    target = DATA_DIR / "worldcup.broadcasters.json"
    previous = load_json(target) if target.exists() else {}
    if not args.force and date.today() > BROADCAST_END_DATE:
        print("Broadcast update window has ended")
        return
    if not args.force and len(previous) == 104 and all(
        value.get("channel") in ALLOWED_CHANNELS for value in previous.values()
    ):
        print("All broadcaster slots are already populated")
        return

    fixture_parser = FixtureParser()
    fixture_parser.feed(read_page(args.input))
    page_fixtures = fixture_parser.fixtures
    if len(page_fixtures) != 104:
        raise ValueError(f"Expected 104 broadcast fixtures, found {len(page_fixtures)}")

    source = load_json(DATA_DIR / "worldcup.json")
    validate_worldcup(source)
    matches = source["matches"]
    countries = country_index(load_json(DATA_DIR.parent / "countries.json"))

    team_pairs: dict[tuple[str, str], list[int]] = {}
    for index, match in enumerate(matches):
        pair = (
            canonical_team(match["team1"], countries),
            canonical_team(match["team2"], countries),
        )
        team_pairs.setdefault(pair, []).append(index)

    output = dict(previous)
    used: set[int] = set()
    for fixture in page_fixtures:
        category = page_category(fixture["competition"])
        page_time = parse_page_datetime(fixture["date"], fixture["time"])
        selected: int | None = None
        matched_by = ""

        if " v " in fixture["teams"] and normalize_name(fixture["teams"]) != "tbc":
            home, away = (part.strip() for part in fixture["teams"].split(" v ", 1))
            pair = (canonical_team(home, countries), canonical_team(away, countries))
            candidates = [index for index in team_pairs.get(pair, []) if index not in used]
            if len(candidates) == 1:
                selected = candidates[0]
                matched_by = "teams"

        if selected is None:
            candidates = []
            for index, match in enumerate(matches):
                if index in used or stage_category(match) != category:
                    continue
                source_time = parse_kickoff(match).astimezone(LONDON)
                difference = abs((source_time - page_time).total_seconds())
                if difference <= 90 * 60:
                    candidates.append((difference, index))
            candidates.sort()
            if len(candidates) == 1 or (
                candidates and len(candidates) > 1 and candidates[0][0] < candidates[1][0]
            ):
                selected = candidates[0][1]
                matched_by = "stage_uk_kickoff"

        if selected is None:
            raise ValueError(
                f"Could not match broadcast fixture: {fixture['date']} "
                f"{fixture['time']} {fixture['teams']}"
            )

        used.add(selected)
        key = match_key(selected + 1)
        channel = next(
            (item for item in fixture["channels"] if item in ALLOWED_CHANNELS), None
        )
        if channel is None and key in previous:
            channel = previous[key].get("channel")
        output[key] = {
            "channel": channel,
            "source": "live-footballontv",
            "matched_by": matched_by,
        }

    if len(output) != 104 or len(used) != 104:
        raise ValueError("Broadcaster mapping is incomplete")
    write_json(target, dict(sorted(output.items())))
    populated = sum(value.get("channel") in ALLOWED_CHANNELS for value in output.values())
    print(f"Mapped 104 broadcast slots; {populated} channels populated")


if __name__ == "__main__":
    main()

