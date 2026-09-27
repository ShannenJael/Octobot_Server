import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from market_radar.ai_training import HistoricalTrainingService
from market_radar.crypto_com_ai import CryptoComAIEngine


class FakeExchange:
    def __init__(self):
        start = 1704067200000  # 2024-01-01T00:00:00Z
        self.rows = []
        for index in range(72):
            open_price = 100.0 + index
            self.rows.append([
                start + index * 3600000,
                open_price,
                open_price + 2.0,
                open_price - 1.0,
                open_price + 1.0,
                1000.0 + index * 10,
            ])

    @staticmethod
    def parse_timeframe(timeframe):
        return {"1h": 3600}[timeframe]

    def fetch_ohlcv(self, symbol, timeframe, since, limit):
        self.last_symbol = symbol
        return [row for row in self.rows if row[0] >= since][:limit]


class HistoricalTrainingTests(unittest.TestCase):
    def test_training_builds_persistent_prompt_context(self):
        with tempfile.TemporaryDirectory() as directory:
            exchange = FakeExchange()
            service = HistoricalTrainingService(
                Path(directory), exchange_factory=lambda: exchange
            )

            profile = service.train(
                "2024-01-01", "2024-01-03", ["BTC_USDT"], timeframe="1h"
            )

            self.assertEqual(profile["status"], "ready")
            self.assertEqual(profile["total_candles"], 72)
            self.assertEqual(profile["instruments"]["BTC_USDT"]["regime"], "bullish")
            self.assertEqual(exchange.last_symbol, "BTC/USDT")
            self.assertTrue(service.profile_path.exists())

            context = HistoricalTrainingService.load_context(
                Path(directory), "BTC_USDT"
            )
            self.assertEqual(context["source"], "historical_training_profile")
            self.assertEqual(context["candle_count"], 72)
            self.assertNotIn("fast_sma", context)

    def test_ai_market_context_loads_matching_training_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            service = HistoricalTrainingService(
                Path(directory), exchange_factory=FakeExchange
            )
            service.train("2024-01-01", "2024-01-03", ["BTC_USDT"], "1h")

            with mock.patch.dict(
                os.environ, {"MARKET_RADAR_DATA_DIR": directory}, clear=False
            ):
                context = CryptoComAIEngine()._get_market_context("BTC_USDT")

            self.assertEqual(
                context["historical_training"]["regime"], "bullish"
            )

    def test_training_rejects_invalid_range_and_instrument(self):
        service = HistoricalTrainingService(exchange_factory=FakeExchange)
        with self.assertRaisesRegex(ValueError, "end_date"):
            service.train("2024-02-01", "2024-01-01", ["BTC_USDT"], "1h")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            service.train("2024-01-01", "2024-01-03", ["BTC_USD"], "1h")


if __name__ == "__main__":
    unittest.main()
