import unittest
from unittest.mock import patch, MagicMock

from market_radar.sentiment import RadarSentimentClient
from market_radar.scoring import deterministic_explanation
from market_radar.ai import explain_with_ai


class SentimentTests(unittest.TestCase):
    def setUp(self):
        self.client = RadarSentimentClient()

    def test_score_text_bullish(self):
        tag, score = self.client._score_text("Bitcoin surges to new record high with massive institutional inflows")
        self.assertEqual(tag, "bullish")
        self.assertGreater(score, 0.0)

    def test_score_text_bearish(self):
        tag, score = self.client._score_text("Crypto crash triggers major liquidations as SEC lawsuit expands")
        self.assertEqual(tag, "bearish")
        self.assertLess(score, 0.0)

    def test_score_text_neutral(self):
        tag, score = self.client._score_text("Federal Reserve holds interest rate meeting on Wednesday")
        self.assertEqual(tag, "neutral")
        self.assertEqual(score, 0.0)

    def test_extract_symbols(self):
        symbols = self.client._extract_symbols("Ethereum and Solana outperform Bitcoin amid Cronos update")
        self.assertIn("ETH", symbols)
        self.assertIn("SOL", symbols)
        self.assertIn("BTC", symbols)
        self.assertIn("CRO", symbols)

    @patch("urllib.request.urlopen")
    def test_fear_and_greed_fetching_and_fallback(self, mock_urlopen):
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = b'{"data": [{"value": "68", "value_classification": "Greed", "timestamp": "1700000000"}]}'
        mock_urlopen.return_value = mock_response

        # Use new client to test un-cached fetch
        client = RadarSentimentClient()
        res = client.get_fear_and_greed(force=True)
        self.assertEqual(res["value"], 68)
        self.assertEqual(res["classification"], "Greed")
        self.assertEqual(res["status"], "ok")

    @patch("urllib.request.urlopen")
    def test_rss_news_parsing(self, mock_urlopen):
        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>CoinTelegraph</title>
            <item>
              <title>Bitcoin surges as ETF approvals multiply</title>
              <link>https://example.com/btc-surge</link>
              <pubDate>Mon, 14 Sep 2026 00:00:00 +0000</pubDate>
              <description>Massive inflows into spot Bitcoin funds.</description>
            </item>
            <item>
              <title>Solana network upgrade successfully deployed</title>
              <link>https://example.com/sol-upgrade</link>
              <pubDate>Sun, 13 Sep 2026 12:00:00 +0000</pubDate>
              <description>Performance enhancements go live.</description>
            </item>
          </channel>
        </rss>"""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = rss_xml
        mock_urlopen.return_value = mock_response

        client = RadarSentimentClient()
        news = client.get_news(force=True)
        self.assertEqual(len(news), 2)
        self.assertEqual(news[0]["sentiment_tag"], "bullish")
        self.assertIn("BTC", news[0]["symbols"])

        # Test filtering by symbol
        btc_news = client.get_news(symbol="BTC_USDT")
        self.assertEqual(len(btc_news), 1)
        self.assertIn("BTC", btc_news[0]["symbols"])

    def test_sentiment_summary_structure(self):
        client = RadarSentimentClient()
        # Mock caches directly to avoid live web calls in this test
        client._fng_cache = {"value": 65, "classification": "Greed", "status": "ok"}
        client._fng_cache_at = 9999999999.0
        client._news_cache = [
            {"title": "BTC rally continues", "sentiment_tag": "bullish", "sentiment_score": 0.6, "symbols": ["BTC"], "link": "#", "published_at": "", "source": "Test"},
            {"title": "Altcoin breakout", "sentiment_tag": "bullish", "sentiment_score": 0.4, "symbols": ["ETH"], "link": "#", "published_at": "", "source": "Test"},
        ]
        client._news_cache_at = 9999999999.0

        summary = client.get_market_sentiment_summary("BTC")
        self.assertIn("composite_score", summary)
        self.assertIn("sentiment_label", summary)
        self.assertIn("fear_and_greed", summary)
        self.assertGreater(summary["composite_score"], 50)

    def test_explanations_with_sentiment(self):
        result = {
            "symbol": "BTC/USDT",
            "score": 82.5,
            "rating": "strong",
            "components": {"trend": 85.0, "momentum": 80.0, "liquidity": 90.0, "volatility": 70.0, "relative_strength": 75.0},
            "flags": [],
        }
        sentiment_summary = {
            "composite_score": 68.0,
            "sentiment_label": "Bullish Greed (68/100) · 2 positive catalysts",
            "recent_headlines": [{"title": "Bitcoin surges past key level"}],
        }
        expl = deterministic_explanation(result, sentiment_summary)
        self.assertEqual(expl["sentiment"], 68.0)
        self.assertIn("Bullish Greed", expl["sentiment_label"])
        self.assertIn("Bitcoin surges", expl["catalysts"][0])

        ai_expl = explain_with_ai(result, expl, sentiment_summary)
        self.assertIn("sentiment", ai_expl)
        self.assertEqual(ai_expl["sentiment"], 68.0)


if __name__ == "__main__":
    unittest.main()
