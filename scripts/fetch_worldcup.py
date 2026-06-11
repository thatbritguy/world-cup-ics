#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

from common import DATA_DIR, load_json, validate_worldcup


SOURCE_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/"
    "master/2026/worldcup.json"
)
UPDATE_END_DATE = date(2026, 7, 31)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Ignore the update cutoff")
    args = parser.parse_args()
    if not args.force and date.today() > UPDATE_END_DATE:
        print("Fixture and result update window has ended")
        return

    request = Request(SOURCE_URL, headers={"User-Agent": "world-cup-ics/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = response.read()
    data = json.loads(payload)
    uidmap = load_json(DATA_DIR / "worldcup.uidmap.json")
    validate_worldcup(data, uidmap)

    target = DATA_DIR / "worldcup.json"
    normalized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=target.parent, delete=False
    ) as handle:
        handle.write(normalized)
        temporary = Path(handle.name)
    temporary.replace(target)
    print(f"Updated {target.relative_to(target.parents[2])}")


if __name__ == "__main__":
    main()
