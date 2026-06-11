#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from common import (
    CALENDAR_PATH,
    DATA_DIR,
    country_index,
    display_city,
    event_uid,
    format_geo,
    fold_ics_line,
    ics_escape,
    load_json,
    match_key,
    normalize_name,
    parse_kickoff,
    semantic_hash,
    stage_label,
    utc_stamp,
    validate_worldcup,
    write_json,
)


FORZA_URL_TEMPLATE = "https://forzafootball.com/match/{forza_match_id}"
STATE_PATH = DATA_DIR / "worldcup.calendar-state.json"


def generation_time() -> datetime:
    configured = os.environ.get("CALENDAR_NOW")
    if configured:
        value = datetime.fromisoformat(configured.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc).replace(microsecond=0)
    return datetime.now(timezone.utc).replace(microsecond=0)


def team_details(name: str, countries: dict[str, dict[str, Any]]) -> dict[str, str]:
    country = countries.get(normalize_name(name))
    if not country:
        return {"name": name, "code": name, "flag": ""}
    return {
        "name": country["name"],
        "code": country["fifa_code"],
        "flag": country.get("flag_icon", ""),
    }


def home_display(team: dict[str, str]) -> str:
    return " ".join(part for part in (team["flag"], team["code"]) if part)


def away_display(team: dict[str, str]) -> str:
    return " ".join(part for part in (team["code"], team["flag"]) if part)


def score_summary(match: dict[str, Any], home: dict[str, str], away: dict[str, str]) -> str:
    score = match.get("score")
    if not score:
        return f"{home_display(home)} vs {away_display(away)}"

    home_text = home_display(home)
    away_text = away_display(away)
    if score.get("p") is not None:
        result = score.get("et") or score.get("ft")
        penalties = score["p"]
        if penalties[0] > penalties[1]:
            home_text += " (p)"
        elif penalties[1] > penalties[0]:
            away_text = "(p) " + away_text
        return f"{home_text} {result[0]}-{result[1]} {away_text}"
    if score.get("et") is not None:
        result = score["et"]
        return f"{home_text} {result[0]}-{result[1]} (aet) {away_text}"
    result = score["ft"]
    return f"{home_text} {result[0]}-{result[1]} {away_text}"


def goal_text(goal: dict[str, Any]) -> str:
    minute = str(goal["minute"])
    if goal.get("offset"):
        minute += f"+{goal['offset']}"
    suffix = " pen" if goal.get("penalty") else ""
    return f"{goal['name']} {minute}'{suffix}"


def description(
    match: dict[str, Any],
    home: dict[str, str],
    away: dict[str, str],
    channel: str | None,
) -> str:
    lines: list[str] = []
    score = match.get("score")
    if score:
        final_score = score.get("et") or score.get("ft")
        lines.append(
            f"{home['name']} {final_score[0]}-{final_score[1]} {away['name']}"
        )
        if score.get("ht") is not None:
            lines.append(f"HT: {score['ht'][0]}-{score['ht'][1]}")
        if score.get("et") is not None:
            if score.get("ft") is not None:
                lines.append(f"FT: {score['ft'][0]}-{score['ft'][1]}")
            lines.append(f"AET: {score['et'][0]}-{score['et'][1]}")
        if score.get("p") is not None:
            lines.append(f"Pens: {score['p'][0]}-{score['p'][1]}")

        goals1 = match.get("goals1") or []
        goals2 = match.get("goals2") or []
        if goals1 or goals2:
            lines.append("Goals:")
            if goals1:
                lines.append(f"{home['code']}: " + ", ".join(map(goal_text, goals1)))
            if goals2:
                lines.append(f"{away['code']}: " + ", ".join(map(goal_text, goals2)))

    lines.append(f"TV: {channel or 'TBC'}")
    return "\n".join(lines)


def location(match: dict[str, Any], stadiums: dict[str, dict[str, Any]]) -> str:
    stadium = stadiums.get(match["ground"])
    if not stadium:
        return match["ground"]
    return f"{stadium['name']}, {display_city(stadium['city'])}"


def geo(match: dict[str, Any], stadiums: dict[str, dict[str, Any]]) -> str:
    stadium = stadiums.get(match["ground"])
    if not stadium:
        raise ValueError(f"No stadium coordinates for {match['ground']}")
    return format_geo(stadium["coords"])


