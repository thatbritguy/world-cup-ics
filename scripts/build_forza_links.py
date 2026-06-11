#!/usr/bin/env python3
from __future__ import annotations

import argparse
import struct
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from common import (
    DATA_DIR,
    country_index,
    load_json,
    match_key,
    normalize_name,
    validate_worldcup,
    write_json,
)


class MessagePackDecoder:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def read(self, size: int) -> bytes:
        value = self.data[self.offset : self.offset + size]
        self.offset += size
        return value

    def extension(self, size: int) -> dict[str, Any]:
        extension_type = struct.unpack(">b", self.read(1))[0]
        return {"type": extension_type, "data": self.read(size).hex()}

    def decode(self) -> Any:
        code = self.data[self.offset]
        self.offset += 1
        if code <= 0x7F:
            return code
        if code >= 0xE0:
            return code - 256
        if 0x80 <= code <= 0x8F:
            return {self.decode(): self.decode() for _ in range(code & 0x0F)}
        if 0x90 <= code <= 0x9F:
            return [self.decode() for _ in range(code & 0x0F)]
        if 0xA0 <= code <= 0xBF:
            return self.read(code & 0x1F).decode("utf-8")
        if code == 0xC0:
            return None
        if code == 0xC2:
            return False
        if code == 0xC3:
            return True
        if code == 0xCC:
            return self.read(1)[0]
        if code == 0xCD:
            return struct.unpack(">H", self.read(2))[0]
        if code == 0xCE:
            return struct.unpack(">I", self.read(4))[0]
        if code == 0xCF:
            return struct.unpack(">Q", self.read(8))[0]
        if code == 0xD0:
            return struct.unpack(">b", self.read(1))[0]
        if code == 0xD1:
            return struct.unpack(">h", self.read(2))[0]
        if code == 0xD2:
            return struct.unpack(">i", self.read(4))[0]
        if code == 0xD3:
            return struct.unpack(">q", self.read(8))[0]
        if code in {0xD4, 0xD5, 0xD6, 0xD7, 0xD8}:
            return self.extension({0xD4: 1, 0xD5: 2, 0xD6: 4, 0xD7: 8, 0xD8: 16}[code])
        if code == 0xD9:
            return self.read(self.read(1)[0]).decode("utf-8")
        if code == 0xDA:
            return self.read(struct.unpack(">H", self.read(2))[0]).decode("utf-8")
        if code == 0xDB:
            return self.read(struct.unpack(">I", self.read(4))[0]).decode("utf-8")
        if code == 0xDC:
            return [self.decode() for _ in range(struct.unpack(">H", self.read(2))[0])]
        if code == 0xDD:
            return [self.decode() for _ in range(struct.unpack(">I", self.read(4))[0])]
        if code == 0xDE:
            return {self.decode(): self.decode() for _ in range(struct.unpack(">H", self.read(2))[0])}
        if code == 0xDF:
            return {self.decode(): self.decode() for _ in range(struct.unpack(">I", self.read(4))[0])}
        raise ValueError(f"Unsupported MessagePack byte 0x{code:02x}")


def canonical_team(name: str, countries: dict[str, dict[str, Any]]) -> str:
    country = countries.get(normalize_name(name))
    return country["fifa_code"] if country else normalize_name(name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Downloaded Forza tournament matches file")
    args = parser.parse_args()

    decoded = MessagePackDecoder(args.source.read_bytes()).decode()
    forza_matches = decoded["matches"]
    source = load_json(DATA_DIR / "worldcup.json")
    validate_worldcup(source)
    countries = country_index(load_json(DATA_DIR.parent / "countries.json"))

    by_kickoff: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for match in forza_matches:
        by_kickoff[match["local_kickoff_at"][:16]].append(match)

    output = {}
    used_ids: set[int] = set()
    for sequence, match in enumerate(source["matches"], start=1):
        local_key = f"{match['date']}T{match['time'][:5]}"
        candidates = [item for item in by_kickoff[local_key] if item["id"] not in used_ids]
        expected = (
            canonical_team(match["team1"], countries),
            canonical_team(match["team2"], countries),
        )
        exact = [
            item
            for item in candidates
            if (
                canonical_team(item["home_team"]["name"], countries),
                canonical_team(item["away_team"]["name"], countries),
            )
            == expected
        ]
        if len(exact) == 1:
            selected = exact[0]
            method = "teams_local_kickoff"
        elif len(candidates) == 1:
            selected = candidates[0]
            method = "local_kickoff"
        else:
            raise ValueError(
                f"Could not uniquely match {match_key(sequence)}: "
                f"{match['team1']} v {match['team2']} at {local_key}; "
                f"candidate IDs={[item['id'] for item in candidates]}"
            )
        used_ids.add(selected["id"])
        output[match_key(sequence)] = {
            "forza_match_id": selected["id"],
            "matched_by": method,
        }

    if len(output) != len(source["matches"]):
        raise ValueError("Forza mapping is incomplete")
    write_json(DATA_DIR / "worldcup.forza.json", output)
    print(f"Mapped {len(output)} Forza match IDs")


if __name__ == "__main__":
    main()

