"""Tariff boundaries, unknown prices and fair year-to-year comparison."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from datetime import date

package = types.ModuleType("billing_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/stavy_meridel")]
sys.modules[package.__name__] = package
b = importlib.import_module("billing_test.billing")


class BillingTests(unittest.TestCase):
    def item(self, months):
        return {"kind": 4, "unit": "m³", "months": months}

    def test_price_changes_apply_from_correct_month(self):
        tariffs = [{"kind": 4, "from": "2025-01", "price": 100},
                   {"kind": 4, "from": "2026-02", "price": 120}]
        item = self.item({"2025-12": 10, "2026-01": 12, "2026-02": 15})
        self.assertEqual(b.monthly_costs(item, tariffs), {"2026-01": 200, "2026-02": 360})

    def test_no_price_is_not_zero_cost(self):
        item = self.item({"2026-01": 10, "2026-02": 12})
        self.assertEqual(b.monthly_costs(item, []), {})

    def test_price_not_applied_retroactively_or_to_other_water_type(self):
        tariffs = [{"kind": 2, "from": "2025-01", "price": 300},
                   {"kind": 4, "from": "2026-03", "price": 100}]
        self.assertIsNone(b.price_for_month(tariffs, 4, "2026-02"))
        self.assertEqual(b.price_for_month(tariffs, 2, "2026-02"), 300)

    def test_explicit_zero_price_is_valid(self):
        self.assertEqual(b.monthly_costs(self.item({"2026-01": 10, "2026-02": 12}),
                         [{"kind": 4, "from": "2026-01", "price": 0}]), {"2026-02": 0})

    def test_edit_price_keeps_older_tariff(self):
        tariffs = b.set_tariff([], 4, "2025-01", 100)
        tariffs = b.set_tariff(tariffs, 4, "2026-01", 110)
        tariffs = b.set_tariff(tariffs, 4, "2026-01", 120)
        self.assertEqual(len(tariffs), 2)
        self.assertEqual(b.price_for_month(tariffs, 4, "2025-06"), 100)
        self.assertEqual(b.price_for_month(tariffs, 4, "2026-06"), 120)

    def test_comparison_uses_completed_matching_months(self):
        item = self.item({"2024-12": 10, "2025-01": 12, "2025-02": 16,
                          "2025-03": 20, "2025-12": 40, "2026-01": 43,
                          "2026-02": 49, "2026-03": 50})
        compared = b.compare_years(item, date(2026, 3, 3))
        self.assertEqual(compared, {"current": 9, "previous": 6, "percent": 50,
                                    "months": [1, 2], "complete": True})

    def test_missing_comparison_is_not_zero(self):
        compared = b.compare_years(self.item({"2026-01": 1, "2026-02": 2}), date(2026, 3, 3))
        self.assertIsNone(compared["previous"])
        self.assertIsNone(compared["percent"])

    def test_zero_previous_year_has_no_infinite_percent(self):
        item = self.item({"2024-12": 10, "2025-01": 10, "2025-12": 20, "2026-01": 21})
        compared = b.compare_years(item, date(2026, 2, 3))
        self.assertEqual(compared["previous"], 0)
        self.assertIsNone(compared["percent"])

    def test_partial_coverage_is_marked(self):
        item = self.item({"2024-12": 10, "2025-01": 12, "2025-12": 20,
                          "2026-01": 23, "2026-02": 25})
        compared = b.compare_years(item, date(2026, 3, 3))
        self.assertEqual(compared["months"], [1])
        self.assertFalse(compared["complete"])

    def test_invalid_price_not_saved_as_free_or_infinite_cost(self):
        for price in (-1, float("nan"), float("inf"), True):
            with self.subTest(price=price), self.assertRaises(ValueError):
                b.set_tariff([], 4, "2026-01", price)

    def test_visible_price_edit_respects_selected_month_and_keeps_history(self):
        options = {"history_years": 3, "price_editor_date": "2025-01-01",
                   "tariffs": [{"kind": 4, "from": "2026-01", "price": 150}]}
        updated = b.price_control_options(options, 4, 100, date(2026, 11, 3), "CZK")
        self.assertEqual(updated["history_years"], 3)
        self.assertEqual(b.price_for_month(updated["tariffs"], 4, "2025-06"), 100)
        self.assertEqual(b.price_for_month(updated["tariffs"], 4, "2026-06"), 150)
        self.assertEqual(updated["tariff_currency"], "CZK")

    def test_date_control_alone_does_not_create_prices(self):
        self.assertEqual(b.editor_date({}, date(2026, 11, 3)), date(2026, 11, 1))
        with self.assertRaises(ValueError):
            b.editor_date({"price_editor_date": "2026-11-03"}, date(2026, 11, 3))

    def test_price_control_keeps_original_currency(self):
        result = b.price_control_options({"tariff_currency": "CZK"}, 4, 100,
                                         date(2026, 11, 3), "EUR")
        self.assertEqual(result["tariff_currency"], "CZK")


if __name__ == "__main__":
    unittest.main()
