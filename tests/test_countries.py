from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import country_index, load_json, normalize_name  # noqa: E402


class CountryDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.countries = load_json(ROOT / "data" / "countries.json")
        cls.index = country_index(cls.countries)

    def test_expected_membership(self) -> None:
        current = [item for item in self.countries if item["status"] == "current"]
        historical = [item for item in self.countries if item["status"] == "historical"]
        self.assertEqual(len(current), 211)
        self.assertEqual(len(historical), 8)
        self.assertEqual(len({item["fifa_code"] for item in self.countries}), 219)

    def test_historical_world_cup_codes(self) -> None:
        expected = {"FRG", "GDR", "INH", "SCG", "TCH", "URS", "YUG", "ZAI"}
        actual = {
            item["fifa_code"]
            for item in self.countries
            if item["status"] == "historical"
        }
        self.assertEqual(actual, expected)

    def test_football_aliases(self) -> None:
        expectations = {
            "Cabo Verde": "CPV",
            "Congo DR": "COD",
            "Côte d'Ivoire": "CIV",
            "Czechia": "CZE",
            "DPR Korea": "PRK",
            "IR Iran": "IRN",
            "Korea Republic": "KOR",
            "Türkiye": "TUR",
            "United States": "USA",
            "USSR": "URS",
        }
        for name, code in expectations.items():
            self.assertEqual(self.index[normalize_name(name)]["fifa_code"], code)

    def test_subdivision_flags(self) -> None:
        for code in ("ENG", "SCO", "WAL"):
            country = next(item for item in self.countries if item["fifa_code"] == code)
            self.assertTrue(country["flag_icon"].startswith("🏴"))
            self.assertTrue(country["iso"].startswith("GB-"))

    def test_no_invented_historical_emoji(self) -> None:
        for country in self.countries:
            if country["status"] == "historical":
                self.assertEqual(country["flag_icon"], "")
                self.assertEqual(country["flag_unicode"], "")


if __name__ == "__main__":
    unittest.main()
