#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from typing import Any

from audit_historical_tournaments import identity, rsssf_team_codes
from common import ROOT, load_json, normalize_name, write_json


def goal(name: str, minute: str, flag: str = "") -> dict[str, Any]:
    minute_match = re.fullmatch(r"(\d+)(?:\+(\d+))?", minute.rstrip("'"))
    if not minute_match:
        raise ValueError(f"Unsupported goal minute: {minute}")
    item: dict[str, Any] = {"name": name.strip(), "minute": int(minute_match.group(1))}
    if minute_match.group(2):
        item["offset"] = int(minute_match.group(2))
    if flag.casefold() in ("p", "pen"):
        item["penalty"] = True
    if flag.casefold() in ("o", "og"):
        item["owngoal"] = True
    return item


def legacy_records(text: str, year: int) -> dict[tuple[str, frozenset[str]], dict[str, Any]]:
    codes = rsssf_team_codes()
    if 1954 <= year <= 1990:
        codes["GER"] = "West Germany"
    if year <= 1990:
        codes["CZE"] = "Czechoslovakia"
    lines = text.splitlines()
    output: dict[tuple[str, frozenset[str]], dict[str, Any]] = {}
    date_re = re.compile(r"^(\d{2})\.(\d{2})\.(\d{2})")
    score_re = re.compile(r"^([A-Z]{3}) - ([A-Z]{3}) (\d+):(\d+) \(([^)]*)\)", re.I)
    event_re = re.compile(
        r"(?:^|,\s*)(\d+):(\d+)\s+(.+?)\s+(\d+(?:\+\d+)?)\s*([pohf]?)"
    )
    for index, line in enumerate(lines):
        date = date_re.match(line)
        if not date:
            continue
        score_index = next(
            (i for i in range(index + 1, min(index + 10, len(lines))) if score_re.match(lines[i])),
            None,
        )
        if score_index is None:
            continue
        parsed = score_re.match(lines[score_index])
        assert parsed
        team1, team2, final_home, final_away, intervals = parsed.groups()
        if team1.upper() not in codes or team2.upper() not in codes:
            continue
        scores = re.findall(r"(\d+):(\d+)", intervals)
        record: dict[str, Any] = {
            "source": "rsssf-full",
            "team1": codes[team1.upper()],
            "team2": codes[team2.upper()],
        }
        if scores:
            record["ht"] = [int(value) for value in scores[0]]
        scorer_lines: list[str] = []
        for candidate in lines[score_index + 1 :]:
            if date_re.match(candidate):
                break
            if event_re.search(candidate) or (scorer_lines and candidate and not re.match(r"^[A-Z]{3}:", candidate)):
                scorer_lines.append(candidate.strip())
            elif scorer_lines:
                break
        goals1: list[dict[str, Any]] = []
        goals2: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []
        previous = (0, 0)
        for event in event_re.finditer(" ".join(scorer_lines)):
            current = (int(event.group(1)), int(event.group(2)))
            item = goal(event.group(3), event.group(4), event.group(5))
            if current[0] > previous[0]:
                goals1.append(item)
            elif current[1] > previous[1]:
                goals2.append(item)
            else:
                ambiguous.append(item)
            previous = current
        for item in ambiguous:
            if len(goals1) < int(final_home):
                goals1.append(item)
            elif len(goals2) < int(final_away):
                goals2.append(item)
        record["goals1"], record["goals2"] = goals1, goals2
        day, month, short_year = date.groups()
        key = identity(f"{1900 + int(short_year):04d}-{month}-{day}", codes[team1.upper()], codes[team2.upper()])
        output[key] = record
    return output


def grouped_goals(value: str) -> list[dict[str, Any]]:
    value = re.sub(r"(^|,\s*)\d{1,2}\s+(?=[^\d])", r"\1", value)
    events: list[dict[str, Any]] = []
    last_name = ""
    cursor = 0
    minute_re = re.compile(r"(\d+(?:\+\d+)?)'?\s*(pen|OG)?", re.I)
    for match in minute_re.finditer(value):
        prefix = value[cursor : match.start()].strip(" ,")
        if prefix:
            last_name = re.sub(r"^\d+[- ]", "", prefix).strip()
        if last_name:
            events.append(goal(last_name, match.group(1), match.group(2) or ""))
        cursor = match.end()
    return events


def modern_records(text: str, year: int) -> list[dict[str, Any]]:
    raw_lines = text.splitlines()
    lines: list[str] = []
    for line in raw_lines:
        if lines and line.startswith(" ") and "(" in lines[-1] and lines[-1].count("(") > lines[-1].count(")"):
            lines[-1] += " " + line.strip()
        else:
            lines.append(line)
    output: list[dict[str, Any]] = []
    if year == 2006:
        team_re = re.compile(r"^([A-Z][A-Za-z .&'-]+?) (\d+)\s*(?:\((.*)\))?$")
    else:
        team_re = re.compile(r"^([A-Z][A-Z .&'-]+?)\s{2,}(\d+)\s*(?:\((.*)\))?$")
    for index in range(len(lines) - 1):
        first, second = team_re.match(lines[index]), team_re.match(lines[index + 1])
        if not first or not second:
            continue
        if first.group(1).startswith(("HT", "Att", "World Cup")):
            continue
        record: dict[str, Any] = {
            "team1": first.group(1).strip().title(),
            "team2": second.group(1).strip().title(),
            "goals1": grouped_goals(first.group(3) or ""),
            "goals2": grouped_goals(second.group(3) or ""),
            "source": "rsssf-full",
        }
        nearby = " ".join(lines[index + 2 : index + 5])
        ht = re.search(r"HT:\s*(\d+)-(\d+)", nearby)
        if ht:
            record["ht"] = [int(ht.group(1)), int(ht.group(2))]
        output.append(record)
    return output


