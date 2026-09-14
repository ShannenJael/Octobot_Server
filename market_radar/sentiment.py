"""Multi-source sentiment and live news ingestor for Market Radar."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

# High-frequency keywords for crypto market sentiment
BULLISH_KEYWORDS = {
    "surge", "surges", "surging", "rally", "rallies", "rallying",
    "breakout", "breaks out", "ath", "all-time high", "all time high",
    "bull", "bullish", "approval", "approved", "partnership", "adoption",
    "inflows", "soars", "jumps", "climbs", "upgrade", "accumulate", "gain",
    "gains", "green", "momentum", "record high", "milestone", "expansion"
}

BEARISH_KEYWORDS = {
    "crash", "crashes", "crashing", "plunge", "plunges", "plunging",
    "dump", "dumps", "dumping", "drop", "drops", "slump", "slumps",
    "bear", "bearish", "lawsuit", "sues", "sec", "ban", "bans", "banned",
    "hack", "hacked", "exploit", "exploited", "liquidation", "liquidated",
    "outflows", "scam", "fraud", "collapse", "rejection", "rejected",
    "selloff", "fud", "investigation", "probe", "bankrupt", "insolvent"
}

ASSET_ALIASES: dict[str, set[str]] = {
    "BTC": {"btc", "bitcoin"},
    "ETH": {"eth", "ethereum", "ether"},
    "SOL": {"sol", "solana"},
    "CRO": {"cro", "cronos", "crypto.com"},
    "BNB": {"bnb", "binance"},
    "XRP": {"xrp", "ripple"},
    "ADA": {"ada", "cardano"},
    "DOGE": {"doge", "dogecoin"},
    "AVAX": {"avax", "avalanche"},
    "DOT": {"dot", "polkadot"},
    "NEAR": {"near"},
    "SUI": {"sui"},
    "LINK": {"link", "chainlink"},
    "PEPE": {"pepe"},
    "SHIB": {"shib", "shiba"},
}


class RadarSentimentClient:
    """Ingests Crypto Fear & Greed index and live crypto headlines with zero required keys."""

    FNG_URL = "https://api.alternative.me/fng/?limit=1"
    RSS_FEEDS = (
        ("CoinTelegraph", "https://cointelegraph.com/rss"),
    )

    def __init__(self):
        self._lock = threading.Lock()
        self._fng_cache: dict[str, Any] | None = None
        self._fng_cache_at: float = 0.0
        self._news_cache: list[dict[str, Any]] = []
        self._news_cache_at: float = 0.0
        self.fng_cache_ttl = 1800  # 30 minutes
        self.news_cache_ttl = 300   # 5 minutes

    def get_fear_and_greed(self, force: bool = False) -> dict[str, Any]:
        """Fetches the Alternative.me Fear & Greed Index with fallback."""
        now = time.time()
        with self._lock:
            if not force and self._fng_cache and (now - self._fng_cache_at < self.fng_cache_ttl):
                return self._fng_cache

        try:
            req = urllib.request.Request(
                self.FNG_URL,
                headers={"User-Agent": "OctoBot-MarketRadar/1.0", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)

            entry = data.get("data", [{}])[0]
            val = int(entry.get("value", 50))
            classification = str(entry.get("value_classification", "Neutral"))
            timestamp = int(entry.get("timestamp", int(now)))

            result = {
                "value": val,
                "classification": classification,
                "timestamp": timestamp,
                "status": "ok",
                "source": "Alternative.me",
            }
            with self._lock:
                self._fng_cache = result
                self._fng_cache_at = now
            return result
        except Exception as err:
            fallback = {
                "value": 50,
                "classification": "Neutral",
                "timestamp": int(now),
                "status": "fallback",
                "error": type(err).__name__,
                "source": "Alternative.me (Cached/Neutral)",
            }
            if self._fng_cache:
                return self._fng_cache
            return fallback

    def _score_text(self, text: str) -> tuple[str, float]:
        """Computes keyword sentiment tag and numeric polarity score in [-1.0, 1.0]."""
        words = re.findall(r"\b[a-zA-Z0-9\-\']+\b", text.lower())
        bull_count = sum(1 for w in words if w in BULLISH_KEYWORDS)
        bear_count = sum(1 for w in words if w in BEARISH_KEYWORDS)

        delta = bull_count - bear_count
        if delta > 0:
            tag = "bullish"
            score = round(min(1.0, 0.3 + delta * 0.2), 2)
        elif delta < 0:
            tag = "bearish"
            score = round(max(-1.0, -0.3 + delta * 0.2), 2)
        else:
            tag = "neutral"
            score = 0.0

        return tag, score

    def _extract_symbols(self, text: str) -> list[str]:
        """Extracts relevant crypto symbols from headline text."""
        lowered = text.lower()
        matched = []
        for symbol, aliases in ASSET_ALIASES.items():
            for alias in aliases:
                if re.search(rf"\b{re.escape(alias)}\b", lowered):
                    matched.append(symbol)
                    break
        return matched

    def get_news(self, limit: int = 25, symbol: str | None = None, force: bool = False) -> list[dict[str, Any]]:
        """Fetches live news headlines from RSS / CryptoPanic, parsed and sentiment-tagged."""
        now = time.time()
        with self._lock:
            cached_valid = not force and self._news_cache and (now - self._news_cache_at < self.news_cache_ttl)

        if not cached_valid:
            articles = []
            # 1. Fetch from RSS Feeds
            for source_name, url in self.RSS_FEEDS:
                try:
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OctoBot-MarketRadar/1.0"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        content = resp.read()

                    root = ET.fromstring(content)
                    items = root.findall(".//item")
                    for item in items[:30]:
                        title = item.find("title").text if item.find("title") is not None else ""
                        link = item.find("link").text if item.find("link") is not None else ""
                        pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                        desc = item.find("description").text if item.find("description") is not None else ""

                        clean_title = re.sub(r"<[^>]+>", "", title or "").strip()
                        clean_desc = re.sub(r"<[^>]+>", "", desc or "").strip()
                        full_text = f"{clean_title} {clean_desc}"

                        tag, score = self._score_text(full_text)
                        symbols = self._extract_symbols(full_text)

                        articles.append({
                            "title": clean_title,
                            "link": link,
                            "published_at": pub_date,
                            "source": source_name,
                            "sentiment_tag": tag,
                            "sentiment_score": score,
                            "symbols": symbols,
                        })
                except Exception:
                    pass

            # 2. CryptoPanic integration if key is set
            cryptopanic_key = os.getenv("CRYPTOPANIC_API_KEY")
            if cryptopanic_key:
                try:
                    panic_url = f"https://cryptopanic.com/api/v1/posts/?auth_token={cryptopanic_key}&public=true"
                    req = urllib.request.Request(panic_url, headers={"User-Agent": "OctoBot-MarketRadar/1.0"})
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        panic_data = json.load(resp)
                    for post in panic_data.get("results", [])[:20]:
                        title = post.get("title", "")
                        link = post.get("url", "")
                        pub = post.get("published_at", "")
                        tag, score = self._score_text(title)
                        symbols = [c.get("code") for c in post.get("currencies", []) if c.get("code")]
                        articles.append({
                            "title": title,
                            "link": link,
                            "published_at": pub,
                            "source": "CryptoPanic",
                            "sentiment_tag": tag,
                            "sentiment_score": score,
                            "symbols": symbols,
                        })
                except Exception:
                    pass

            with self._lock:
                if articles:
                    self._news_cache = articles
                    self._news_cache_at = now

        with self._lock:
            all_articles = list(self._news_cache)

        # Filter by symbol if specified
        if symbol:
            target_sym = symbol.replace("_USDT", "").replace("/", "").upper()
            filtered = [
                a for a in all_articles
                if target_sym in a["symbols"] or target_sym.lower() in a["title"].lower()
            ]
            return filtered[:limit]

        return all_articles[:limit]

    def get_market_sentiment_summary(self, symbol: str | None = None) -> dict[str, Any]:
        """Combines Fear & Greed with recent headline sentiment into an advisory summary."""
        fng = self.get_fear_and_greed()
        news = self.get_news(limit=25, symbol=symbol)

        bullish_news = sum(1 for n in news if n["sentiment_tag"] == "bullish")
        bearish_news = sum(1 for n in news if n["sentiment_tag"] == "bearish")
        neutral_news = sum(1 for n in news if n["sentiment_tag"] == "neutral")
        total_news = len(news)

        if total_news > 0:
            avg_polarity = sum(n["sentiment_score"] for n in news) / total_news
            news_score = round(50.0 + avg_polarity * 40.0, 1)
        else:
            news_score = float(fng["value"])

        composite_score = round(0.5 * fng["value"] + 0.5 * news_score, 1)

        if composite_score >= 70:
            sentiment_label = f"Bullish Greed ({composite_score}/100)"
        elif composite_score >= 55:
            sentiment_label = f"Moderately Bullish ({composite_score}/100)"
        elif composite_score <= 30:
            sentiment_label = f"Extreme Fear ({composite_score}/100)"
        elif composite_score <= 45:
            sentiment_label = f"Cautious / Bearish ({composite_score}/100)"
        else:
            sentiment_label = f"Neutral ({composite_score}/100)"

        if bullish_news > bearish_news and bullish_news > 0:
            sentiment_label += f" · {bullish_news} positive headlines"
        elif bearish_news > bullish_news and bearish_news > 0:
            sentiment_label += f" · {bearish_news} negative headlines"

        return {
            "composite_score": composite_score,
            "sentiment_label": sentiment_label,
            "fear_and_greed": fng,
            "news_summary": {
                "total_headlines": total_news,
                "bullish_count": bullish_news,
                "bearish_count": bearish_news,
                "neutral_count": neutral_news,
            },
            "recent_headlines": news[:6],
        }
