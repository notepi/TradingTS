import unittest

from cli.utils import normalize_ticker_symbol
from tradingagents.dataflows.a_share_symbols import normalize_a_share_symbol
from tradingagents.agents.utils.agent_utils import build_instrument_context


class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_accepts_bare_mainland_code(self):
        self.assertEqual(normalize_ticker_symbol("600519"), "600519.SH")

    def test_normalize_ticker_symbol_converts_ss_to_sh(self):
        self.assertEqual(normalize_ticker_symbol("688333.ss"), "688333.SH")

    def test_normalize_ticker_symbol_accepts_sz_suffix(self):
        self.assertEqual(normalize_ticker_symbol("000001.sz"), "000001.SZ")

    def test_normalize_ticker_symbol_rejects_non_a_share_symbols(self):
        for symbol in ("NVDA", "SPY", "0700.HK", "7203.T"):
            with self.subTest(symbol=symbol):
                with self.assertRaises(ValueError):
                    normalize_ticker_symbol(symbol)

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context("600519.SH")
        self.assertIn("600519.SH", context)
        self.assertIn("exchange suffix", context)

    def test_shared_normalizer_matches_cli_behavior(self):
        self.assertEqual(normalize_a_share_symbol("688333.SS"), "688333.SH")


if __name__ == "__main__":
    unittest.main()
