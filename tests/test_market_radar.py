import json
import math
import os
import tempfile
import unittest
from pathlib import Path

from market_radar.crypto_com import liquid_usdt_tickers
from market_radar.journal import RadarJournal
from market_radar.scoring import MODEL_VERSION, deterministic_explanation, score_market


def candles(start=100.0, growth=0.001, count=90, step_ms=3_600_000):
    values = []
    price = start
    for index in range(count):
        price *= 1 + growth + math.sin(index / 5) * 0.0003
        values.append({"o": str(price * 0.999), "h": str(price * 1.002), "l": str(price * 0.998), "c": str(price), "v": "100", "t": 1_700_000_000_000 + index * step_ms})
    return values


class ScoringTests(unittest.TestCase):
    def test_score_is_bounded_versioned_and_explainable(self):
        ticker = {"i": "TEST_USDT", "a": "110", "b": "109.9", "k": "110.1", "c": "0.03", "vv": "5000000"}
        result = score_market(ticker, {"1h": candles(), "4h": candles(growth=0.002), "1D": candles(growth=0.003)}, 0.01)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)
        self.assertEqual(result["model_version"], MODEL_VERSION)
        self.assertEqual(len(result["signal_id"]), 20)
        self.assertIn("TEST/USDT", deterministic_explanation(result)["summary"])

    def test_rejects_insufficient_history(self):
        with self.assertRaises(ValueError):
            score_market({"i": "TEST_USDT", "a": 1, "b": 1, "k": 1, "vv": 1}, {"1h": candles(count=20)}, 0)

    def test_universe_filters_derivatives_and_stables(self):
        tickers = [
            {"i": "BTC_USDT", "a": "10", "b": "9.9", "k": "10.1", "vv": "1000"},
            {"i": "ETH_USDT", "a": "10", "b": "9.9", "k": "10.1", "vv": "2000"},
            {"i": "USDC_USDT", "a": "1", "b": ".99", "k": "1.01", "vv": "9999"},
            {"i": "BTCUSD-PERP", "a": "10", "b": "9.9", "k": "10.1", "vv": "9999"},
        ]
        self.assertEqual([item["i"] for item in liquid_usdt_tickers(tickers)], ["ETH_USDT", "BTC_USDT"])


class JournalTests(unittest.TestCase):
    def test_prediction_dedup_outcomes_watchlist_and_disabled_paper(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = RadarJournal(directory)
            prediction = {"signal_id": "abc", "instrument": "BTC_USDT", "last_price": 100, "as_of_ms": 1_700_000_000_000, "model_version": MODEL_VERSION, "score": 70}
            journal.record_prediction(prediction)
            journal.record_prediction(prediction)
            self.assertEqual(len(journal.recent_events()), 1)
            written = journal.resolve_due_outcomes({"BTC_USDT": 110}, now=1_700_000_000 + 80 * 3600)
            self.assertEqual(written, 3)
            self.assertEqual(journal.resolve_due_outcomes({"BTC_USDT": 120}, now=1_700_000_000 + 80 * 3600), 0)
            self.assertEqual(journal.set_watchlist(["BTC_USDT", "bad"]), ["BTC_USDT"])
            old = os.environ.pop("MARKET_RADAR_PAPER_HANDOFF_ENABLED", None)
            try:
                with self.assertRaises(PermissionError):
                    journal.queue_paper_candidate(prediction)
            finally:
                if old is not None:
                    os.environ["MARKET_RADAR_PAPER_HANDOFF_ENABLED"] = old


class ServiceStudioTests(unittest.TestCase):
    def test_service_train_and_status(self):
        with tempfile.TemporaryDirectory() as directory:
            os.environ["MARKET_RADAR_DATA_DIR"] = directory
            try:
                from market_radar.service import MarketRadarService
                service = MarketRadarService()
                train_result = service.train_model(bootstrap_if_empty=True)
                self.assertEqual(train_result["status"], "trained")
                self.assertIn("weights", train_result)

                status = service.get_model_status()
                self.assertTrue(status["is_custom_trained"])

                params = service.get_strategy_params()
                self.assertIn("parameters", params)
                self.assertIn("min_buy_score", params["parameters"])
            finally:
                os.environ.pop("MARKET_RADAR_DATA_DIR", None)


if __name__ == "__main__":
    unittest.main()

