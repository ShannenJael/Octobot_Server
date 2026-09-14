"""Automated Strategy Parameter Optimizer for Market Radar signals."""

from __future__ import annotations

import json
import math
import os
import statistics
import time
from pathlib import Path

from .scoring import DEFAULT_WEIGHTS, MODEL_VERSION, score_market


DEFAULT_STRATEGY_PARAMS = {
    "min_buy_score": 75.0,
    "max_sell_score": 40.0,
    "take_profit_pct": 3.0,
    "stop_loss_pct": 2.0,
    "max_holding_hours": 24,
    "max_spread_bps": 25.0,
}


class RadarOptimizer:
    """Simulates and optimizes trade entry/exit parameters over candle series."""

    def __init__(self, data_dir: str | Path | None = None):
        self.root = Path(data_dir or os.getenv("MARKET_RADAR_DATA_DIR", "user/market_radar"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.params_path = self.root / "strategy_params.json"

    def backtest(
        self,
        candles_1h: list[dict],
        min_buy_score: float,
        take_profit_pct: float,
        stop_loss_pct: float,
        max_holding_hours: int,
    ) -> dict:
        """Simulates trades on a 1-hour candle series using the specified parameters."""
        if len(candles_1h) < 60:
            return {
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "trades": [],
            }

        closes = []
        for c in candles_1h:
            try:
                closes.append(float(c["c"]))
            except (KeyError, TypeError, ValueError):
                continue

        trades = []
        in_trade = False
        entry_price = 0.0
        entry_idx = 0

        # Step through candle history (step every 2 candles to avoid over-trading)
        step = 2
        for i in range(50, len(closes) - 1, step):
            if not in_trade:
                # Calculate window momentum and trend proxy
                window = closes[max(0, i - 48) : i + 1]
                if len(window) < 30:
                    continue
                # Simple rapid score proxy for backtest simulation:
                # 6h return, 24h return, EMA20/EMA50
                r6 = (window[-1] / window[-7] - 1) if len(window) > 7 else 0.0
                r24 = (window[-1] / window[-25] - 1) if len(window) > 25 else 0.0
                sim_score = 50.0 + r6 * 400 + r24 * 200
                sim_score = max(0.0, min(100.0, sim_score))

                if sim_score >= min_buy_score:
                    in_trade = True
                    entry_price = closes[i]
                    entry_idx = i
            else:
                # Check exit conditions
                current_price = closes[i]
                holding_hours = i - entry_idx
                ret_pct = ((current_price / entry_price) - 1) * 100

                exit_reason = None
                if ret_pct >= take_profit_pct:
                    exit_reason = "take_profit"
                elif ret_pct <= -stop_loss_pct:
                    exit_reason = "stop_loss"
                elif holding_hours >= max_holding_hours:
                    exit_reason = "time_exit"

                if exit_reason:
                    trades.append({
                        "entry_idx": entry_idx,
                        "exit_idx": i,
                        "holding_hours": holding_hours,
                        "return_pct": round(ret_pct, 2),
                        "reason": exit_reason,
                    })
                    in_trade = False

        if not trades:
            return {
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "trades": [],
            }

        returns = [t["return_pct"] for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]

        win_rate = (len(wins) / len(trades)) * 100 if trades else 0.0
        sum_wins = sum(wins)
        sum_losses = abs(sum(losses))
        profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else (99.0 if sum_wins > 0 else 0.0)

        # Equity curve & Max Drawdown
        equity = 100.0
        peak = 100.0
        max_dd = 0.0
        for r in returns:
            equity *= (1.0 + r / 100.0)
            if equity > peak:
                peak = equity
            dd = ((peak - equity) / peak) * 100.0
            if dd > max_dd:
                max_dd = dd

        total_return = equity - 100.0
        stdev = statistics.stdev(returns) if len(returns) > 1 else 1.0
        sharpe = (statistics.mean(returns) / stdev * math.sqrt(len(returns))) if stdev > 0 else 0.0

        return {
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "total_return_pct": round(total_return, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "trades": trades[:20],
        }

    def optimize(
        self,
        candles_1h: list[dict],
        candidate_scores: list[float] | None = None,
        candidate_tps: list[float] | None = None,
        candidate_sls: list[float] | None = None,
        candidate_horizons: list[int] | None = None,
    ) -> dict:
        """Runs grid search across parameter candidates and selects the Pareto-optimal configuration."""
        scores = candidate_scores or [65.0, 70.0, 75.0, 80.0]
        tps = candidate_tps or [2.0, 3.0, 4.5]
        sls = candidate_sls or [1.5, 2.0, 3.0]
        horizons = candidate_horizons or [12, 24, 48]

        best_score = -float("inf")
        best_params = dict(DEFAULT_STRATEGY_PARAMS)
        best_metrics = {}
        all_results = []

        for min_buy in scores:
            for tp in tps:
                for sl in sls:
                    for horizon in horizons:
                        metrics = self.backtest(candles_1h, min_buy, tp, sl, horizon)
                        if metrics["total_trades"] < 2:
                            continue

                        # Objective function: Sharpe + Profit Factor - Drawdown penalty
                        objective = (
                            metrics["sharpe_ratio"] * 2.0
                            + min(metrics["profit_factor"], 5.0) * 1.5
                            + (metrics["win_rate_pct"] / 20.0)
                            - (metrics["max_drawdown_pct"] / 10.0)
                        )

                        all_results.append({
                            "params": {
                                "min_buy_score": min_buy,
                                "max_sell_score": 40.0,
                                "take_profit_pct": tp,
                                "stop_loss_pct": sl,
                                "max_holding_hours": horizon,
                                "max_spread_bps": 25.0,
                            },
                            "metrics": metrics,
                            "objective": round(objective, 3),
                        })

                        if objective > best_score:
                            best_score = objective
                            best_params = {
                                "min_buy_score": min_buy,
                                "max_sell_score": 40.0,
                                "take_profit_pct": tp,
                                "stop_loss_pct": sl,
                                "max_holding_hours": horizon,
                                "max_spread_bps": 25.0,
                            }
                            best_metrics = metrics

        payload = {
            "model_version": MODEL_VERSION,
            "optimized_at": int(time.time()),
            "optimized_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "parameters": best_params,
            "metrics": best_metrics or {
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
            },
            "total_tested_combinations": len(scores) * len(tps) * len(sls) * len(horizons),
        }

        # Save to strategy_params.json
        with open(self.params_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return {
            "status": "optimized",
            **payload,
        }

    def get_active_params(self) -> dict:
        """Returns the active strategy parameters from disk, or defaults."""
        if self.params_path.exists():
            try:
                with open(self.params_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "parameters" in data and isinstance(data["parameters"], dict):
                        return data["parameters"]
            except (ValueError, OSError):
                pass
        return dict(DEFAULT_STRATEGY_PARAMS)

    def get_status(self) -> dict:
        """Returns strategy parameters and optimization telemetry."""
        params = self.get_active_params()
        status = {
            "parameters": params,
            "is_optimized": self.params_path.exists(),
        }
        if self.params_path.exists():
            try:
                with open(self.params_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    status.update({
                        "optimized_at": metadata.get("optimized_at"),
                        "optimized_at_iso": metadata.get("optimized_at_iso"),
                        "metrics": metadata.get("metrics"),
                        "total_tested_combinations": metadata.get("total_tested_combinations"),
                    })
            except (ValueError, OSError):
                pass
        return status
