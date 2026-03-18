import unittest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from build_oe_screener import (
    calc_oe_yield,
    calc_blended_growth,
    calc_expected_return,
    filter_usd_only,
    build_output_entry,
    fetch_price,
    _parse_fmp_response,
)


class TestCalcOeYield(unittest.TestCase):
    def test_basic(self):
        self.assertAlmostEqual(calc_oe_yield(20, 400), 5.0)

    def test_zero_price(self):
        self.assertIsNone(calc_oe_yield(20, 0))


class TestCalcBlendedGrowth(unittest.TestCase):
    def test_basic(self):
        result = calc_blended_growth(8, 3.5, phase1_years=10, total_years=30)
        self.assertAlmostEqual(result, 5.0)

    def test_equal_rates(self):
        result = calc_blended_growth(5, 5, phase1_years=10, total_years=30)
        self.assertAlmostEqual(result, 5.0)


class TestCalcExpectedReturn(unittest.TestCase):
    def test_basic(self):
        self.assertAlmostEqual(calc_expected_return(5.0, 5.0), 10.0)


class TestSkipsNonUsd(unittest.TestCase):
    def test_filters_currency_entries(self):
        entries = [
            {"ticker": "MSFT", "oePerShare": 6.28, "g1": 10, "g2": 3.5},
            {"ticker": "8031.T", "oePerShare": 335, "g1": 3, "g2": 3, "currency": "JPY"},
        ]
        result = filter_usd_only(entries)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ticker"], "MSFT")

    def test_keeps_all_usd(self):
        entries = [
            {"ticker": "MSFT"},
            {"ticker": "GOOG"},
        ]
        self.assertEqual(len(filter_usd_only(entries)), 2)


class TestBuildOutputEntry(unittest.TestCase):
    def test_all_fields(self):
        estimate = {
            "ticker": "CB",
            "company": "Chubb Ltd",
            "businessType": "Insurance",
            "oePerShare": 21.66,
            "g1": 7.0,
            "g2": 3.5,
            "durability": "HIGH",
            "estimateDate": "2026-03-13",
            "notes": "Test note",
        }
        price = 280.0
        entry = build_output_entry(estimate, price)
        self.assertEqual(entry["ticker"], "CB")
        self.assertEqual(entry["company"], "Chubb Ltd")
        self.assertEqual(entry["businessType"], "Insurance")
        self.assertEqual(entry["oePerShare"], 21.66)
        self.assertEqual(entry["currentPrice"], 280.0)
        self.assertAlmostEqual(entry["oeYield"], round(21.66 / 280.0 * 100, 2))
        self.assertEqual(entry["g1"], 7.0)
        self.assertEqual(entry["g2"], 3.5)
        expected_blended = (10 * 7.0 + 20 * 3.5) / 30
        self.assertAlmostEqual(entry["blendedGrowth"], round(expected_blended, 2))
        self.assertAlmostEqual(entry["expectedReturn"], round(21.66 / 280.0 * 100 + expected_blended, 2))
        self.assertEqual(entry["durability"], "HIGH")
        self.assertEqual(entry["estimateDate"], "2026-03-13")
        self.assertEqual(entry["notes"], "Test note")


class TestMultiCurrency(unittest.TestCase):
    """Tests for multi-currency support — all currencies in one table."""

    def test_filter_all_includes_all_entries(self):
        """filter_all should return every entry regardless of currency."""
        entries = [
            {"ticker": "MSFT", "oePerShare": 6.28, "g1": 10, "g2": 3.5},
            {"ticker": "8031.T", "oePerShare": 335, "g1": 3, "g2": 3, "currency": "JPY"},
            {"ticker": "JDG.L", "oePerShare": 266, "g1": 8, "g2": 3.5, "currency": "GBp"},
        ]
        from build_oe_screener import filter_all
        result = filter_all(entries)
        self.assertEqual(len(result), 3)

    def test_build_output_entry_includes_currency(self):
        """Output entry should include currency field, defaulting to USD."""
        estimate = {
            "ticker": "CB", "company": "Chubb", "businessType": "Insurance",
            "oePerShare": 21.66, "g1": 7.0, "g2": 3.5,
            "durability": "HIGH", "estimateDate": "2026-03-13",
        }
        entry = build_output_entry(estimate, 280.0)
        self.assertEqual(entry["currency"], "USD")

    def test_build_output_entry_preserves_currency(self):
        """Output entry should pass through non-USD currency."""
        estimate = {
            "ticker": "JDG.L", "company": "Judges Scientific",
            "businessType": "Serial Acquirer", "oePerShare": 266,
            "g1": 8.0, "g2": 3.5, "durability": "MEDIUM",
            "estimateDate": "2026-03-18", "currency": "GBp",
        }
        entry = build_output_entry(estimate, 3860)
        self.assertEqual(entry["currency"], "GBp")
        self.assertAlmostEqual(entry["oeYield"], round(266 / 3860 * 100, 2))

    def test_currency_symbol_mapping(self):
        """Currency codes should map to display symbols."""
        from build_oe_screener import currency_symbol
        self.assertEqual(currency_symbol("USD"), "$")
        self.assertEqual(currency_symbol("GBp"), "£")
        self.assertEqual(currency_symbol("JPY"), "¥")
        self.assertEqual(currency_symbol("EUR"), "€")
        self.assertEqual(currency_symbol("XYZ"), "XYZ ")  # unknown fallback


class TestHandlesMissingPrice(unittest.TestCase):
    def test_returns_none_for_empty_response(self):
        # Simulate FMP returning empty array
        price = _parse_fmp_response([])
        self.assertIsNone(price)

    def test_returns_none_for_none_response(self):
        price = _parse_fmp_response(None)
        self.assertIsNone(price)

    def test_extracts_price(self):
        price = _parse_fmp_response([{"price": 123.45}])
        self.assertAlmostEqual(price, 123.45)


if __name__ == "__main__":
    unittest.main()
