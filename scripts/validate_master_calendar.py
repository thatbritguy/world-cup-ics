#!/usr/bin/env python3
from __future__ import annotations

from common import ROOT, load_json
from validate_historical_calendar import unfold


def main() -> None:
    manifests = []
    for path in (ROOT / "data").glob("[0-9][0-9][0-9][0-9]/worldcup.manifest.json"):
        value = load_json(path)
        if value.get("status") == "validated" and value.get("calendar_profile") == "archive":
            manifests.append(value)
    manifests.sort(key=lambda item: item["year"])
    expected_uids = [
        match["uid"] for manifest in manifests for match in manifest["matches"]
    ]
    raw = (ROOT / "ics" / "world-cup.ics").read_bytes()
    physical = raw.decode("utf-8").split("\r\n")[:-1]
    if any(len(line.encode("utf-8")) > 75 for line in physical):
        raise ValueError("Master calendar contains an overlong physical line")
    lines = unfold(physical)
    uids = [line.removeprefix("UID:") for line in lines if line.startswith("UID:")]
    if uids != expected_uids or len(uids) != len(set(uids)):
        raise ValueError("Master calendar UIDs do not match validated manifests")
    if lines.count("BEGIN:VEVENT") != len(expected_uids):
        raise ValueError("Master calendar event count is incorrect")
    print(
        f"Master calendar validation passed: {len(expected_uids)} events from "
        f"{[item['year'] for item in manifests]}"
    )


if __name__ == "__main__":
    main()
