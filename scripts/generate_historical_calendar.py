#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from common import (
    ROOT,
    country_index,
    fold_ics_line,
    ics_escape,
    load_json,
    normalize_name,
    write_json,
)


UID_DOMAIN = "world-cup-ics"


def team_details(name: str, countries: dict[str, dict[str, Any]]) -> dict[str, str]:
    country = countries.get(normalize_name(name))
    if not country:
        raise ValueError(f"No country metadata for {name}")
    return {
        "name": country["name"],
        "code": country["fifa_code"],
        "flag": country.get("flag_icon", ""),
    }


def score_summary(match: dict[str, Any], home: dict[str, str], away: dict[str, str]) -> str:
    score = match["score"]
    home_label = " ".join(part for part in (home["flag"], home["code"]) if part)
    away_label = " ".join(part for part in (away["code"], away["flag"]) if part)
    result = score.get("et") or score["ft"]
    suffix = " (aet)" if score.get("et") is not None else ""
    return f"{home_label} {result[0]}-{result[1]}{suffix} {away_label}"


def goal_text(goal: dict[str, Any]) -> str:
    suffix = " pen" if goal.get("penalty") else " og" if goal.get("owngoal") else ""
    return f"{goal['name']} {goal['minute']}'{suffix}"


def description(match: dict[str, Any], home: dict[str, str], away: dict[str, str]) -> str:
    header = match.get("group") or match["round"]
    if match.get("group"):
        header += f" | {match['round']}"
    score = match["score"]
    result = score.get("et") or score["ft"]
    lines = [header, f"{home['name']} {result[0]}-{result[1]} {away['name']}"]
    if score.get("ht") is not None:
        lines.append(f"HT: {score['ht'][0]}-{score['ht'][1]}")
    if score.get("et") is not None:
        lines.append(f"FT: {score['ft'][0]}-{score['ft'][1]}")
        lines.append(f"AET: {score['et'][0]}-{score['et'][1]}")
    goals1 = match.get("goals1") or []
    goals2 = match.get("goals2") or []
    if goals1 or goals2:
        lines.append("Goals:")
        if goals1:
            label = " ".join(part for part in (home["code"], home["flag"]) if part)
            lines.append(f"{label}: " + ", ".join(map(goal_text, goals1)))
        if goals2:
            label = " ".join(part for part in (away["code"], away["flag"]) if part)
            lines.append(f"{label}: " + ", ".join(map(goal_text, goals2)))
    return "\n".join(lines)


def match_identity(match: dict[str, Any]) -> tuple[str, str, str]:
    aliases = {normalize_name("United States"): normalize_name("USA")}

    def name(value: str) -> str:
        normalized = normalize_name(value)
        return aliases.get(normalized, normalized)

    teams = sorted((name(match["team1"]), name(match["team2"])))
    return match["date"], teams[0], teams[1]


def stage_label(match: dict[str, Any], knockout_number: int | None = None) -> str:
    if match.get("group"):
        return f"G{match['group'].removeprefix('Group ')}"
    if match["round"] == "Semi-finals":
        return f"SF{knockout_number}"
    if match["round"] in ("Preliminary round", "First round"):
        return "R16"
    if match["round"] == "First round, Replays":
        return "R16-REPLAY"
    if match["round"] == "Quarter-finals":
        return f"QF{knockout_number}"
    if match["round"] == "Quarter-finals, Replays":
        return "QF-REPLAY"
    if match["round"] in ("Third-place match", "Match for third place"):
        return "3RD"
    if match["round"] == "Final":
        return "FINAL"
    return match["round"].upper().replace(" ", "-")


def structured_location(name: str, latitude: float, longitude: float) -> str:
    title = name.replace('"', "'")
    return (
        'X-APPLE-STRUCTURED-LOCATION;VALUE=URI;'
        f'X-ADDRESS="{title}";X-APPLE-RADIUS=100;X-TITLE="{title}":'
        f"geo:{latitude:.6f},{longitude:.6f}"
    )


