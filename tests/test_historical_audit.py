from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_historical_tournaments import (  # noqa: E402
    AUDIT_RESOLUTIONS,
    DATE_RESOLUTIONS,
    classify,
    identity,
    fifa_team_codes,
    parse_openfootball_time,
    parse_rsssf_records,
    rsssf_team_codes,
)
from historical_config import WORLD_CUP_YEARS, historical_years  # noqa: E402
from common import normalize_name  # noqa: E402


class HistoricalAuditTests(unittest.TestCase):
    def test_tournament_allowlist_excludes_club_world_cup(self) -> None:
        self.assertNotIn(2025, WORLD_CUP_YEARS)
        self.assertNotIn(2025, historical_years())
        self.assertIn(2022, historical_years())

    def test_openfootball_time_with_and_without_offset(self) -> None:
        self.assertEqual(parse_openfootball_time("16:00"), ("16:00", None))
        self.assertEqual(parse_openfootball_time("17:00 UTC+2"), ("17:00", "+2"))

    def test_modern_authoritative_single_source_is_accepted(self) -> None:
        self.assertEqual(
            classify(
                2006,
                {"rsssf": None, "fifa_archive": "18:00", "openfootball": None},
            ),
            ("accepted-modern-source", "18:00"),
        )
        self.assertEqual(
            classify(
                1998,
                {"rsssf": "18:00", "fifa_archive": None, "openfootball": None},
            ),
            ("single-source", "18:00"),
        )

    def test_rsssf_germany_code_is_tournament_aware(self) -> None:
        source = "17.06.54 (18.00)\nGER - TUR 4-1\n"
        records = parse_rsssf_records(source, 1954, {"GER": "Germany", "TUR": "Turkey"})
        key = (
            "1954-06-17",
            frozenset((normalize_name("West Germany"), normalize_name("Turkey"))),
        )
        self.assertIn(key, records)

    def test_source_team_names_share_stable_identities(self) -> None:
        self.assertEqual(
            identity("2002-06-05", "USA", "Portugal"),
            identity("2002-06-05", "United States", "Portugal"),
        )

    def test_rsssf_codes_cannot_override_official_fifa_codes(self) -> None:
        self.assertEqual(fifa_team_codes()["CAM"], "Cambodia")
        self.assertEqual(rsssf_team_codes()["CAM"], "Cameroon")
        self.assertEqual(
            identity("2006-06-10", "Côte d'Ivoire", "Argentina"),
            identity("2006-06-10", "Ivory Coast", "Argentina"),
        )

    def test_1990_england_netherlands_resolution_uses_scheduled_time(self) -> None:
        resolution = AUDIT_RESOLUTIONS[
            identity("1990-06-16", "England", "Netherlands")
        ]
        self.assertEqual(resolution["time"], "21:00")

    def test_1990_ireland_egypt_resolution_uses_scheduled_time(self) -> None:
        resolution = AUDIT_RESOLUTIONS[
            identity("1990-06-17", "Republic of Ireland", "Egypt")
        ]
        self.assertEqual(resolution["time"], "17:00")

    def test_known_rsssf_date_typos_are_resolved(self) -> None:
        self.assertIn(
            identity("1990-07-07", "Italy", "England"), DATE_RESOLUTIONS
        )


if __name__ == "__main__":
    unittest.main()