def team_key(name: str) -> str:
    aliases = {
        "cotedivoire": "ivorycoast",
        "germanyfr": "westgermany",
        "korearepublic": "southkorea",
        "serbiaandmontenegro": "serbiamontenegro",
        "unitedstates": "usa",
    }
    return aliases.get(normalize_name(name), normalize_name(name))


def pair_key(team1: str, team2: str) -> frozenset[str]:
    return frozenset(team_key(name) for name in (team1, team2))


def valid(record: dict[str, Any], match: dict[str, Any]) -> bool:
    result = match["score"].get("et") or match["score"]["ft"]
    return len(record.get("goals1", [])) == result[0] and len(record.get("goals2", [])) == result[1]


def orient(record: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    if team_key(record["team1"]) == team_key(match["team1"]):
        return record
    swapped = dict(record)
    swapped["team1"], swapped["team2"] = record["team2"], record["team1"]
    swapped["goals1"], swapped["goals2"] = record.get("goals2", []), record.get("goals1", [])
    if record.get("ht") is not None:
        swapped["ht"] = list(reversed(record["ht"]))
    return swapped


def enrich(year: int) -> None:
    path = ROOT / "data" / str(year) / "worldcup.json"
    payload = load_json(path)
    source = ROOT / "data" / "historical-sources" / str(year) / "rsssf-full.txt"
    text = source.read_text(encoding="utf-8") if source.exists() else ""
    legacy = legacy_records(text, year) if text and year <= 1998 else {}
    legacy_pairs: dict[frozenset[str], list[dict[str, Any]]] = defaultdict(list)
    for record in legacy.values():
        legacy_pairs[pair_key(record["team1"], record["team2"])].append(record)
    modern: dict[frozenset[str], list[dict[str, Any]]] = defaultdict(list)
    if text and year >= 2002:
        for record in modern_records(text, year):
            modern[pair_key(record["team1"], record["team2"])].append(record)
    enriched = 0
    for match in payload["matches"]:
        if match.get("goals1") is not None and match.get("goals2") is not None and match["score"].get("ht") is not None:
            continue
        record = legacy.get(identity(match["date"], match["team1"], match["team2"]))
        if record:
            candidates = legacy_pairs[pair_key(match["team1"], match["team2"])]
            if record in candidates:
                candidates.remove(record)
        elif legacy:
            candidates = legacy_pairs.get(pair_key(match["team1"], match["team2"]), [])
            record = next(
                (candidate for candidate in candidates if valid(orient(candidate, match), match)),
                None,
            )
            if record:
                candidates.remove(record)
        if not record and modern:
            candidates = modern.get(pair_key(match["team1"], match["team2"]), [])
            record = candidates.pop(0) if candidates else None
        if not record:
            continue
        record = orient(record, match)
        if record.get("ht") is None and valid(record, match):
            record["ht"] = [
                sum(item["minute"] <= 45 for item in record["goals1"]),
                sum(item["minute"] <= 45 for item in record["goals2"]),
            ]
        if match["score"].get("ht") is None and record.get("ht") is not None:
            match["score"]["ht"] = record["ht"]
        if (not match.get("goals1") and not match.get("goals2")) and valid(record, match):
            match["goals1"], match["goals2"] = record["goals1"], record["goals2"]
        match["result_enrichment"] = {"source": record["source"], "score_reconciled": valid(record, match)}
        enriched += 1
    for match in payload["matches"]:
        result = match["score"].get("et") or match["score"]["ft"]
        goals1, goals2 = match.get("goals1") or [], match.get("goals2") or []
        reconciled = [len(goals1), len(goals2)] == result
        if match["score"].get("ht") is None and reconciled:
            match["score"]["ht"] = [
                sum(item["minute"] <= 45 for item in goals1),
                sum(item["minute"] <= 45 for item in goals2),
            ]
        metadata = match.setdefault(
            "result_enrichment",
            {"source": "openfootball" if reconciled else "none"},
        )
        metadata["score_reconciled"] = reconciled
        missing = []
        if not reconciled:
            missing.append("goalscorers")
        if match["score"].get("ht") is None:
            missing.append("half_time_score")
        if missing:
            metadata["missing_fields"] = missing
        else:
            metadata.pop("missing_fields", None)
    write_json(path, payload)
    print(f"Enriched {year}: {enriched} matches")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("years", nargs="*", type=int)
    args = parser.parse_args()
    for year in args.years or range(1954, 2015, 4):
        if (ROOT / "data" / str(year)).exists():
            enrich(year)


if __name__ == "__main__":
    main()