def build_manifest(year: int, matches: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    current = load_json(path) if path.exists() else None
    proposed = {
        "year": year,
        "status": current.get("status", "review") if current else "review",
        "calendar_profile": "archive",
        "numbering": "FIFA official match numbers",
        "matches": [
            {
                "sequence": index,
                "key": f"wc{year}-match-{index:03d}",
                "uid": f"wc{year}-match-{index:03d}@{UID_DOMAIN}",
                "date": item["date"],
                "team1": item["team1"],
                "team2": item["team2"],
                "official_match_number": item["official_match_number"],
                "fifa_match_id": item["fifa_match_id"],
            }
            for index, item in enumerate(matches, start=1)
        ],
    }
    if current:
        current_identities = [
            (item["uid"], item["date"], item["team1"], item["team2"])
            for item in current["matches"]
        ]
        proposed_identities = [
            (item["uid"], item["date"], item["team1"], item["team2"])
            for item in proposed["matches"]
        ]
        if current_identities != proposed_identities and current.get("status") == "validated":
            raise ValueError("Historical match identities changed; review manifest explicitly")
        write_json(path, proposed)
        return proposed
    write_json(path, proposed)
    return proposed


def build_event_lines(year: int) -> tuple[list[str], int]:
    data_dir = ROOT / "data" / str(year)

    source = load_json(data_dir / "worldcup.json")
    enrichment = load_json(data_dir / "worldcup.enrichment.json")["matches"]
    enrichments = {match_identity(item): item for item in enrichment}
    combined: list[dict[str, Any]] = []
    played_matches = [match for match in source["matches"] if match.get("score")]
    for source_index, match in enumerate(played_matches):
        enriched = enrichments.get(match_identity(match))
        if not enriched:
            raise ValueError(f"No kickoff enrichment for {match['date']} {match['team1']} v {match['team2']}")
        combined.append({**enriched, **match, "source_index": source_index})
    combined.sort(key=lambda item: int(item["official_match_number"]))

    manifest = build_manifest(year, combined, data_dir / "worldcup.manifest.json")
    countries = country_index(load_json(ROOT / "data" / "countries.json"))
    venue_data = load_json(data_dir / "worldcup.stadiums.json")["venues"]
    venues = {alias: venue for venue in venue_data for alias in venue["ground_aliases"]}
    stamp = max(item["kickoff_utc"] for item in combined).replace("-", "").replace(":", "")

    lines: list[str] = []
    semi_final = 0
    quarter_final = 0
    for index, match in enumerate(combined):
        identity = manifest["matches"][index]
        home = team_details(match["team1"], countries)
        away = team_details(match["team2"], countries)
        if match["round"] == "Semi-finals":
            semi_final += 1
            label = stage_label(match, semi_final)
        elif match["round"] == "Quarter-finals":
            quarter_final += 1
            label = stage_label(match, quarter_final)
        else:
            label = stage_label(match)
        kickoff = datetime.strptime(match["kickoff_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        duration = timedelta(hours=3 if not match.get("group") else 2)
        venue = venues.get(match["ground"])
        if not venue:
            raise ValueError(f"No venue metadata for {match['ground']}")
        latitude = float(venue["latitude"])
        longitude = float(venue["longitude"])
        location = match["ground"]
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{identity['uid']}",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{kickoff.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTEND:{(kickoff + duration).strftime('%Y%m%dT%H%M%SZ')}",
                f"SUMMARY:{ics_escape(f'[{label}] {score_summary(match, home, away)} [{identity['official_match_number']:03d}]')}",
                f"LOCATION:{ics_escape(location)}",
                f"GEO:{latitude:.6f};{longitude:.6f}",
                structured_location(location, latitude, longitude),
                f"DESCRIPTION:{ics_escape(description(match, home, away))}",
                f"URL:{match['fifa_url']}",
                "STATUS:CONFIRMED",
                "TRANSP:TRANSPARENT",
                f"CATEGORIES:FIFA World Cup {year}",
                "END:VEVENT",
            ]
        )
    return lines, len(combined)


def calendar_lines(year: int) -> tuple[list[str], int]:
    events, count = build_event_lines(year)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//world-cup-ics//FIFA World Cup {year}//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:FIFA World Cup {year}",
        f"X-WR-CALDESC:Complete fixtures and results for the FIFA World Cup {year}",
        *events,
        "END:VCALENDAR",
    ]
    return lines, count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("year", type=int)
    args = parser.parse_args()
    lines, count = calendar_lines(args.year)

    output = ROOT / "ics" / f"world-cup-{args.year}.ics"
    folded = [part for line in lines for part in fold_ics_line(line)]
    output.write_bytes(("\r\n".join(folded) + "\r\n").encode("utf-8"))
    print(f"Generated {output.relative_to(ROOT)} with {count} events")


if __name__ == "__main__":
    main()
