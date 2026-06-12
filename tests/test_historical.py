from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import country_index, load_json, normalize_name  # noqa: E402


class HistoricalCalendarTests(unittest.TestCase):
    def test_1930_manifest_is_chronological_and_stable(self) -> None:
        manifest = load_json(ROOT / "data" / "1930" / "manifest.json")
        self.assertEqual(len(manifest["matches"]), 18)
        self.assertEqual(manifest["matches"][0]["uid"], "wc1930-match-001@world-cup-ics")
        self.assertEqual(manifest["matches"][0]["team1"], "France")
        self.assertEqual(manifest["matches"][-1]["uid"], "wc1930-match-018@world-cup-ics")
        self.assertEqual(manifest["matches"][-1]["team1"], "Uruguay")

    def test_master_countries_cover_1930(self) -> None:
        countries = country_index(load_json(ROOT / "data" / "countries.json"))
        source = load_json(ROOT / "data" / "1930" / "worldcup.json")
        missing = {
            team
            for match in source["matches"]
            for team in (match["team1"], match["team2"])
            if normalize_name(team) not in countries
        }
        self.assertEqual(missing, set())
        self.assertEqual(countries[normalize_name("Kingdom of Yugoslavia")]["fifa_code"], "YUG")


if __name__ == "__main__":
    unittest.main()
