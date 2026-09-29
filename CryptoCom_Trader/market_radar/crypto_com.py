"""Small, dependency-free client for Crypto.com's public REST market data."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request


class MarketDataError(RuntimeError):
    pass


class CryptoComPublicClient:
    BASE_URL = "https://api.crypto.com/exchange/v1"

    def __init__(self, timeout: float = 10.0, retries: int = 2):
        self.timeout = timeout
        self.retries = retries

    def _get(self, method: str, params: dict | None = None) -> dict:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.BASE_URL}/{method}" + (f"?{query}" if query else "")
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                request = urllib.request.Request(
                    url,
                    headers={"Accept": "application/json", "User-Agent": "OctoBot-Market-Radar/1.0"},
                )
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.load(response)
                if payload.get("code") != 0:
                    raise MarketDataError(f"Crypto.com returned code {payload.get('code')}")
                return payload.get("result") or {}
            except (OSError, ValueError, urllib.error.URLError, MarketDataError) as error:
                last_error = error
                if attempt < self.retries:
                    time.sleep(0.3 * (2**attempt))
        raise MarketDataError(f"Crypto.com public market data unavailable: {last_error}")

    def tickers(self) -> list[dict]:
        return list(self._get("public/get-tickers").get("data") or [])

    def candles(self, instrument: str, timeframe: str, count: int = 100) -> list[dict]:
        result = self._get(
            "public/get-candlestick",
            {"instrument_name": instrument, "timeframe": timeframe, "count": count},
        )
        candles = list(result.get("data") or [])
        candles.sort(key=lambda candle: int(candle.get("t", 0)))
        return candles


def liquid_usdt_tickers(tickers: list[dict], limit: int = 15) -> list[dict]:
    """Return liquid spot USDT markets, excluding stable/stable and derivatives."""
    stable_bases = {"USDC", "DAI", "TUSD", "FDUSD", "PYUSD", "EUR", "USD"}
    candidates = []
    for ticker in tickers:
        instrument = str(ticker.get("i", ""))
        if not instrument.endswith("_USDT") or "-PERP" in instrument:
            continue
        base = instrument.removesuffix("_USDT")
        if base in stable_bases:
            continue
        try:
            last = float(ticker.get("a") or 0)
            quote_volume = float(ticker.get("vv") or 0)
            bid = float(ticker.get("b") or 0)
            ask = float(ticker.get("k") or 0)
        except (TypeError, ValueError):
            continue
        if last <= 0 or quote_volume <= 0 or bid <= 0 or ask <= 0:
            continue
        normalized = dict(ticker)
        normalized.update(last=last, quote_volume=quote_volume, bid=bid, ask=ask)
        candidates.append(normalized)
    candidates.sort(key=lambda item: item["quote_volume"], reverse=True)
    return candidates[: max(1, min(limit, 40))]
