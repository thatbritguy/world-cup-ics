#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re

from common import ROOT, load_json


def unfold(lines: list[str]) -> list[str]:
    output: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and output:
            output[-1] += line[1:]
        else:
            output.append(line)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("year", type=int)
    args = parser.parse_args()
    calendar = ROOT / "ics" / f"world-cup-{args.year}.ics"
    manifest = load_json(ROOT / "data" / str(args.year) / "worldcup.manifest.json")
    expected = len(manifest["matches"])

    raw = calendar.read_bytes()
    if b"\r\n" not in raw or raw.replace(b"\r\n", b"").find(b"\n") != -1:
        raise ValueError("Calendar must use CRLF line endings")
    physical = raw.decode("utf-8").split("\r\n")[:-1]
    for number, line in enumerate(physical, start=1):
        if len(line.encode("utf-8")) > 75:
            raise ValueError(f"Line {number} exceeds 75 octets")
    lines = unfold(physical)
    if lines.count("BEGIN:VEVENT") != expected:
        raise ValueError(f"Expected {expected} events")
    if lines.count("BEGIN:VALARM") != 0:
        raise ValueError("Historical events must not create alerts")

    uids = [line.removeprefix("UID:") for line in lines if line.startswith("UID:")]
    expected_uids = [item["uid"] for item in manifest["matches"]]
    if uids != expected_uids:
        raise ValueError("Calendar UIDs do not match the historical manifest")
    starts = [line for line in lines if line.startswith("DTSTART:")]
    if starts != sorted(starts):
        raise ValueError("Historical events are not in chronological order")
    summaries = [line for line in lines if line.startswith("SUMMARY:")]
    numbers = [int(re.search(r"\[(\d{3})\]$", line).group(1)) for line in summaries]
    if numbers != list(range(1, expected + 1)):
        raise ValueError("Historical visible numbering is not sequential")
    if len([line for line in lines if line.startswith("GEO:")]) != expected:
        raise ValueError("Every historical event must have coordinates")
    print(f"Historical calendar validation passed: {expected} chronological events")


if __name__ == "__main__":
    main()
