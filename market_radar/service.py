"""Orchestrates collection, ranking, explanations, journaling and paper handoff."""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .ai import explain_with_ai
from .crypto_com import CryptoComPublicClient, MarketDataError, liquid_usdt_tickers
from .journal import RadarJournal
from .optimizer import RadarOptimizer
from .scoring import MODEL_VERSION, deterministic_explanation, score_market
from .sentiment import RadarSentimentClient
from .trainer import RadarTrainer


class MarketRadarService:
    def __init__(self):
        self.client = CryptoComPublicClient()
        self.journal = RadarJournal()
        self.trainer = RadarTrainer(self.journal.root)
        self.optimizer = RadarOptimizer(self.journal.root)
        self.sentiment = RadarSentimentClient()
        self.cache_seconds = max(30, int(os.getenv("MARKET_RADAR_CACHE_SECONDS", "120")))
        self._cache = None
        self._cache_at = 0.0
        self._cache_limit = 0
        self._lock = threading.Lock()

    def _analyze(self, ticker: dict, btc_change: float) -> dict:
        candles = {
            timeframe: self.client.candles(ticker["i"], timeframe, 90)
            for timeframe in ("1h", "4h", "1D")
        }
        return score_market(ticker, candles, btc_change)

    def scan(self, limit: int = 12, force: bool = False) -> dict:
        now = time.time()
        with self._lock:
            if (
                not force
                and self._cache
                and now - self._cache_at < self.cache_seconds
                and self._cache_limit >= limit
            ):
                payload = dict(self._cache)
                payload["results"] = list(self._cache.get("results", []))[:limit]
                return payload
        tickers = self.client.tickers()
        current_prices = {}
        for item in tickers:
            try:
                current_prices[str(item.get("i"))] = float(item.get("a") or 0)
            except (TypeError, ValueError):
                pass
        outcomes_recorded = self.journal.resolve_due_outcomes(current_prices)
        candidates = liquid_usdt_tickers(tickers, limit)
        btc_change = next((float(item.get("c") or 0) for item in tickers if item.get("i") == "BTC_USDT"), 0.0)
        results, errors = [], []
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(candidates)))) as executor:
            futures = {executor.submit(self._analyze, ticker, btc_change): ticker["i"] for ticker in candidates}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    self.journal.record_prediction(result)
                except Exception as error:
                    errors.append({"instrument": futures[future], "error": type(error).__name__})
        results.sort(key=lambda item: item["score"], reverse=True)
        payload = {
            "status": "ok" if results else "unavailable",
            "source": "Crypto.com public REST",
            "model_version": MODEL_VERSION,
            "generated_at": int(time.time()),
            "advisory_only": True,
            "paper_handoff_enabled": os.getenv("MARKET_RADAR_PAPER_HANDOFF_ENABLED", "false").lower() == "true",
            "watchlist": self.journal.get_watchlist(),
            "outcomes_recorded": outcomes_recorded,
            "active_weights": self.trainer.get_active_weights(),
            "strategy_params": self.optimizer.get_active_params(),
            "model_status": self.trainer.get_status(),
            "market_sentiment": self.sentiment.get_market_sentiment_summary(),
            "results": results,
            "errors": errors,
        }
        with self._lock:
            self._cache, self._cache_at, self._cache_limit = payload, now, limit
        return payload

    def detail(self, instrument: str) -> dict:
        if not instrument.endswith("_USDT") or not instrument.replace("_", "").isalnum():
            raise ValueError("Invalid USDT instrument")
        scan = self.scan()
        result = next((item for item in scan["results"] if item["instrument"] == instrument), None)
        if result is None:
            tickers = liquid_usdt_tickers(self.client.tickers(), 40)
            ticker = next((item for item in tickers if item["i"] == instrument), None)
            if ticker is None:
                raise MarketDataError("Instrument is unavailable or outside the liquid universe")
            btc_change = next((float(item.get("c") or 0) for item in tickers if item.get("i") == "BTC_USDT"), 0.0)
            result = self._analyze(ticker, btc_change)
            self.journal.record_prediction(result)

        sentiment_summary = self.sentiment.get_market_sentiment_summary(instrument)
        explanation = explain_with_ai(
            result,
            deterministic_explanation(result, sentiment_summary),
            sentiment_summary=sentiment_summary,
        )
        return {
            **result,
            "explanation": explanation,
            "sentiment": sentiment_summary,
            "news": self.sentiment.get_news(limit=6, symbol=instrument),
        }

    def get_sentiment(self, symbol: str | None = None) -> dict:
        """Returns the market-wide or symbol-specific sentiment summary."""
        return self.sentiment.get_market_sentiment_summary(symbol)

    def get_news(self, limit: int = 25, symbol: str | None = None) -> list[dict]:
        """Returns live news articles, optionally filtered by asset."""
        return self.sentiment.get_news(limit=limit, symbol=symbol)

    def update_watchlist(self, instrument: str, enabled: bool) -> list[str]:
        current = set(self.journal.get_watchlist())
        current.add(instrument) if enabled else current.discard(instrument)
        return self.journal.set_watchlist(list(current))

    def queue_paper(self, signal_id: str) -> dict:
        result = next((item for item in self.scan()["results"] if item["signal_id"] == signal_id), None)
        if result is None:
            raise ValueError("Signal is not in the current scan")
        return self.journal.queue_paper_candidate(result)

    def train_model(self, bootstrap_if_empty: bool = True) -> dict:
        """Trains component weights against realized returns and clears scan cache."""
        result = self.trainer.train(bootstrap_if_empty=bootstrap_if_empty)
        with self._lock:
            self._cache = None
            self._cache_at = 0.0
            self._cache_limit = 0
        return result

    def get_model_status(self) -> dict:
        """Returns the current model status and weight configurations."""
        return self.trainer.get_status()

    def optimize_strategy(self, instrument: str = "BTC_USDT") -> dict:
        """Fetches candle history for the instrument and optimizes strategy parameters."""
        try:
            candles_1h = self.client.candles(instrument, "1h", 150)
        except Exception:
            # Fallback if network or instrument fails: try scan candidates
            scan = self.scan()
            instrument = scan["results"][0]["instrument"] if scan["results"] else "BTC_USDT"
            candles_1h = self.client.candles(instrument, "1h", 150)
        return self.optimizer.optimize(candles_1h)

    def get_strategy_params(self) -> dict:
        """Returns the active strategy trading parameters."""
        return self.optimizer.get_status()

