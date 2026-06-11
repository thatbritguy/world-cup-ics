from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import country_index, format_geo, load_json  # noqa: E402
from generate_calendar import description, score_summary, team_details  # noqa: E402


class ResultFormattingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.countries = country_index(load_json(ROOT / "data" / "countries.json"))
        cls.mexico = team_details("Mexico", cls.countries)
        cls.south_africa = team_details("South Africa", cls.countries)

    def test_prematch_summary(self) -> None:
        self.assertEqual(
            score_summary({}, self.mexico, self.south_africa),
            "🇲🇽 MEX vs RSA 🇿🇦",
        )

    def test_normal_time_summary(self) -> None:
        match = {"score": {"ft": [2, 0], "ht": [1, 0]}}
        self.assertEqual(
            score_summary(match, self.mexico, self.south_africa),
            "🇲🇽 MEX 2-0 RSA 🇿🇦",
        )

    def test_extra_time_summary(self) -> None:
        match = {"score": {"ft": [0, 0], "et": [1, 0], "ht": [0, 0]}}
        self.assertEqual(
            score_summary(match, self.mexico, self.south_africa),
            "🇲🇽 MEX 1-0 (aet) RSA 🇿🇦",
        )

    def test_penalty_summary_and_description(self) -> None:
        match = {
            "score": {"p": [4, 2], "et": [1, 1], "ft": [0, 0], "ht": [0, 0]},
            "goals1": [{"name": "Mexican Player", "minute": 105, "offset": 1}],
            "goals2": [{"name": "South African Player", "minute": 72}],
        }
        self.assertEqual(
            score_summary(match, self.mexico, self.south_africa),
            "🇲🇽 MEX (p) 1-1 RSA 🇿🇦",
        )
        self.assertEqual(
            description(match, self.mexico, self.south_africa, "ITV1"),
            "Mexico 1-1 South Africa\n"
            "HT: 0-0\n"
            "FT: 0-0\n"
            "AET: 1-1\n"
            "Pens: 4-2\n"
            "Goals:\n"
            "MEX: Mexican Player 105+1'\n"
            "RSA: South African Player 72'\n"
            "TV: ITV1",
        )

    def test_empty_goal_lists_are_omitted(self) -> None:
        match = {
            "score": {"ft": [0, 0], "ht": [0, 0]},
            "goals1": [],
            "goals2": None,
        }
        value = description(match, self.mexico, self.south_africa, None)
        self.assertNotIn("Goals:", value)
        self.assertNotIn("MEX:", value)
        self.assertIn("TV: TBC", value)

    def test_country_aliases(self) -> None:
        self.assertEqual(team_details("Türkiye", self.countries)["code"], "TUR")
        self.assertEqual(team_details("Korea Republic", self.countries)["code"], "KOR")
        self.assertEqual(team_details("Czechia", self.countries)["code"], "CZE")

    def test_dms_coordinates(self) -> None:
        self.assertEqual(
            format_geo('19°18\'11"N 99°09\'02"W'),
            "19.303056;-99.150556",
        )

    def test_decimal_coordinates(self) -> None:
        self.assertEqual(
            format_geo("37.403°N 121.970°W"),
            "37.403000;-121.970000",
        )


if __name__ == "__main__":
    unittest.main()
