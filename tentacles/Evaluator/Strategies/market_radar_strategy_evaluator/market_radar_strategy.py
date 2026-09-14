"""OctoBot Strategy Evaluator that trades on Market Radar multi-timeframe signals."""

from __future__ import annotations

import typing
import logging

try:
    import octobot_commons.constants as common_constants
    import octobot_commons.enums as common_enums
    import octobot_evaluators.evaluators as evaluators
    import octobot_evaluators.enums as enums
    BaseStrategyEvaluator = evaluators.StrategyEvaluator
except ImportError:
    class BaseStrategyEvaluator:
        def __init__(self, tentacles_setup_config=None):
            self.logger = logging.getLogger("MarketRadarStrategyEvaluator")
            self.eval_note = 0.0

        def init_user_inputs(self, inputs: dict) -> None:
            pass

        async def strategy_completed(self, *args, **kwargs):
            pass

from market_radar.service import MarketRadarService
from market_radar.optimizer import RadarOptimizer


class MarketRadarStrategyEvaluator(BaseStrategyEvaluator):
    """Bridges Market Radar AI opportunity rankings into OctoBot trading signals."""

    def __init__(self, tentacles_setup_config=None):
        super().__init__(tentacles_setup_config)
        self.service = MarketRadarService()
        self.optimizer = RadarOptimizer(self.service.journal.root)
        self.evaluation_time_frame = "1h"
        self.min_buy_score = 75.0
        self.max_sell_score = 40.0
        self.max_spread_bps = 25.0

    def init_user_inputs(self, inputs: dict) -> None:
        """Configures the tentacle inputs based on optimizer parameters and user settings."""
        super().init_user_inputs(inputs)
        active_params = self.optimizer.get_active_params()
        self.min_buy_score = float(active_params.get("min_buy_score", 75.0))
        self.max_sell_score = float(active_params.get("max_sell_score", 40.0))
        self.max_spread_bps = float(active_params.get("max_spread_bps", 25.0))

        self.min_buy_score = self.UI.user_input(
            "min_buy_score",
            common_enums.UserInputTypes.FLOAT,
            self.min_buy_score,
            inputs,
            min_val=50.0,
            max_val=95.0,
            title="Minimum Market Radar Score to Buy",
        )
        self.max_sell_score = self.UI.user_input(
            "max_sell_score",
            common_enums.UserInputTypes.FLOAT,
            self.max_sell_score,
            inputs,
            min_val=10.0,
            max_val=50.0,
            title="Maximum Market Radar Score to Sell",
        )
        self.max_spread_bps = self.UI.user_input(
            "max_spread_bps",
            common_enums.UserInputTypes.FLOAT,
            self.max_spread_bps,
            inputs,
            min_val=5.0,
            max_val=100.0,
            title="Maximum Allowed Spread (basis points)",
        )

    def calculate_eval_note(self, score_data: dict) -> float:
        """Converts a radar scoring dictionary into an OctoBot eval_note in [-1.0, 1.0]."""
        score = float(score_data.get("score", 50.0))
        spread = float(score_data.get("spread_bps", 0.0))
        flags = score_data.get("flags", [])

        # Hard guardrail: reject buy on wide spread or extreme volatility
        if spread > self.max_spread_bps or "extreme volatility" in flags:
            return 0.0

        if score >= self.min_buy_score:
            # Scale buy note between 0.3 and 1.0 based on score over threshold
            excess = (score - self.min_buy_score) / max(1.0, (100.0 - self.min_buy_score))
            return round(min(1.0, max(0.3, 0.3 + excess * 0.7)), 3)
        elif score <= self.max_sell_score:
            # Scale sell note between -0.3 and -1.0
            deficit = (self.max_sell_score - score) / max(1.0, self.max_sell_score)
            return round(max(-1.0, min(-0.3, -0.3 - deficit * 0.7)), 3)

        return 0.0

    async def matrix_callback(
        self,
        matrix_id,
        evaluator_name,
        evaluator_type,
        eval_note,
        eval_note_type,
        eval_note_description,
        eval_note_metadata,
        exchange_name,
        cryptocurrency,
        symbol,
        time_frame,
    ):
        """Processes incoming price updates and evaluates symbol against Market Radar."""
        instrument = symbol.replace("/", "_")
        try:
            detail = self.service.detail(instrument)
            self.eval_note = self.calculate_eval_note(detail)
        except Exception as error:
            self.logger.warning(f"MarketRadarStrategy failed for {symbol}: {error}")
            self.eval_note = 0.0

        await self.strategy_completed(cryptocurrency, symbol, time_frame=time_frame)
