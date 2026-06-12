#!/usr/bin/env python3
from __future__ import annotations

from common import ROOT, fold_ics_line, load_json
from generate_historical_calendar import build_event_lines


def validated_years() -> list[int]:
    years: list[int] = []
    for path in (ROOT / "data").glob("[0-9][0-9][0-9][0-9]/worldcup.manifest.json"):
        manifest = load_json(path)
        if (
            manifest.get("status") == "validated"
            and manifest.get("calendar_profile") == "archive"
        ):
            years.append(int(manifest["year"]))
    return sorted(years)


def main() -> None:
    years = validated_years()
    if not years:
        raise ValueError("No validated archive tournaments found")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//world-cup-ics//Complete FIFA World Cup History//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:FIFA World Cup History",
        "X-WR-CALDESC:Validated FIFA World Cup finals fixtures and results",
    ]
    count = 0
    for year in years:
        events, event_count = build_event_lines(year)
        lines.extend(events)
        count += event_count
    lines.append("END:VCALENDAR")
    folded = [part for line in lines for part in fold_ics_line(line)]
    output = ROOT / "ics" / "world-cup.ics"
    output.write_bytes(("\r\n".join(folded) + "\r\n").encode("utf-8"))
    print(f"Generated {output.relative_to(ROOT)} with {count} events from {years}")


if __name__ == "__main__":
    main()
