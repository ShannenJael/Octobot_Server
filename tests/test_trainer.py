import json
import tempfile
import unittest
from pathlib import Path

from market_radar.trainer import RadarTrainer
from market_radar.scoring import DEFAULT_WEIGHTS, load_active_weights


class TrainerTests(unittest.TestCase):
    def test_bootstrap_training_converges_and_sums_to_one(self):
        with tempfile.TemporaryDirectory() as directory:
            trainer = RadarTrainer(directory)
            result = trainer.train(bootstrap_if_empty=True, epochs=50)

            self.assertEqual(result["status"], "trained")
            self.assertTrue(result["is_bootstrapped"])
            self.assertGreater(result["sample_count"], 0)

            weights = result["weights"]
            for key in ("trend", "momentum", "liquidity", "volatility", "relative_strength"):
                self.assertIn(key, weights)
                self.assertGreaterEqual(weights[key], 0.04)

            total_weight = sum(weights.values())
            self.assertAlmostEqual(total_weight, 1.0, places=3)

            # Test persistence and loading
            loaded = load_active_weights(directory)
            self.assertEqual(loaded, weights)

            # Test get_status
            status = trainer.get_status()
            self.assertTrue(status["is_custom_trained"])
            self.assertEqual(status["active_weights"], weights)

    def test_skips_when_empty_without_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            trainer = RadarTrainer(directory)
            result = trainer.train(bootstrap_if_empty=False)
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["weights"], DEFAULT_WEIGHTS)


if __name__ == "__main__":
    unittest.main()
