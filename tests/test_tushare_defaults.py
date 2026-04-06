import unittest

from tradingagents.dataflows.config import get_config, set_config
from tradingagents.dataflows.interface import get_vendor
from tradingagents.dataflows.tushare_data import (
    get_global_news,
    get_insider_transactions,
    get_news,
)
from tradingagents.default_config import DEFAULT_CONFIG


class TushareDefaultsTests(unittest.TestCase):
    def setUp(self):
        set_config(DEFAULT_CONFIG.copy())

    def test_default_data_vendors_match_project_defaults(self):
        config = get_config()
        self.assertEqual(config["data_vendors"]["core_stock_apis"], "tushare")
        self.assertEqual(config["data_vendors"]["technical_indicators"], "tushare")
        self.assertEqual(config["data_vendors"]["fundamental_data"], "tushare")
        self.assertEqual(config["data_vendors"]["news_data"], "tavily")

    def test_vendor_lookup_returns_expected_vendors_for_categories(self):
        expected_vendors = {
            "core_stock_apis": "tushare",
            "technical_indicators": "tushare",
            "fundamental_data": "tushare",
            "news_data": "tavily",
        }
        for category, vendor in expected_vendors.items():
            with self.subTest(category=category):
                self.assertEqual(get_vendor(category), vendor)

    def test_placeholder_tools_return_stable_messages(self):
        news = get_news("600519.SH", "2025-04-01", "2025-04-02")
        self.assertIn("not available via Tushare citydata mode", news)

        global_news = get_global_news("2025-04-02", 7, 5)
        self.assertIn("Global market news is not available", global_news)

        insider = get_insider_transactions("000001.SZ")
        self.assertIn("not available via Tushare citydata mode", insider)


if __name__ == "__main__":
    unittest.main()
