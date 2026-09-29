"""Deterministic, versioned market ranking. This module does not place orders."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import statistics
from datetime import datetime, timezone

MODEL_VERSION = "market-radar-1.0.0"

DEFAULT_WEIGHTS = {
    "trend": 0.30,
    "momentum": 0.20,
    "liquidity": 0.25,
    "volatility": 0.15,
    "relative_strength": 0.10,
}


def load_active_weights(data_dir: str | Path | None = None) -> dict[str, float]:
    """Loads calibrated weights if available, otherwise returns DEFAULT_WEIGHTS."""
    root = Path(data_dir or os.getenv("MARKET_RADAR_DATA_DIR", "user/market_radar"))
    weights_path = root / "model_weights.json"
    if weights_path.exists():
        try:
            with open(weights_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                weights = data.get("weights")
                if isinstance(weights, dict) and all(k in weights for k in DEFAULT_WEIGHTS):
                    return {k: float(weights[k]) for k in DEFAULT_WEIGHTS}
        except (ValueError, OSError):
            pass
    return dict(DEFAULT_WEIGHTS)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result


def _rsi(values: list[float], period: int = 14) -> float:
    changes = [right - left for left, right in zip(values[-period - 1 : -1], values[-period:])]
    if not changes:
        return 50.0
    gains = sum(max(change, 0) for change in changes) / len(changes)
    losses = sum(max(-change, 0) for change in changes) / len(changes)
    if losses == 0:
        return 100.0
    return 100 - 100 / (1 + gains / losses)


def _return(values: list[float], periods: int) -> float:
    if len(values) <= periods or values[-periods - 1] <= 0:
        return 0.0
    return values[-1] / values[-periods - 1] - 1


def _closes(candles: list[dict]) -> list[float]:
    result = []
    for candle in candles:
        try:
            value = float(candle["c"])
            if value > 0:
                result.append(value)
        except (KeyError, TypeError, ValueError):
            pass
    return result


def score_market(
    ticker: dict,
    candles_by_timeframe: dict[str, list[dict]],
    btc_change: float = 0.0,
    weights: dict[str, float] | None = None,
) -> dict:
    series = {timeframe: _closes(candles) for timeframe, candles in candles_by_timeframe.items()}
    one_hour = series.get("1h", [])
    if len(one_hour) < 50:
        raise ValueError("At least 50 valid hourly candles are required")

    active_weights = weights or load_active_weights()
    trend_votes = []
    for timeframe in ("1h", "4h", "1D"):
        values = series.get(timeframe, [])
        if len(values) >= 50:
            ema20, ema50 = _ema(values[-60:], 20), _ema(values[-80:], 50)
            distance = (ema20 / ema50 - 1) if ema50 else 0
            trend_votes.append(_clamp(50 + distance * 1200))
    trend = statistics.fmean(trend_votes) if trend_votes else 50.0

    rsi = _rsi(one_hour)
    return_6h = _return(one_hour, 6)
    return_24h = _return(one_hour, 24)
    # Momentum is strongest around RSI 60-68; overbought readings are penalized.
    rsi_score = _clamp(100 - abs(rsi - 64) * 3.2)
    momentum = _clamp(0.55 * rsi_score + 45 + return_6h * 500 + return_24h * 180)

    log_returns = [math.log(right / left) for left, right in zip(one_hour[-49:-1], one_hour[-48:]) if left > 0]
    hourly_vol = statistics.pstdev(log_returns) if len(log_returns) > 2 else 0.0
    # Prefer enough movement to trade, but reject chaotic markets.
    volatility = _clamp(100 - abs(hourly_vol - 0.012) * 5000)

    quote_volume = max(float(ticker.get("quote_volume") or ticker.get("vv") or 0), 1)
    bid = float(ticker.get("bid") or ticker.get("b") or 0)
    ask = float(ticker.get("ask") or ticker.get("k") or 0)
    midpoint = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
    spread_bps = ((ask - bid) / midpoint * 10000) if midpoint else 10000
    liquidity = _clamp((math.log10(quote_volume) - 4) * 24 - max(0, spread_bps - 5) * 0.7)

    ticker_change = float(ticker.get("c") or 0)
    relative_strength = _clamp(50 + (ticker_change - btc_change) * 500)
    data_completeness = sum(len(series.get(tf, [])) >= 50 for tf in ("1h", "4h", "1D")) / 3
    risk_penalty = _clamp(max(0, spread_bps - 12) * 0.9 + max(0, hourly_vol - 0.035) * 1000 + (1 - data_completeness) * 15, 0, 45)

    components = {
        "trend": round(trend, 2),
        "momentum": round(momentum, 2),
        "liquidity": round(liquidity, 2),
        "volatility": round(volatility, 2),
        "relative_strength": round(relative_strength, 2),
    }
    weighted = sum(components[k] * active_weights.get(k, DEFAULT_WEIGHTS.get(k, 0.2)) for k in components)
    total = round(_clamp(weighted - risk_penalty), 2)
    as_of_ms = max(int(candle.get("t", 0)) for candle in candles_by_timeframe.get("1h", []))
    instrument = str(ticker.get("i"))
    signal_id = hashlib.sha256(f"{MODEL_VERSION}|{instrument}|{as_of_ms}".encode()).hexdigest()[:20]
    flags = []
    if spread_bps > 20:
        flags.append("wide spread")
    if hourly_vol > 0.035:
        flags.append("extreme volatility")
    if data_completeness < 1:
        flags.append("incomplete multi-timeframe history")
    return {
        "signal_id": signal_id,
        "model_version": MODEL_VERSION,
        "instrument": instrument,
        "symbol": instrument.replace("_", "/"),
        "score": total,
        "rating": "strong" if total >= 75 else "watch" if total >= 60 else "neutral" if total >= 45 else "avoid",
        "last_price": float(ticker.get("last") or ticker.get("a") or one_hour[-1]),
        "change_24h": round(ticker_change * 100, 3),
        "quote_volume_24h": round(quote_volume, 2),
        "spread_bps": round(spread_bps, 2),
        "rsi_14": round(rsi, 2),
        "return_6h": round(return_6h * 100, 3),
        "return_24h": round(return_24h * 100, 3),
        "hourly_volatility": round(hourly_vol * 100, 3),
        "risk_penalty": round(risk_penalty, 2),
        "components": components,
        "weights": active_weights,
        "flags": flags,
        "as_of_ms": as_of_ms,
        "as_of": datetime.fromtimestamp(as_of_ms / 1000, tz=timezone.utc).isoformat(),
    }


def deterministic_explanation(result: dict, sentiment_summary: dict | None = None) -> dict:
    components = result["components"]
    strongest = max(components, key=components.get)
    weakest = min(components, key=components.get)
    risk = ", ".join(result["flags"]) if result["flags"] else "no automatic risk flags"
    summary = (
        f"{result['symbol']} ranks {result['rating']} at {result['score']}/100. "
        f"Its strongest measured factor is {strongest.replace('_', ' ')}; "
        f"the weakest is {weakest.replace('_', ' ')}. Current checks show {risk}."
    )
    if sentiment_summary:
        sentiment_val = sentiment_summary.get("composite_score")
        sentiment_lbl = sentiment_summary.get("sentiment_label", "Neutral")
        catalysts = [h.get("title") for h in sentiment_summary.get("recent_headlines", [])[:3]]
    else:
        sentiment_val = None
        sentiment_lbl = "unavailable (no verified news feed)"
        catalysts = []

    return {
        "status": "deterministic",
        "summary": summary,
        "sentiment": sentiment_val,
        "sentiment_label": sentiment_lbl,
        "catalysts": catalysts,
        "risks": result["flags"],
        "disclaimer": "Research signal only; not financial advice or an order instruction.",
    }
