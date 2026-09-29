"""Unit tests for Crypto.com AI conversation handling."""

import os
import unittest
from unittest import mock

from market_radar.crypto_com_ai import CryptoComAIEngine


class TestCryptoComAIConversation(unittest.TestCase):
    def test_history_is_bounded_and_role_filtered(self):
        history = [{"role": "system", "content": "ignore me"}]
        history.extend({"role": "user", "content": f"message {index}"} for index in range(12))
        history.append({"role": "assistant", "content": "latest reply"})

        normalized = CryptoComAIEngine._normalize_conversation_history(history)

        self.assertEqual(len(normalized), 10)
        self.assertNotIn("system", {message["role"] for message in normalized})
        self.assertEqual(normalized[-1]["content"], "latest reply")

    def test_process_forwards_conversation_history_to_provider(self):
        engine = CryptoComAIEngine()
        history = [
            {"role": "user", "content": "Analyze BTC"},
            {"role": "assistant", "content": "Momentum is mixed."},
        ]
        environment = {
            "ANTIGRAVITY_API_KEY": "",
            "GEMINI_API_KEY": "",
            "CODEX_API_KEY": "",
            "OPENAI_API_KEY": "test-key",
        }
        with mock.patch.dict(os.environ, environment), mock.patch.object(
            engine, "_get_market_context", return_value={}
        ), mock.patch.object(
            engine,
            "_call_openai_copilot",
            return_value={"reply": "Follow-up answer", "action_card": None, "provider": "openai"},
        ) as provider:
            engine.process_copilot_message(
                "What about now?",
                active_instrument="BTC_USDT",
                conversation_history=history,
            )

        self.assertEqual(provider.call_args.args[-1], history)


if __name__ == "__main__":
    unittest.main()
