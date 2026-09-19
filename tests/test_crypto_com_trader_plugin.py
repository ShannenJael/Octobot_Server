"""Tests for CryptoComTraderPlugin registration and endpoints."""

import unittest
try:
    from tentacles.Services.Interfaces.web_interface.plugins.crypto_com_trader_plugin import (
        CryptoComTraderPlugin,
    )
    HAS_TENTACLES = True
except ImportError:
    HAS_TENTACLES = False


@unittest.skipUnless(HAS_TENTACLES, "octobot tentacles packages not installed in local environment")
class TestCryptoComTraderPlugin(unittest.TestCase):
    def test_plugin_instantiation_and_tabs(self):
        plugin = CryptoComTraderPlugin.factory()
        self.assertEqual(plugin.NAME, "crypto_com_trader")
        self.assertEqual(plugin.URL_PREFIX, "/crypto-com")

        tabs = plugin.get_tabs()
        self.assertEqual(len(tabs), 1)
        self.assertEqual(tabs[0].tab_id, "crypto_com_trader")
        self.assertEqual(tabs[0].title, "Crypto.com Trader")

    def test_blueprint_and_routes_registered(self):
        plugin = CryptoComTraderPlugin.factory()
        blueprint = plugin.blueprint_factory()
        plugin.register_routes()
        self.assertIsNotNone(blueprint)


if __name__ == "__main__":
    unittest.main()
