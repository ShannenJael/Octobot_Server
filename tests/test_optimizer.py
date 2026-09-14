import math
import tempfile
import unittest

from market_radar.optimizer import RadarOptimizer, DEFAULT_STRATEGY_PARAMS


def generate_candles(count=200, growth=0.0005):
    candles = []
    price = 100.0
    for i in range(count):
        # Oscillate price with an upward drift
        price *= 1.0 + growth + math.sin(i / 6.0) * 0.008
        candles.append({
            "o": str(price * 0.998),
            "h": str(price * 1.005),
            "l": str(price * 0.995),
            "c": str(price),
            "v": "500",
            "t": 1_700_000_000_000 + i * 3_600_000,
        })
    return candles


class OptimizerTests(unittest.TestCase):
    def test_backtest_runs_and_calculates_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            optimizer = RadarOptimizer(directory)
            candles = generate_candles(count=250)
            metrics = optimizer.backtest(
                candles_1h=candles,
                min_buy_score=60.0,
                take_profit_pct=2.0,
                stop_loss_pct=1.5,
                max_holding_hours=24,
            )
            self.assertIn("total_trades", metrics)
            self.assertIn("win_rate_pct", metrics)
            self.assertIn("profit_factor", metrics)
            self.assertIn("max_drawdown_pct", metrics)
            self.assertGreaterEqual(metrics["win_rate_pct"], 0.0)

    def test_optimize_selects_best_and_saves_params(self):
        with tempfile.TemporaryDirectory() as directory:
            optimizer = RadarOptimizer(directory)
            candles = generate_candles(count=250)
            res = optimizer.optimize(
                candles_1h=candles,
                candidate_scores=[60.0, 70.0],
                candidate_tps=[2.0, 3.0],
                candidate_sls=[1.5],
                candidate_horizons=[12, 24],
            )
            self.assertEqual(res["status"], "optimized")
            self.assertIn("parameters", res)
            self.assertIn("min_buy_score", res["parameters"])
            self.assertIn("take_profit_pct", res["parameters"])

            status = optimizer.get_status()
            self.assertTrue(status["is_optimized"])
            self.assertEqual(status["parameters"], res["parameters"])


if __name__ == "__main__":
    unittest.main()
