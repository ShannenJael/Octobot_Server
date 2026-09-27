"""Historical market training profiles for Crypto.com AI decision support."""

from __future__ import annotations

import json
import os
import statistics
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


class HistoricalTrainingService:
    """Collects OHLCV history and distills it into prompt-safe market features."""

    SUPPORTED_TIMEFRAMES = {"5m", "15m", "30m", "1h", "4h", "1d"}
    MAX_RANGE_DAYS = 366
    MAX_INSTRUMENTS = 8

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        exchange_factory: Optional[Callable[[], Any]] = None,
    ):
        self.data_dir = data_dir or Path(
            os.getenv("MARKET_RADAR_DATA_DIR", "user/crypto_com_trader")
        )
        self.profile_path = self.data_dir / "ai_training_profile.json"
        self.exchange_factory = exchange_factory or self._default_exchange_factory

    @staticmethod
    def _default_exchange_factory() -> Any:
        import ccxt

        return ccxt.cryptocom({"enableRateLimit": True})

    @staticmethod
    def _parse_date(value: str, field: str) -> date:
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{field} must use YYYY-MM-DD format") from error

    @staticmethod
    def _normalize_instrument(value: str) -> str:
        instrument = str(value).strip().upper().replace("/", "_").replace("-", "_")
        if not instrument.endswith("_USDT") or not instrument.replace("_", "").isalnum():
            raise ValueError(f"Unsupported Crypto.com instrument: {value}")
        return instrument

    @staticmethod
    def _to_symbol(instrument: str) -> str:
        return instrument.replace("_", "/", 1)

    @staticmethod
    def _timeframe_ms(exchange: Any, timeframe: str) -> int:
        if hasattr(exchange, "parse_timeframe"):
            return int(exchange.parse_timeframe(timeframe) * 1000)
        units = {"m": 60, "h": 3600, "d": 86400}
        return int(timeframe[:-1]) * units[timeframe[-1]] * 1000

    def _fetch_range(
        self,
        exchange: Any,
        instrument: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
    ) -> list[list[float]]:
        timeframe_ms = self._timeframe_ms(exchange, timeframe)
        since = start_ms
        candles: dict[int, list[float]] = {}
        while since < end_ms:
            batch = exchange.fetch_ohlcv(
                self._to_symbol(instrument), timeframe=timeframe, since=since, limit=300
            )
            if not batch:
                break
            newest = since
            for candle in batch:
                if len(candle) < 6:
                    continue
                timestamp = int(candle[0])
                newest = max(newest, timestamp)
                if start_ms <= timestamp < end_ms:
                    candles[timestamp] = [float(value) for value in candle[:6]]
            next_since = newest + timeframe_ms
            if next_since <= since:
                break
            since = next_since
            if newest >= end_ms - timeframe_ms:
                break
        return [candles[key] for key in sorted(candles)]

    @staticmethod
    def _percentile(values: list[float], ratio: float) -> float:
        ordered = sorted(values)
        if not ordered:
            return 0.0
        index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * ratio)))
        return ordered[index]

    @classmethod
    def _summarize(cls, instrument: str, candles: list[list[float]]) -> dict[str, Any]:
        if len(candles) < 30:
            raise ValueError(f"{instrument} returned only {len(candles)} candles; at least 30 are required")

        closes = [row[4] for row in candles]
        volumes = [row[5] for row in candles]
        returns = [
            ((closes[index] / closes[index - 1]) - 1.0) * 100.0
            for index in range(1, len(closes))
            if closes[index - 1] > 0
        ]
        ranges = [
            ((row[2] - row[3]) / row[1]) * 100.0
            for row in candles
            if row[1] > 0
        ]
        positive = sum(1 for value in returns if value > 0)
        negative = sum(1 for value in returns if value < 0)
        peak = closes[0]
        max_drawdown = 0.0
        for close in closes:
            peak = max(peak, close)
            if peak > 0:
                max_drawdown = min(max_drawdown, ((close / peak) - 1.0) * 100.0)

        fast_window = closes[-min(20, len(closes)) :]
        slow_window = closes[-min(80, len(closes)) :]
        fast_sma = statistics.fmean(fast_window)
        slow_sma = statistics.fmean(slow_window)
        total_return = ((closes[-1] / closes[0]) - 1.0) * 100.0
        if fast_sma > slow_sma * 1.01 and total_return > 0:
            regime = "bullish"
        elif fast_sma < slow_sma * 0.99 and total_return < 0:
            regime = "bearish"
        else:
            regime = "range-bound"

        recent_volume = statistics.fmean(volumes[-min(20, len(volumes)) :])
        baseline_volume = statistics.fmean(volumes) or 1.0
        next_up_after_up = []
        next_up_after_down = []
        for index in range(len(returns) - 1):
            target = 1 if returns[index + 1] > 0 else 0
            (next_up_after_up if returns[index] > 0 else next_up_after_down).append(target)

        return {
            "instrument": instrument,
            "candle_count": len(candles),
            "first_candle_at": datetime.fromtimestamp(candles[0][0] / 1000, timezone.utc).isoformat(),
            "last_candle_at": datetime.fromtimestamp(candles[-1][0] / 1000, timezone.utc).isoformat(),
            "regime": regime,
            "total_return_pct": round(total_return, 3),
            "average_candle_return_pct": round(statistics.fmean(returns), 5),
            "return_volatility_pct": round(statistics.pstdev(returns), 5),
            "up_candle_pct": round((positive / max(1, positive + negative)) * 100.0, 2),
            "average_range_pct": round(statistics.fmean(ranges), 4),
            "max_drawdown_pct": round(max_drawdown, 3),
            "support_zone": round(cls._percentile(closes, 0.20), 8),
            "median_price": round(cls._percentile(closes, 0.50), 8),
            "resistance_zone": round(cls._percentile(closes, 0.80), 8),
            "fast_sma": round(fast_sma, 8),
            "slow_sma": round(slow_sma, 8),
            "recent_volume_vs_average": round(recent_volume / baseline_volume, 3),
            "next_up_probability_after_up_pct": round(
                statistics.fmean(next_up_after_up) * 100.0 if next_up_after_up else 50.0, 2
            ),
            "next_up_probability_after_down_pct": round(
                statistics.fmean(next_up_after_down) * 100.0 if next_up_after_down else 50.0, 2
            ),
        }

    def train(
        self,
        start_date: str,
        end_date: str,
        instruments: list[str],
        timeframe: str = "1h",
    ) -> dict[str, Any]:
        start = self._parse_date(start_date, "start_date")
        end = self._parse_date(end_date, "end_date")
        if end < start:
            raise ValueError("end_date must be on or after start_date")
        if end > date.today():
            raise ValueError("end_date cannot be in the future")
        range_days = (end - start).days + 1
        if range_days > self.MAX_RANGE_DAYS:
            raise ValueError(f"Date range cannot exceed {self.MAX_RANGE_DAYS} days")
        if timeframe not in self.SUPPORTED_TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        normalized = list(dict.fromkeys(self._normalize_instrument(item) for item in instruments))
        if not normalized:
            raise ValueError("Select at least one instrument")
        if len(normalized) > self.MAX_INSTRUMENTS:
            raise ValueError(f"Select no more than {self.MAX_INSTRUMENTS} instruments")

        start_ms = int(datetime.combine(start, datetime.min.time(), timezone.utc).timestamp() * 1000)
        end_exclusive = datetime.combine(end, datetime.min.time(), timezone.utc).timestamp() + 86400
        end_ms = int(end_exclusive * 1000)
        exchange = self.exchange_factory()
        summaries = {}
        total_candles = 0
        for instrument in normalized:
            candles = self._fetch_range(exchange, instrument, timeframe, start_ms, end_ms)
            summaries[instrument] = self._summarize(instrument, candles)
            total_candles += len(candles)

        profile = {
            "schema_version": 1,
            "status": "ready",
            "exchange": "Crypto.com",
            "trained_at": int(time.time()),
            "trained_at_iso": datetime.now(timezone.utc).isoformat(),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "timeframe": timeframe,
            "instrument_count": len(summaries),
            "total_candles": total_candles,
            "instruments": summaries,
            "usage_note": (
                "Historical statistics are supporting context only. Live price, liquidity, "
                "risk limits, and model agreement must remain the primary decision inputs."
            ),
        }
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = self.profile_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        temporary_path.replace(self.profile_path)
        return profile

    def status(self) -> dict[str, Any]:
        if not self.profile_path.exists():
            return {"status": "not_trained", "profile_exists": False}
        try:
            profile = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"status": "invalid", "profile_exists": True}
        profile["profile_exists"] = True
        return profile

    @staticmethod
    def load_context(data_dir: Optional[Path], instrument: str) -> Optional[dict[str, Any]]:
        root = data_dir or Path(os.getenv("MARKET_RADAR_DATA_DIR", "user/crypto_com_trader"))
        path = root / "ai_training_profile.json"
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
            summary = (profile.get("instruments") or {}).get(instrument.upper())
            if not summary:
                return None
            allowed = {
                key: summary.get(key)
                for key in (
                    "regime",
                    "candle_count",
                    "total_return_pct",
                    "return_volatility_pct",
                    "up_candle_pct",
                    "average_range_pct",
                    "max_drawdown_pct",
                    "support_zone",
                    "median_price",
                    "resistance_zone",
                    "recent_volume_vs_average",
                    "next_up_probability_after_up_pct",
                    "next_up_probability_after_down_pct",
                )
            }
            return {
                "source": "historical_training_profile",
                "trained_at_iso": profile.get("trained_at_iso"),
                "date_range": f"{profile.get('start_date')} to {profile.get('end_date')}",
                "timeframe": profile.get("timeframe"),
                **allowed,
            }
        except (OSError, ValueError, TypeError):
            return None
