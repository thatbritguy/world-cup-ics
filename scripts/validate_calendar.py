#!/usr/bin/env python3
from __future__ import annotations

from common import CALENDAR_PATH, DATA_DIR, event_uid, load_json


def unfold(lines: list[str]) -> list[str]:
    output: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and output:
            output[-1] += line[1:]
        else:
            output.append(line)
    return output


def main() -> None:
    raw = CALENDAR_PATH.read_bytes()
    if b"\r\n" not in raw or raw.replace(b"\r\n", b"").find(b"\n") != -1:
        raise ValueError("Calendar must use CRLF line endings")
    physical = raw.decode("utf-8").split("\r\n")[:-1]
    for number, line in enumerate(physical, start=1):
        if len(line.encode("utf-8")) > 75:
            raise ValueError(f"Line {number} exceeds 75 octets")

    lines = unfold(physical)
    if lines[0] != "BEGIN:VCALENDAR" or lines[-1] != "END:VCALENDAR":
        raise ValueError("Invalid VCALENDAR boundaries")
    if lines.count("BEGIN:VEVENT") != 104 or lines.count("END:VEVENT") != 104:
        raise ValueError("Calendar must contain exactly 104 events")
    if lines.count("BEGIN:VALARM") != 208 or lines.count("END:VALARM") != 208:
        raise ValueError("Each event must contain two alerts")

    uids = [line.removeprefix("UID:") for line in lines if line.startswith("UID:")]
    expected = [event_uid(sequence) for sequence in range(1, 105)]
    if uids != expected or len(set(uids)) != 104:
        raise ValueError("Calendar UIDs are missing, duplicated, or out of order")

    required_files = {
        "uidmap": DATA_DIR / "worldcup.uidmap.json",
        "forza": DATA_DIR / "worldcup.forza.json",
        "broadcasters": DATA_DIR / "worldcup.broadcasters.json",
        "state": DATA_DIR / "worldcup.calendar-state.json",
    }
    for label, path in required_files.items():
        value = load_json(path)
        if len(value) != 104:
            raise ValueError(f"{label} must contain 104 entries")

    countries = load_json(DATA_DIR.parent / "countries.json")
    if len(countries) != 48:
        raise ValueError("countries.json must contain all 48 teams")
    england = next(item for item in countries if item["fifa_code"] == "ENG")
    codepoints = [f"{ord(char):X}" for char in england["flag_icon"]]
    expected_codepoints = ["1F3F4", "E0067", "E0062", "E0065", "E006E", "E0067", "E007F"]
    if codepoints != expected_codepoints:
        raise ValueError("England flag is not the full subdivision tag sequence")

    print("Calendar validation passed: 104 events, 104 unique UIDs, 208 alerts")


if __name__ == "__main__":
    main()

