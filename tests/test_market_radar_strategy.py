import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock

# Load market_radar_strategy directly to avoid loading unrelated tentacles
strategy_path = (
    Path(__file__).resolve().parent.parent
    / "tentacles"
    / "Evaluator"
    / "Strategies"
    / "market_radar_strategy_evaluator"
    / "market_radar_strategy.py"
)
spec = importlib.util.spec_from_file_location("market_radar_strategy", strategy_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MarketRadarStrategyEvaluator = module.MarketRadarStrategyEvaluator


class StrategyEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.mock_config = MagicMock()
        self.evaluator = MarketRadarStrategyEvaluator(self.mock_config)
        self.evaluator.min_buy_score = 75.0
        self.evaluator.max_sell_score = 40.0
        self.evaluator.max_spread_bps = 25.0

    def test_calculate_eval_note_buy(self):
        score_data = {
            "score": 85.0,
            "spread_bps": 10.0,
            "flags": [],
        }
        note = self.evaluator.calculate_eval_note(score_data)
        self.assertGreater(note, 0.3)
        self.assertLessEqual(note, 1.0)

    def test_calculate_eval_note_sell(self):
        score_data = {
            "score": 30.0,
            "spread_bps": 10.0,
            "flags": [],
        }
        note = self.evaluator.calculate_eval_note(score_data)
        self.assertLess(note, -0.3)
        self.assertGreaterEqual(note, -1.0)

    def test_calculate_eval_note_neutral(self):
        score_data = {
            "score": 55.0,
            "spread_bps": 10.0,
            "flags": [],
        }
        note = self.evaluator.calculate_eval_note(score_data)
        self.assertEqual(note, 0.0)

    def test_calculate_eval_note_rejects_wide_spread(self):
        score_data = {
            "score": 90.0,
            "spread_bps": 40.0,  # exceeds max_spread_bps = 25.0
            "flags": ["wide spread"],
        }
        note = self.evaluator.calculate_eval_note(score_data)
        self.assertEqual(note, 0.0)

    def test_calculate_eval_note_rejects_extreme_volatility(self):
        score_data = {
            "score": 90.0,
            "spread_bps": 10.0,
            "flags": ["extreme volatility"],
        }
        note = self.evaluator.calculate_eval_note(score_data)
        self.assertEqual(note, 0.0)


if __name__ == "__main__":
    unittest.main()