def event_lines(properties: dict[str, Any]) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{properties['uid']}",
        f"DTSTAMP:{properties['last_modified']}",
        f"LAST-MODIFIED:{properties['last_modified']}",
        f"SEQUENCE:{properties['sequence']}",
        f"DTSTART:{properties['dtstart']}",
        f"DTEND:{properties['dtend']}",
        f"SUMMARY:{ics_escape(properties['summary'])}",
        f"LOCATION:{ics_escape(properties['location'])}",
        f"GEO:{properties['geo']}",
        f"DESCRIPTION:{ics_escape(properties['description'])}",
        f"URL:{properties['url']}",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "CATEGORIES:FIFA World Cup 2026",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        "DESCRIPTION:Kickoff in 15 minutes",
        "TRIGGER:-PT15M",
        "END:VALARM",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        "DESCRIPTION:Kickoff",
        "TRIGGER:PT0S",
        "END:VALARM",
        "END:VEVENT",
    ]
    return lines


def main() -> None:
    source = load_json(DATA_DIR / "worldcup.json")
    uidmap = load_json(DATA_DIR / "worldcup.uidmap.json")
    validate_worldcup(source, uidmap)
    matches = source["matches"]
    countries = country_index(load_json(DATA_DIR.parent / "countries.json"))
    stadium_data = load_json(DATA_DIR / "worldcup.stadiums.json")
    stadiums = {item["city"]: item for item in stadium_data["stadiums"]}
    forza = load_json(DATA_DIR / "worldcup.forza.json")
    broadcasters = load_json(DATA_DIR / "worldcup.broadcasters.json")
    overrides = load_json(DATA_DIR / "overrides.json")
    previous_state = load_json(STATE_PATH) if STATE_PATH.exists() else {}
    next_state: dict[str, Any] = {}
    now = utc_stamp(generation_time())

    calendar_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//world-cup-ics//FIFA World Cup 2026//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:FIFA World Cup 2026",
        "X-WR-CALDESC:Fixtures and results for the FIFA World Cup 2026",
        "REFRESH-INTERVAL;VALUE=DURATION:PT2H",
        "X-PUBLISHED-TTL:PT2H",
    ]

    for index, match in enumerate(matches):
        sequence = index + 1
        key = match_key(sequence)
        home = team_details(match["team1"], countries)
        away = team_details(match["team2"], countries)
        override = overrides.get(key, {})
        channel = override.get("channel", broadcasters.get(key, {}).get("channel"))
        forza_id = override.get("forza_match_id", forza[key]["forza_match_id"])
        kickoff = parse_kickoff(match)
        duration = timedelta(hours=2) if match["round"].startswith("Matchday") else timedelta(hours=3)
        semantic = {
            "uid": event_uid(sequence),
            "dtstart": utc_stamp(kickoff),
            "dtend": utc_stamp(kickoff + duration),
            "summary": (
                f"[{stage_label(matches, index)}] "
                f"{score_summary(match, home, away)} [{sequence:03d}]"
            ),
            "location": location(match, stadiums),
            "geo": geo(match, stadiums),
            "description": description(match, home, away, channel),
            "url": FORZA_URL_TEMPLATE.format(forza_match_id=forza_id),
        }
        content_hash = semantic_hash(semantic)
        prior = previous_state.get(key)
        if prior and prior.get("content_hash") == content_hash:
            revision = prior["sequence"]
            modified = prior["last_modified"]
        else:
            revision = (prior["sequence"] + 1) if prior else 0
            modified = now
        next_state[key] = {
            "content_hash": content_hash,
            "sequence": revision,
            "last_modified": modified,
        }
        calendar_lines.extend(
            event_lines({**semantic, "sequence": revision, "last_modified": modified})
        )

    calendar_lines.append("END:VCALENDAR")
    folded = [part for line in calendar_lines for part in fold_ics_line(line)]
    CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALENDAR_PATH.write_bytes(("\r\n".join(folded) + "\r\n").encode("utf-8"))
    write_json(STATE_PATH, next_state)
    print(f"Generated {CALENDAR_PATH.relative_to(CALENDAR_PATH.parents[1])} with 104 events")


if __name__ == "__main__":
    main()
