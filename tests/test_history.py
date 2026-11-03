"""Historical calendar attribution and corrections, independent of HA."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

package = types.ModuleType("history_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/stavy_meridel")]
sys.modules[package.__name__] = package
h = importlib.import_module("history_test.history")


class HistoryTests(unittest.TestCase):
    def item(self, months, kind=4, unit="m³"):
        return {"months": months, "kind": kind, "unit": unit}

    def test_first_unknown_month_is_not_whole_meter_lifetime(self):
        self.assertEqual(h.monthly_consumption(self.item({"2026-09": 100, "2026-10": 106})),
                         {"2026-10": 6})

    def test_gap_does_not_shift_two_months_to_later_month(self):
        self.assertEqual(h.monthly_consumption(self.item({"2026-07": 10, "2026-09": 20,
                                                       "2026-10": 23})), {"2026-10": 3})

    def test_january_heat_reset(self):
        self.assertEqual(h.monthly_consumption(self.item({"2025-12": 150, "2026-01": 20,
                                                       "2026-02": 50}, 19, "dílky")),
                         {"2026-01": 20, "2026-02": 30})

    def test_january_water_does_not_reset(self):
        self.assertEqual(h.monthly_consumption(self.item({"2025-12": 150, "2026-01": 155})),
                         {"2026-01": 5})

    def test_water_decrease_not_counted_as_reset(self):
        self.assertEqual(h.monthly_consumption(self.item({"2026-09": 50, "2026-10": 2})), {})

    def test_energy_heat_meter_does_not_reset(self):
        self.assertEqual(h.monthly_consumption(self.item({"2025-12": 150, "2026-01": 155},
                                                       19, "GJ")), {"2026-01": 5})

    def test_rollover_archive_and_correction(self):
        archive = {"x": self.item({"2025-12": 100, "2026-01": 105})}
        incoming = {"x": self.item({"2026-01": 106, "2027-01": 200})}
        h.merge_history(archive, incoming)
        self.assertEqual(archive["x"]["months"]["2025-12"], 100)
        self.assertEqual(archive["x"]["months"]["2026-01"], 106)

    def test_temporarily_missing_reading_preserves_archived_value(self):
        archive = {"x": self.item({"2026-01": 105})}
        h.merge_history(archive, {"x": self.item({"2026-01": None})})
        self.assertEqual(archive["x"]["months"]["2026-01"], 105)

    def test_month_bucket_and_zero_baseline(self):
        rows = h.statistics_rows({"2026-01": 5, "2026-02": 7}, ZoneInfo("Europe/Prague"),
                                 datetime(2026, 11, 3, tzinfo=timezone.utc))
        self.assertEqual([r["sum"] for r in rows], [0, 5, 12])
        self.assertEqual(rows[1]["start"], datetime(2025, 12, 31, 23, tzinfo=timezone.utc))
        self.assertEqual(rows[1]["start"].astimezone(ZoneInfo("Europe/Prague")).month, 1)

    def test_current_month_correction_reuses_same_timestamp(self):
        now = datetime(2026, 11, 3, tzinfo=timezone.utc)
        a = h.statistics_rows({"2026-10": 5, "2026-11": 1}, timezone.utc, now)
        b = h.statistics_rows({"2026-10": 5, "2026-11": 2}, timezone.utc, now)
        self.assertEqual([r["start"] for r in a], [r["start"] for r in b])
        self.assertEqual(b[-1]["sum"], 7)

    def test_open_hour_and_future_month_not_imported(self):
        rows = h.statistics_rows({"2026-11": 2, "2026-12": 4}, timezone.utc,
                                 datetime(2026, 11, 1, 0, 30, tzinfo=timezone.utc))
        self.assertEqual(rows, [])

    def test_id_stable_and_valid(self):
        self.assertEqual(h.statistic_id("0000000000", "4_123456"),
                         "stavy_meridel:byt_0000000000_4_123456")

    def test_counter_correction_decrease_requires_inspection(self):
        self.assertEqual(h.history_issue(self.item({"2026-09": 50, "2026-10": 2})),
                         "counter_decreased")
        self.assertIsNone(h.history_issue(self.item({"2025-12": 50, "2026-01": 2},
                                                  19, "dílky")))

    def test_summer_timezone_stays_in_correct_calendar_month(self):
        tz = ZoneInfo("Europe/Prague")
        rows = h.statistics_rows({"2026-03": 5, "2026-04": 6}, tz,
                                 datetime(2026, 11, 3, tzinfo=timezone.utc))
        self.assertEqual(rows[1]["start"].astimezone(tz).month, 3)
        self.assertEqual(rows[2]["start"], datetime(2026, 3, 31, 22, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
