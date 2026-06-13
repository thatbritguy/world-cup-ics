from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import country_index, load_json, normalize_name  # noqa: E402
from generate_master_calendar import validated_years  # noqa: E402


class HistoricalCalendarTests(unittest.TestCase):
    def test_rsssf_is_the_historical_kickoff_baseline(self) -> None:
        for year in (1930, 1934, 1938):
            enrichment = load_json(
                ROOT / "data" / str(year) / "worldcup.enrichment.json"
            )["matches"]
            for match in enrichment:
                sources = match["local_time_sources"]
                if sources["selected"] == "RSSSF full tournament record":
                    self.assertEqual(match["local_time"], sources["rsssf"])

        enrichment_1934 = load_json(
            ROOT / "data" / "1934" / "worldcup.enrichment.json"
        )["matches"]
        fallbacks = [
            match
            for match in enrichment_1934
            if match["local_time_sources"]["rsssf"] is None
        ]
        self.assertEqual(len(fallbacks), 3)
        self.assertTrue(
            all(
                match["local_time_sources"]["selected"].startswith("Archived FIFA")
                for match in fallbacks
            )
        )

    def test_1930_manifest_is_chronological_and_stable(self) -> None:
        manifest = load_json(ROOT / "data" / "1930" / "worldcup.manifest.json")
        self.assertEqual(len(manifest["matches"]), 18)
        self.assertEqual(manifest["matches"][0]["uid"], "wc1930-match-001@world-cup-ics")
        self.assertEqual(manifest["matches"][0]["team1"], "France")
        self.assertEqual(manifest["matches"][-1]["uid"], "wc1930-match-018@world-cup-ics")
        self.assertEqual(manifest["matches"][-1]["team1"], "Uruguay")
        self.assertEqual(manifest["status"], "validated")
        self.assertEqual(manifest["calendar_profile"], "archive")
        self.assertEqual(
            [item["official_match_number"] for item in manifest["matches"]],
            list(range(1, 19)),
        )

    def test_disputed_kickoffs_use_local_time_and_historical_timezone(self) -> None:
        enrichment = load_json(
            ROOT / "data" / "1930" / "worldcup.enrichment.json"
        )["matches"]
        semi_final = next(
            match
            for match in enrichment
            if match["team1"] == "Uruguay" and match["team2"] == "Yugoslavia"
        )
        final = next(
            match
            for match in enrichment
            if match["team1"] == "Uruguay" and match["team2"] == "Argentina"
        )
        self.assertEqual(semi_final["local_time"], "14:45")
        self.assertEqual(semi_final["kickoff_utc"], "1930-07-27T18:15:00Z")
        self.assertEqual(final["local_time"], "15:30")
        self.assertEqual(final["kickoff_utc"], "1930-07-30T19:00:00Z")
        self.assertEqual(final["timezone"], "America/Montevideo")
        self.assertEqual(final["utc_offset"], "-03:30")
        self.assertEqual(final["local_time_sources"]["fifa_archive"], "14:15")
        self.assertEqual(final["local_time_sources"]["wikipedia"], "12:45")
        self.assertEqual(final["local_time_sources"]["rsssf"], "15:30")

    def test_1934_uses_fifa_numbering_and_historical_rome_time(self) -> None:
        manifest = load_json(ROOT / "data" / "1934" / "worldcup.manifest.json")
        enrichment = load_json(
            ROOT / "data" / "1934" / "worldcup.enrichment.json"
        )["matches"]
        self.assertEqual(len(manifest["matches"]), 17)
        self.assertEqual(
            [item["official_match_number"] for item in manifest["matches"]],
            list(range(1, 18)),
        )
        final = next(item for item in enrichment if item["official_match_number"] == 17)
        self.assertEqual(final["local_time"], "17:00")
        self.assertEqual(final["timezone"], "Europe/Rome")
        self.assertEqual(final["utc_offset"], "+01:00")
        self.assertEqual(final["kickoff_utc"], "1934-06-10T16:00:00Z")
        self.assertEqual(final["local_time_sources"]["fifa_archive"], "17:30")
        self.assertEqual(final["local_time_sources"]["wikipedia"], "15:30")
        self.assertEqual(final["local_time_sources"]["rsssf"], "17:00")
        self.assertNotEqual(final["kickoff_utc"], final["fifa_derived_utc"])
        third_place = next(
            item for item in enrichment if item["official_match_number"] == 16
        )
        self.assertEqual(third_place["local_time"], "17:30")
        self.assertEqual(third_place["kickoff_utc"], "1934-06-07T16:30:00Z")

    def test_master_includes_only_validated_archive_tournaments(self) -> None:
        self.assertEqual(validated_years(), [1930, 1934])
        master = (ROOT / "ics" / "world-cup.ics").read_text(encoding="utf-8")
        self.assertEqual(master.count("BEGIN:VEVENT"), 35)
        self.assertIn("UID:wc1930-match-001@world-cup-ics", master)
        self.assertIn("UID:wc1934-match-017@world-cup-ics", master)
        self.assertNotIn("UID:wc2026-match-001@world-cup-ics", master)

    def test_1938_draft_excludes_cancelled_fixture(self) -> None:
        manifest = load_json(ROOT / "data" / "1938" / "worldcup.manifest.json")
        enrichment = load_json(
            ROOT / "data" / "1938" / "worldcup.enrichment.json"
        )["matches"]
        self.assertEqual(manifest["status"], "review")
        self.assertEqual(len(manifest["matches"]), 18)
        self.assertEqual(len(enrichment), 18)
        self.assertNotIn("Austria", {item["team2"] for item in manifest["matches"]})
        disputed = next(
            item for item in enrichment if item["official_match_number"] == 1
        )
        self.assertEqual(disputed["local_time"], "18:00")
        self.assertEqual(disputed["local_time_sources"]["confidence"], "provisional")

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
