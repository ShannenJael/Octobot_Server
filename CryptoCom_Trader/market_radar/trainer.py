"""Self-tuning trainer for Market Radar component weights based on realized outcomes."""

from __future__ import annotations

import json
import math
import os
import random
import time
from pathlib import Path

from .scoring import DEFAULT_WEIGHTS, MODEL_VERSION


class RadarTrainer:
    """Optimizes component weights using realized prediction outcomes from RadarJournal."""

    FEATURE_KEYS = ("trend", "momentum", "liquidity", "volatility", "relative_strength")
    MIN_WEIGHT = 0.05
    AVAILABLE_WEIGHT_SPREAD = 0.75  # 1.0 - 5 * 0.05

    def __init__(self, data_dir: str | Path | None = None):
        self.root = Path(data_dir or os.getenv("MARKET_RADAR_DATA_DIR", "user/market_radar"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "prediction_events.jsonl"
        self.weights_path = self.root / "model_weights.json"

    def load_dataset(self) -> list[dict]:
        """Pairs predictions with their latest realized outcomes from the journal."""
        if not self.events_path.exists():
            return []

        predictions: dict[str, dict] = {}
        outcomes: dict[str, list[dict]] = {}

        with self.events_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    event_type = event.get("type")
                    signal_id = event.get("signal_id")
                    if not signal_id:
                        continue
                    if event_type == "prediction" and "components" in event:
                        predictions[signal_id] = event
                    elif event_type == "outcome" and "realized_return_pct" in event:
                        outcomes.setdefault(signal_id, []).append(event)
                except (ValueError, OSError):
                    continue

        dataset = []
        for signal_id, pred in predictions.items():
            resolved = outcomes.get(signal_id, [])
            if not resolved:
                continue
            # Prefer 24h outcome if available, otherwise average resolved returns
            ret_24h = next((o["realized_return_pct"] for o in resolved if o.get("horizon_hours") == 24), None)
            if ret_24h is None:
                ret_24h = sum(o["realized_return_pct"] for o in resolved) / len(resolved)

            dataset.append({
                "signal_id": signal_id,
                "components": pred["components"],
                "risk_penalty": float(pred.get("risk_penalty", 0.0)),
                "realized_return_pct": float(ret_24h),
                "recorded_at": pred.get("recorded_at", int(time.time())),
            })

        return dataset

    def _generate_bootstrap_samples(self, count: int = 50) -> list[dict]:
        """Generates realistic synthetic outcome samples for cold-start training."""
        samples = []
        random.seed(42)
        for index in range(count):
            trend = random.uniform(30.0, 85.0)
            momentum = random.uniform(25.0, 80.0)
            liquidity = random.uniform(40.0, 90.0)
            volatility = random.uniform(20.0, 75.0)
            relative_strength = random.uniform(30.0, 80.0)
            risk = random.uniform(0.0, 15.0)

            # Ground-truth return signal has strong dependence on trend and momentum
            simulated_return = (
                (trend - 50.0) * 0.08
                + (momentum - 50.0) * 0.06
                + (relative_strength - 50.0) * 0.04
                + (liquidity - 50.0) * 0.02
                - risk * 0.1
                + random.gauss(0, 1.2)
            )

            samples.append({
                "signal_id": f"bootstrap_{index}",
                "components": {
                    "trend": trend,
                    "momentum": momentum,
                    "liquidity": liquidity,
                    "volatility": volatility,
                    "relative_strength": relative_strength,
                },
                "risk_penalty": risk,
                "realized_return_pct": round(simulated_return, 3),
                "recorded_at": int(time.time()),
            })
        return samples

    def _theta_to_weights(self, theta: list[float]) -> dict[str, float]:
        """Maps unconstrained parameters theta to normalized simplex weights with floor."""
        max_t = max(theta)
        exp_t = [math.exp(t - max_t) for t in theta]
        sum_exp = sum(exp_t)
        softmax = [e / sum_exp for e in exp_t]

        weights = {}
        for key, s in zip(self.FEATURE_KEYS, softmax):
            weights[key] = round(self.MIN_WEIGHT + self.AVAILABLE_WEIGHT_SPREAD * s, 4)

        # Ensure exact sum to 1.0
        total = sum(weights.values())
        diff = round(1.0 - total, 4)
        weights["trend"] = round(weights["trend"] + diff, 4)
        return weights

    def train(self, bootstrap_if_empty: bool = True, epochs: int = 200, lr: float = 0.05) -> dict:
        """Runs gradient descent to fit component weights against realized returns."""
        dataset = self.load_dataset()
        is_bootstrapped = False

        if len(dataset) < 5:
            if not bootstrap_if_empty:
                return {
                    "status": "skipped",
                    "reason": f"Insufficient resolved outcomes ({len(dataset)}/5 required)",
                    "weights": self.get_active_weights(),
                }
            dataset = self._generate_bootstrap_samples(60)
            is_bootstrapped = True

        # Target mapping: map return to ideal score in [20, 80] centered at 50
        # Positive returns target scores > 50, negative returns target scores < 50
        targets = []
        for d in dataset:
            ret = d["realized_return_pct"]
            target = max(10.0, min(90.0, 50.0 + ret * 5.0))
            targets.append(target)

        # Initialize theta from default weights
        theta = [0.0] * len(self.FEATURE_KEYS)
        for i, key in enumerate(self.FEATURE_KEYS):
            target_share = (DEFAULT_WEIGHTS.get(key, 0.2) - self.MIN_WEIGHT) / self.AVAILABLE_WEIGHT_SPREAD
            target_share = max(0.01, min(0.99, target_share))
            theta[i] = math.log(target_share)

        best_loss = float("inf")
        best_weights = self._theta_to_weights(theta)

        # Adam optimizer state
        m = [0.0] * len(theta)
        v = [0.0] * len(theta)
        beta1, beta2, eps = 0.9, 0.999, 1e-8

        for epoch in range(1, epochs + 1):
            weights = self._theta_to_weights(theta)
            # Compute loss and gradients via finite differences for numerical stability
            # Loss: MSE(predicted_score, target) + L2 penalty towards default weights
            current_loss = 0.0
            for d, target in zip(dataset, targets):
                pred_score = sum(weights[k] * d["components"].get(k, 50.0) for k in self.FEATURE_KEYS)
                pred_score -= d.get("risk_penalty", 0.0)
                current_loss += (pred_score - target) ** 2
            current_loss /= len(dataset)

            # L2 penalty
            for k in self.FEATURE_KEYS:
                current_loss += 5.0 * (weights[k] - DEFAULT_WEIGHTS.get(k, 0.2)) ** 2

            if current_loss < best_loss:
                best_loss = current_loss
                best_weights = weights

            # Compute numerical gradient
            h = 1e-4
            grad = [0.0] * len(theta)
            for i in range(len(theta)):
                theta_forward = list(theta)
                theta_forward[i] += h
                w_fwd = self._theta_to_weights(theta_forward)

                loss_fwd = 0.0
                for d, target in zip(dataset, targets):
                    pred_score = sum(w_fwd[k] * d["components"].get(k, 50.0) for k in self.FEATURE_KEYS)
                    pred_score -= d.get("risk_penalty", 0.0)
                    loss_fwd += (pred_score - target) ** 2
                loss_fwd /= len(dataset)
                for k in self.FEATURE_KEYS:
                    loss_fwd += 5.0 * (w_fwd[k] - DEFAULT_WEIGHTS.get(k, 0.2)) ** 2

                grad[i] = (loss_fwd - current_loss) / h

            # Update theta with Adam
            for i in range(len(theta)):
                m[i] = beta1 * m[i] + (1 - beta1) * grad[i]
                v[i] = beta2 * v[i] + (1 - beta2) * (grad[i] ** 2)
                m_hat = m[i] / (1 - beta1 ** epoch)
                v_hat = v[i] / (1 - beta2 ** epoch)
                theta[i] -= lr * m_hat / (math.sqrt(v_hat) + eps)

        # Compute directional accuracy / win rate on trained weights
        correct_direction = 0
        for d in dataset:
            pred_score = sum(best_weights[k] * d["components"].get(k, 50.0) for k in self.FEATURE_KEYS)
            pred_score -= d.get("risk_penalty", 0.0)
            ret = d["realized_return_pct"]
            if (pred_score >= 50.0 and ret >= 0.0) or (pred_score < 50.0 and ret < 0.0):
                correct_direction += 1
        accuracy_pct = round((correct_direction / len(dataset)) * 100, 1)

        result_payload = {
            "model_version": MODEL_VERSION,
            "trained_at": int(time.time()),
            "trained_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sample_count": len(dataset),
            "is_bootstrapped": is_bootstrapped,
            "weights": best_weights,
            "loss": round(best_loss, 4),
            "directional_accuracy_pct": accuracy_pct,
        }

        # Save weights to file
        with open(self.weights_path, "w", encoding="utf-8") as f:
            json.dump(result_payload, f, indent=2)

        return {
            "status": "trained",
            **result_payload,
        }

    def get_active_weights(self) -> dict[str, float]:
        """Returns the active weights from disk, or defaults."""
        if self.weights_path.exists():
            try:
                with open(self.weights_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "weights" in data and isinstance(data["weights"], dict):
                        return data["weights"]
            except (ValueError, OSError):
                pass
        return dict(DEFAULT_WEIGHTS)

    def get_status(self) -> dict:
        """Returns the current model status and metrics."""
        dataset = self.load_dataset()
        status = {
            "active_weights": self.get_active_weights(),
            "resolved_samples": len(dataset),
            "is_custom_trained": self.weights_path.exists(),
        }
        if self.weights_path.exists():
            try:
                with open(self.weights_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    status.update({
                        "trained_at": metadata.get("trained_at"),
                        "trained_at_iso": metadata.get("trained_at_iso"),
                        "sample_count": metadata.get("sample_count"),
                        "is_bootstrapped": metadata.get("is_bootstrapped", False),
                        "directional_accuracy_pct": metadata.get("directional_accuracy_pct"),
                        "loss": metadata.get("loss"),
                    })
            except (ValueError, OSError):
                pass
        return status
