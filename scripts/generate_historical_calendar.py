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

    return match["date"], name(match["team1"]), name(match["team2"])


def stage_label(match: dict[str, Any], knockout_number: int | None = None) -> str:
    if match.get("group"):
        return f"G{match['group'].removeprefix('Group ')}"
    if match["round"] == "Semi-finals":
        return f"SF{knockout_number}"
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
    proposed = {
        "year": year,
        "numbering": "chronological kickoff order; source order breaks identical kickoff ties",
        "matches": [
            {
                "sequence": index,
                "key": f"wc{year}-match-{index:03d}",
                "uid": f"wc{year}-match-{index:03d}@{UID_DOMAIN}",
                "date": item["date"],
                "team1": item["team1"],
                "team2": item["team2"],
            }
            for index, item in enumerate(matches, start=1)
        ],
    }
    if path.exists():
        current = load_json(path)
        if current != proposed:
            raise ValueError("Historical match identities changed; review manifest explicitly")
        return current
    write_json(path, proposed)
    return proposed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("year", type=int)
    args = parser.parse_args()
    data_dir = ROOT / "data" / str(args.year)

    source = load_json(data_dir / "worldcup.json")
    enrichment = load_json(data_dir / "enrichment.json")["matches"]
    enrichments = {match_identity(item): item for item in enrichment}
    combined: list[dict[str, Any]] = []
    for source_index, match in enumerate(source["matches"]):
        enriched = enrichments.get(match_identity(match))
        if not enriched:
            raise ValueError(f"No kickoff enrichment for {match['date']} {match['team1']} v {match['team2']}")
        combined.append({**match, **enriched, "source_index": source_index})
    combined.sort(key=lambda item: (item["kickoff_utc"], item["source_order"]))

    manifest = build_manifest(args.year, combined, data_dir / "manifest.json")
    countries = country_index(load_json(ROOT / "data" / "countries.json"))
    venue_data = load_json(data_dir / "venues.json")["venues"]
    venues = {alias: venue for venue in venue_data for alias in venue["ground_aliases"]}
    stamp = max(item["kickoff_utc"] for item in combined).replace("-", "").replace(":", "")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//world-cup-ics//FIFA World Cup {args.year}//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:FIFA World Cup {args.year}",
        f"X-WR-CALDESC:Complete fixtures and results for the FIFA World Cup {args.year}",
    ]
    semi_final = 0
    for index, match in enumerate(combined):
        identity = manifest["matches"][index]
        home = team_details(match["team1"], countries)
        away = team_details(match["team2"], countries)
        if match["round"] == "Semi-finals":
            semi_final += 1
            label = stage_label(match, semi_final)
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
        properties = [
            "BEGIN:VEVENT",
            f"UID:{identity['uid']}",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{kickoff.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{(kickoff + duration).strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{ics_escape(f'[{label}] {score_summary(match, home, away)} [{identity['sequence']:03d}]')}",
            f"LOCATION:{ics_escape(location)}",
            f"GEO:{latitude:.6f};{longitude:.6f}",
            structured_location(location, latitude, longitude),
            f"DESCRIPTION:{ics_escape(description(match, home, away))}",
            f"URL:{match['fifa_url']}",
            "STATUS:CONFIRMED",
            "TRANSP:TRANSPARENT",
            f"CATEGORIES:FIFA World Cup {args.year}",
            "END:VEVENT",
        ]
        lines.extend(properties)
    lines.append("END:VCALENDAR")

    output = ROOT / "ics" / f"world-cup-{args.year}.ics"
    folded = [part for line in lines for part in fold_ics_line(line)]
    output.write_bytes(("\r\n".join(folded) + "\r\n").encode("utf-8"))
    print(f"Generated {output.relative_to(ROOT)} with {len(combined)} events")


if __name__ == "__main__":
    main()
