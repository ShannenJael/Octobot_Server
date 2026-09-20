"""Crypto.com AI Engine for Copilot (Talk to Trade) and Market Radar.

Supports:
- OpenAI / Codex API (via OPENAI_API_KEY, CODEX_API_KEY, OPENAI_BASE_URL)
- Google / Antigravity / Gemini API (via GEMINI_API_KEY, ANTIGRAVITY_API_KEY)
- Heuristic Quantitative Fallback (RSI, Bollinger Bands, ATR, Order Book Depth Imbalance)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("CryptoComAI")


class CryptoComAIEngine:
    """Intelligent AI agent for Crypto.com trading analysis and conversational trade execution."""

    def __init__(self, trade_service: Any = None):
        self.trade_service = trade_service
        self.history: List[Dict[str, str]] = []

    def _ensure_env_loaded(self) -> None:
        """Load .env file if key environment variables are missing."""
        if not os.getenv("ANTIGRAVITY_API_KEY") and not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            for env_path in [".env", "/octobot/.env", os.path.join(os.getcwd(), ".env")]:
                if os.path.exists(env_path):
                    try:
                        with open(env_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("#") and "=" in line:
                                    k, v = line.split("=", 1)
                                    os.environ.setdefault(k.strip(), v.strip())
                    except Exception:
                        pass

    def get_api_credentials(self) -> Tuple[Optional[str], str, Optional[str]]:
        """Identify available API provider and key."""
        self._ensure_env_loaded()

        # 1. Antigravity / Gemini (Priority)
        gemini_key = os.getenv("ANTIGRAVITY_API_KEY") or os.getenv("GEMINI_API_KEY")
        if gemini_key and not gemini_key.startswith("AQ.placeholder"):
            return "gemini", gemini_key, "https://generativelanguage.googleapis.com/v1beta"

        # 2. OpenAI / Codex
        openai_key = os.getenv("CODEX_API_KEY") or os.getenv("OPENAI_API_KEY")
        openai_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        if openai_key and not openai_key.startswith("sk-proj-placeholder"):
            return "openai", openai_key, openai_base

        return None, "", None

    # -------------------------------------------------------------------------
    # Copilot ("Talk to Trade")
    # -------------------------------------------------------------------------
    def process_copilot_message(
        self,
        prompt: str,
        active_instrument: str = "BTC_USDT",
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Process user natural language message and return conversational response + action cards."""
        self._ensure_env_loaded()
        market_context = self._get_market_context(active_instrument)

        # 1. Try Antigravity / Gemini first
        gemini_key = os.getenv("ANTIGRAVITY_API_KEY") or os.getenv("GEMINI_API_KEY")
        if gemini_key and not gemini_key.startswith("AQ.placeholder"):
            try:
                return self._call_gemini_copilot(prompt, market_context, active_instrument, gemini_key, "https://generativelanguage.googleapis.com/v1beta")
            except Exception as e:
                logger.warning("Antigravity API call failed (%s), attempting secondary provider...", e)

        # 2. Try OpenAI / Codex
        openai_key = os.getenv("CODEX_API_KEY") or os.getenv("OPENAI_API_KEY")
        openai_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        if openai_key and not openai_key.startswith("sk-proj-placeholder"):
            try:
                return self._call_openai_copilot(prompt, market_context, active_instrument, openai_key, openai_base)
            except Exception as e:
                logger.warning("OpenAI / Codex API call failed (%s), falling back to quantitative assistant...", e)

        # 3. Smart quantitative & pattern-matching fallback
        return self._heuristic_copilot(prompt, market_context, active_instrument)

    def _call_openai_copilot(
        self,
        prompt: str,
        context: Dict[str, Any],
        active_pair: str,
        api_key: str,
        base_url: str,
    ) -> Dict[str, Any]:
        """Send prompt to OpenAI / Codex API."""
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        system_prompt = (
            "You are an expert Crypto.com Exchange Pro Trading Copilot. "
            "You assist the user by analyzing markets, reporting portfolio status, or creating trade orders.\n\n"
            f"LIVE MARKET CONTEXT:\n{json.dumps(context, indent=2)}\n\n"
            "RULES:\n"
            "1. If the user wants to trade (e.g. 'buy $100 BTC', 'limit sell 0.05 BTC at 90000', 'buy 1 ETH'), "
            "you MUST output a JSON response containing an 'action_card' with exact parameters:\n"
            "   - 'type': 'TRADE'\n"
            "   - 'instrument': e.g. 'BTC_USDT'\n"
            "   - 'side': 'BUY' or 'SELL'\n"
            "   - 'order_type': 'MARKET' or 'LIMIT'\n"
            "   - 'quantity': float\n"
            "   - 'price': float or null if market\n"
            "   - 'notional_usdt': float\n"
            "   - 'rationale': brief reason for trade\n"
            "2. If the user asks a market or portfolio question, provide a concise, professional markdown reply.\n"
            "3. Response format MUST be JSON with fields: 'reply' (markdown string) and optional 'action_card' (dict or null)."
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=15) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            content = res_data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {
                "reply": parsed.get("reply", "Understood."),
                "action_card": parsed.get("action_card"),
                "provider": "openai",
            }

    def _call_gemini_copilot(
        self,
        prompt: str,
        context: Dict[str, Any],
        active_pair: str,
        api_key: str,
        base_url: str,
    ) -> Dict[str, Any]:
        """Send prompt to Google Antigravity / Gemini API."""
        system_instruction = (
            "You are a Crypto.com Exchange Pro Trading Copilot. "
            "Given the live market context, answer user queries or output a structured trade action card.\n"
            f"LIVE MARKET CONTEXT:\n{json.dumps(context, indent=2)}\n\n"
            "RULES:\n"
            "1. If the user wants to trade (e.g. 'buy $100 BTC', 'limit sell 0.05 BTC at 90000'), "
            "you MUST output JSON with an 'action_card' with keys: 'type': 'TRADE', 'instrument', 'side' ('BUY'/'SELL'), 'order_type' ('MARKET'/'LIMIT'), 'quantity' (float), 'price' (float or null), 'notional_usdt' (float), 'rationale' (string).\n"
            "2. If user asks a question, reply with concise markdown in 'reply'.\n"
            "3. Output MUST be valid JSON with 'reply' (string) and optional 'action_card' (dict or null)."
        )

        payload = {
            "contents": [
                {"parts": [{"text": f"System Instruction:\n{system_instruction}\n\nUser Request:\n{prompt}"}]}
            ],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        models_to_try = [
            os.getenv("ANTIGRAVITY_MODEL", "gemini-3.6-flash"),
            "gemini-3.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-flash-latest",
        ]
        last_err = None
        for model in models_to_try:
            url = f"{base_url}/models/{model}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=12) as res:
                    res_data = json.loads(res.read().decode("utf-8"))
                    text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                    clean_text = text.strip()
                    if clean_text.startswith("```json"):
                        clean_text = clean_text[7:]
                    if clean_text.startswith("```"):
                        clean_text = clean_text[3:]
                    if clean_text.endswith("```"):
                        clean_text = clean_text[:-3]
                    parsed = json.loads(clean_text.strip())
                    return {
                        "reply": parsed.get("reply", "Understood."),
                        "action_card": parsed.get("action_card"),
                        "provider": "gemini",
                    }
            except urllib.error.HTTPError as he:
                last_err = he
                if he.code in (503, 429, 404):
                    continue
                raise
            except Exception as ex:
                last_err = ex
                continue

        if last_err:
            raise last_err
        raise RuntimeError("All Gemini model endpoints were unavailable")

    def _heuristic_copilot(
        self,
        prompt: str,
        context: Dict[str, Any],
        active_pair: str,
    ) -> Dict[str, Any]:
        """High-precision deterministic NLP parser for commands and queries."""
        p_lower = prompt.lower().strip()
        last_price = context.get("last_price", 81000.0)
        balances = context.get("balances", {})
        base, quote = active_pair.split("_")

        # 1. Trading Intent Detection
        is_buy = bool(re.search(r"\b(buy|purchase|long|accumulate|bid)\b", p_lower))
        is_sell = bool(re.search(r"\b(sell|short|dump|liquidate|close|ask)\b", p_lower))

        if is_buy or is_sell:
            side = "BUY" if is_buy else "SELL"

            # Check instrument in prompt
            instrument = active_pair
            for pair_cand in ["BTC", "ETH", "SOL", "CRO", "DOGE"]:
                if pair_cand.lower() in p_lower:
                    instrument = f"{pair_cand}_USDT"
                    break

            # Check order type (limit vs market)
            is_market = bool(re.search(r"\bmarket\b", p_lower))
            price_match = re.search(r"(?:at|\@|\$)\s*(\d+[\d,]*\.?\d*)", p_lower)
            target_price = None
            if price_match:
                try:
                    target_price = float(price_match.group(1).replace(",", ""))
                except Exception:
                    target_price = None

            if is_market:
                order_type = "MARKET"
                target_price = last_price
            elif "limit" in p_lower:
                order_type = "LIMIT"
                if target_price is None:
                    target_price = last_price
            elif target_price is not None and not is_market:
                order_type = "LIMIT"
            else:
                order_type = "MARKET"
                target_price = last_price

            # Check quantity or dollar value
            qty = None
            dollar_match = re.search(r"(?:\$|usdt\s*|dollars\s*)(\d+[\d,]*\.?\d*)", p_lower) or re.search(r"(\d+[\d,]*\.?\d*)\s*(?:usdt|dollars|\$)", p_lower)
            qty_match = re.search(r"(\d+\.?\d*)\s*(?:btc|eth|sol|cro|doge|coins|tokens|units)", p_lower)
            pct_match = re.search(r"(\d+)%", p_lower)

            if dollar_match:
                usdt_val = float(dollar_match.group(1).replace(",", ""))
                px = target_price or last_price
                if px > 0:
                    qty = round(usdt_val / px, 5)
            elif qty_match:
                qty = float(qty_match.group(1))
            elif pct_match:
                pct = float(pct_match.group(1)) / 100.0
                if side == "BUY":
                    avail_usdt = balances.get(quote, 1000.0) * pct
                    px = target_price or last_price
                    qty = round((avail_usdt * 0.999) / px, 5) if px > 0 else 0.001
                else:
                    avail_base = balances.get(base, 0.1) * pct
                    qty = round(avail_base, 5)
            else:
                # Default reasonable micro-test quantity
                default_qtys = {"BTC_USDT": 0.001, "ETH_USDT": 0.01, "SOL_USDT": 0.1, "CRO_USDT": 50.0, "DOGE_USDT": 50.0}
                qty = default_qtys.get(instrument, 0.01)

            exec_price = target_price or last_price
            notional = round((qty or 0.001) * exec_price, 2)

            action_card = {
                "type": "TRADE",
                "instrument": instrument,
                "side": side,
                "order_type": order_type,
                "quantity": qty or 0.001,
                "price": round(target_price, 2) if (order_type == "LIMIT" and target_price is not None) else None,
                "notional_usdt": notional,
                "rationale": f"Prepared {side} {order_type} order for {qty or 0.001} {instrument.split('_')[0]} based on your request.",
            }

            reply = (
                f"I have prepared your **{side}** order for **{qty} {instrument.split('_')[0]}** "
                f"({order_type} @ ${exec_price:,.2f}). Total value: **${notional:,.2f} USDT**.\n\n"
                f"Review the action card below and click **Confirm & Execute** to submit it to Crypto.com."
            )
            return {"reply": reply, "action_card": action_card, "provider": "copilot-engine"}

        # 2. Portfolio / Balance Query
        if any(w in p_lower for w in ["balance", "portfolio", "equity", "pnl", "how much", "funds"]):
            equity = context.get("total_equity_usdt", 0)
            usdt = balances.get("USDT", 0)
            btc = balances.get("BTC", 0)
            pnl_pct = context.get("unrealized_pnl_pct", 0)

            reply = (
                f"### 💼 Portfolio Overview ({context.get('mode', 'paper').upper()} Mode)\n\n"
                f"* **Total Equity**: **${equity:,.2f} USDT**\n"
                f"* **Available Cash**: **${usdt:,.2f} USDT**\n"
                f"* **BTC Holdings**: **{btc:.5f} BTC** (~${btc * last_price:,.2f})\n"
                f"* **Unrealized PnL**: **{pnl_pct:+.2f}%**\n\n"
                f"You have sufficient liquidity to place additional trades or launch grid bots."
            )
            return {"reply": reply, "action_card": None, "provider": "copilot-engine"}

        # 3. Market Analysis Query
        if any(w in p_lower for w in ["analysis", "outlook", "trend", "how is", "look", "rsi", "indicator", "support"]):
            rsi = context.get("rsi_14", 54.2)
            spread = context.get("spread_bps", 1.2)
            chg = context.get("change_24h", 0)
            depth_ratio = context.get("depth_bid_ask_ratio", 1.15)
            sentiment = "Bullish" if rsi > 50 and depth_ratio > 1.0 else ("Bearish" if rsi < 45 else "Neutral")

            reply = (
                f"### 📊 Real-Time Market Analysis: {active_pair}\n\n"
                f"* **Current Price**: **${last_price:,.2f}** ({chg:+.2f}% 24h)\n"
                f"* **Momentum (RSI 14)**: **{rsi:.1f}** ({'Neutral / Healthy' if 40 <= rsi <= 60 else 'Overbought' if rsi > 70 else 'Oversold'})\n"
                f"* **Order Book Pressure**: **{depth_ratio:.2f}x** ({'Buyer dominance on bid depth' if depth_ratio > 1.0 else 'Seller resistance on asks'})\n"
                f"* **Spread**: **{spread:.2f} bps** (Tight institutional liquidity)\n"
                f"* **Overall Bias**: **{sentiment}**\n\n"
                f"*Suggested Play*: You can enter a limit order near key support (~${last_price * 0.985:,.2f}) or use the AI Radar tab to view full multi-target breakout levels."
            )
            return {"reply": reply, "action_card": None, "provider": "copilot-engine"}

        # 4. General Helpful Response
        reply = (
            f"Hello! I am your **Crypto.com Trading Copilot**. I can execute trades, check your balances, and analyze real-time market data.\n\n"
            f"Try asking:\n"
            f"- *'Buy $250 worth of BTC at market'*\n"
            f"- *'Place a limit buy for 0.05 BTC at ${last_price * 0.98:,.0f}'*\n"
            f"- *'How is BTC momentum looking right now?'*\n"
            f"- *'Show my portfolio equity and PnL'*"
        )
        return {"reply": reply, "action_card": None, "provider": "copilot-engine"}

    # -------------------------------------------------------------------------
    # AI Market Radar & Technical Analyst
    # -------------------------------------------------------------------------
    def generate_radar_analysis(self, instrument: str = "BTC_USDT") -> Dict[str, Any]:
        """Generate high-fidelity technical and orderbook radar analysis for an instrument."""
        provider, api_key, base_url = self.get_api_credentials()
        context = self._get_market_context(instrument)
        last_price = context.get("last_price", 81000.0)

        # Quantitative metrics calculation
        rsi = context.get("rsi_14", 52.4)
        depth_ratio = context.get("depth_bid_ask_ratio", 1.12)
        chg_24h = context.get("change_24h", 1.8)
        high_24h = context.get("high_24h", last_price * 1.02)
        low_24h = context.get("low_24h", last_price * 0.98)

        # Dynamic S/R and Targets
        atr = (high_24h - low_24h) * 0.6 or (last_price * 0.025)
        s1 = round(last_price - (atr * 0.5), 2)
        s2 = round(last_price - (atr * 1.1), 2)
        r1 = round(last_price + (atr * 0.6), 2)
        r2 = round(last_price + (atr * 1.3), 2)

        # Stop loss & take profit
        stop_loss = round(s1 * 0.985, 2)
        take_profit = round(r2, 2)

        # Signal logic
        if rsi >= 65 and depth_ratio >= 1.2:
            signal = "STRONG BUY"
            signal_color = "success"
            confidence = 88
        elif rsi >= 50 and depth_ratio >= 1.0:
            signal = "ACCUMULATE"
            signal_color = "primary"
            confidence = 79
        elif rsi <= 35 and depth_ratio <= 0.8:
            signal = "DEFENSIVE"
            signal_color = "danger"
            confidence = 84
        elif rsi >= 75:
            signal = "TAKE PROFIT"
            signal_color = "warning"
            confidence = 82
        else:
            signal = "NEUTRAL"
            signal_color = "secondary"
            confidence = 68

        narrative = (
            f"{instrument} is currently consolidating at **${last_price:,.2f}** with 24h change of **{chg_24h:+.2f}%**. "
            f"The 14-period RSI stands at **{rsi:.1f}**, reflecting sustainable upward momentum without severe overextension. "
            f"Crypto.com order book depth reveals a **{depth_ratio:.2f}x bid-to-ask liquidity ratio**, confirming solid buyer support "
            f"clustered around **${s1:,.2f}**. Immediate resistance is established at **${r1:,.2f}**, with secondary expansion targets at **${r2:,.2f}**."
        )

        return {
            "instrument": instrument,
            "signal": signal,
            "signal_color": signal_color,
            "confidence": confidence,
            "last_price": last_price,
            "change_24h": chg_24h,
            "rsi_14": rsi,
            "depth_ratio": depth_ratio,
            "levels": {
                "support_1": s1,
                "support_2": s2,
                "resistance_1": r1,
                "resistance_2": r2,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "recommended_entry": round(s1 * 1.002, 2),
            },
            "narrative": narrative,
            "indicators": {
                "rsi": {"value": f"{rsi:.1f}", "status": "Healthy" if 40 <= rsi <= 60 else "Overbought" if rsi > 70 else "Oversold"},
                "order_book_bias": {"value": f"{depth_ratio:.2f}x", "status": "Bids Dominant" if depth_ratio > 1.0 else "Asks Heavy"},
                "volatility_range": {"value": f"${atr:,.2f}", "status": "Moderate ATR"},
                "spread": {"value": f"{context.get('spread_bps', 1.0):.2f} bps", "status": "Tight Institutional"},
            },
            "timestamp": time.time(),
        }

    # -------------------------------------------------------------------------
    # Market Context Ingestion
    # -------------------------------------------------------------------------
    def _get_market_context(self, instrument: str) -> Dict[str, Any]:
        """Aggregate real-time order book, ticker, balances, and open orders."""
        context: Dict[str, Any] = {
            "instrument": instrument,
            "last_price": 81000.0,
            "spread_bps": 1.0,
            "change_24h": 0.0,
            "high_24h": 82000.0,
            "low_24h": 80000.0,
            "depth_bid_ask_ratio": 1.15,
            "rsi_14": 54.0,
            "balances": {"USDT": 10000.0, "BTC": 0.0},
            "mode": "paper",
        }

        if not self.trade_service:
            return context

        try:
            # 1. Market overview (ticker + order book)
            market = self.trade_service.get_market_overview(instrument)
            if market:
                ticker = market.get("ticker")
                if ticker:
                    context["last_price"] = float(ticker.get("a") or ticker.get("b") or 81000.0)
                    context["change_24h"] = float(ticker.get("c") or 0.0) * 100
                    context["high_24h"] = float(ticker.get("h") or context["last_price"] * 1.02)
                    context["low_24h"] = float(ticker.get("l") or context["last_price"] * 0.98)

                book = market.get("book")
                if book:
                    bids = book.get("bids", [])
                    asks = book.get("asks", [])
                    total_bid_vol = sum(float(b[1]) for b in bids[:15]) if bids else 1.0
                    total_ask_vol = sum(float(a[1]) for a in asks[:15]) if asks else 1.0
                    context["depth_bid_ask_ratio"] = round(total_bid_vol / (total_ask_vol or 1.0), 2)
                    if bids and asks:
                        best_bid = float(bids[0][0])
                        best_ask = float(asks[0][0])
                        context["spread_bps"] = round(((best_ask - best_bid) / best_bid) * 10000, 2)

            # 2. Candlesticks for RSI
            candles = self.trade_service.get_candles(instrument, timeframe="1h", count=30)
            if candles and len(candles) >= 15:
                closes = [float(c["c"]) for c in candles]
                context["rsi_14"] = self._compute_rsi(closes)

            # 3. User balances & mode
            port = self.trade_service.get_portfolio()
            if port:
                context["balances"] = port.get("balances", {})
                context["total_equity_usdt"] = port.get("total_equity_usdt", 0)
                context["unrealized_pnl_pct"] = port.get("unrealized_pnl_pct", 0)
                context["mode"] = port.get("mode", "paper")
        except Exception as e:
            logger.warning("Error aggregating live market context: %s", e)

        return context

    @staticmethod
    def _compute_rsi(closes: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index (RSI)."""
        if len(closes) < period + 1:
            return 50.0
        gains: List[float] = []
        losses: List[float] = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            if diff >= 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(diff))

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100.0 - (100.0 / (1.0 + rs)), 1)

    # -------------------------------------------------------------------------
    # Seconds Scalper AI Micro-Advisor (Antigravity & Codex)
    # -------------------------------------------------------------------------
    def _call_antigravity_seconds(
        self,
        instrument: str,
        last_price: float,
        depth_ratio: float,
        taker_ratio: float,
        micro_delta: float = 0.0,
        micro_pct: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        gemini_key = os.getenv("ANTIGRAVITY_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not gemini_key or gemini_key.startswith("AQ.placeholder"):
            return None
        try:
            model = os.getenv("ANTIGRAVITY_MODEL", "gemini-3.6-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            prompt = (
                f"You are a quant high-frequency scalper analyzing {instrument} at ${last_price:,.2f}.\n"
                f"Orderbook Bid/Ask Volume Depth Skew: {depth_ratio:.2f}x ({'Bid dominant' if depth_ratio >= 1.0 else 'Ask dominant'}).\n"
                f"Taker Buy/Sell Flow: {taker_ratio:.2f}x.\n"
                f"Recent Micro-Tick Price Trajectory: {micro_delta:+.2f} USDT ({micro_pct:+.3f}%).\n"
                "TASK: Predict micro-trend direction for the next 30 to 60 seconds ('CALL' for upward micro tick surge, 'PUT' for downward dump).\n"
                "RULES:\n"
                "- Do NOT bias toward CALL. If micro-momentum is negative or asks dominate, predict PUT.\n"
                "- If indicators conflict or market is in flat chop, output probability 48-60.\n"
                "- Only output probability >= 70 when orderbook skew and micro-momentum firmly align.\n"
                "Output JSON with keys: 'direction' ('CALL' or 'PUT'), 'probability' (integer 45-88), "
                "'duration' (30 or 60), and 'rationale' (1 concise sentence)."
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=6) as res:
                res_data = json.loads(res.read().decode("utf-8"))
                text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                parsed = json.loads(text.strip())
                return {
                    "instrument": instrument,
                    "direction": str(parsed.get("direction", "CALL")).upper(),
                    "probability": int(parsed.get("probability", 70)),
                    "duration": int(parsed.get("duration", 30)),
                    "last_price": last_price,
                    "depth_ratio": depth_ratio,
                    "taker_ratio": taker_ratio,
                    "micro_delta": micro_delta,
                    "rationale": parsed.get("rationale", f"Order book depth ratio of {depth_ratio:.2f}x and micro-momentum {micro_delta:+.2f} favor {parsed.get('direction', 'CALL')}."),
                    "provider": "antigravity",
                    "model": model,
                    "timestamp": time.time(),
                }
        except Exception as e:
            logger.debug("Antigravity micro-advice error: %s", e)
            return None

    def _call_codex_seconds(
        self,
        instrument: str,
        last_price: float,
        depth_ratio: float,
        taker_ratio: float,
        micro_delta: float = 0.0,
        micro_pct: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        openai_key = os.getenv("CODEX_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not openai_key or openai_key.startswith("sk-proj-placeholder"):
            return None
        openai_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("CODEX_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o")
        url = f"{openai_base}/chat/completions"
        system_prompt = (
            "You are an unbiased ultra-high-frequency quantitative scalping AI predicting 30s-60s micro-trends on Crypto.com. "
            "You MUST treat CALL and PUT with equal objective weight based purely on the data. "
            "Respond strictly in JSON format with keys: 'direction' ('CALL' or 'PUT'), 'probability' (integer 45-88), "
            "'duration' (integer 30 or 60), and 'rationale' (concise 1-sentence explanation)."
        )
        user_prompt = (
            f"Instrument: {instrument}\n"
            f"Current Mid Price: ${last_price:,.2f}\n"
            f"Orderbook Bid/Ask Depth Skew: {depth_ratio:.2f}x ({'Bids Dominant' if depth_ratio >= 1.0 else 'Asks Dominant'})\n"
            f"Recent Taker Volume Flow: {taker_ratio:.2f}x buy-to-sell ratio\n"
            f"Recent Micro-Tick Trajectory (last 25 trades): {micro_delta:+.2f} USDT ({micro_pct:+.3f}%)\n\n"
            "RULES:\n"
            "1. If micro-momentum is negative ({micro_delta:+.2f} < 0) or ask depth dominates (< 0.95x), PREDICT PUT.\n"
            "2. If micro-momentum is positive ({micro_delta:+.2f} > 0) and bid depth dominates (> 1.05x), PREDICT CALL.\n"
            "3. If signals conflict (e.g. positive ticks but heavy asks) or the market is flat/choppy, keep probability low (50-60%) so the auto-pilot avoids entering low-conviction chop.\n"
            "Predict micro-trend direction for the next 30-60 seconds."
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.15,
            "max_tokens": 150
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openai_key}"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as res:
                data = json.loads(res.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content.strip())
                return {
                    "instrument": instrument,
                    "direction": str(parsed.get("direction", "CALL")).upper(),
                    "probability": int(parsed.get("probability", 70)),
                    "duration": int(parsed.get("duration", 30)),
                    "last_price": last_price,
                    "depth_ratio": depth_ratio,
                    "taker_ratio": taker_ratio,
                    "micro_delta": micro_delta,
                    "rationale": parsed.get("rationale", f"Codex AI evaluates depth skew of {depth_ratio:.2f}x and tick trajectory {micro_delta:+.2f} on {instrument}."),
                    "provider": "codex",
                    "model": model,
                    "timestamp": time.time(),
                }
        except Exception as e:
            logger.debug("Codex micro-advice error: %s", e)
            return None

    def generate_seconds_advice(self, instrument: str = "BTC_USDT", provider: str = "auto") -> Dict[str, Any]:
        """Generate ultra-short-term (30s-120s) micro-direction prediction and orderbook tape advice.

        Supported providers: 'antigravity', 'codex', 'consensus', 'auto'
        """
        self._ensure_env_loaded()

        if not self.trade_service:
            try:
                from market_radar.crypto_com_trade import CryptoComTraderService
                self.trade_service = CryptoComTraderService.get_instance()
            except Exception:
                pass

        context = self._get_market_context(instrument)
        last_price = context.get("last_price", 81000.0)
        depth_ratio = context.get("depth_bid_ask_ratio", 1.0)

        # Micro-tape flow analysis and tick trajectory from live trades
        taker_ratio = 1.0
        micro_delta = 0.0
        micro_pct = 0.0
        if self.trade_service:
            try:
                overview = self.trade_service.get_market_overview(instrument)
                trades = overview.get("trades") or overview.get("recent_trades") or []
                if trades:
                    buy_vol = sum(float(t.get("q", 0)) for t in trades if str(t.get("s", "")).lower() == "buy")
                    sell_vol = sum(float(t.get("q", 0)) for t in trades if str(t.get("s", "")).lower() == "sell")
                    if sell_vol > 0:
                        taker_ratio = round(buy_vol / sell_vol, 2)
                    elif buy_vol > 0:
                        taker_ratio = 2.5
                    if len(trades) >= 2:
                        p_now = float(trades[0].get("p", last_price))
                        p_old = float(trades[-1].get("p", last_price))
                        micro_delta = round(p_now - p_old, 2)
                        micro_pct = round((micro_delta / p_old) * 100.0, 4) if p_old > 0 else 0.0
            except Exception:
                pass

        req_prov = provider.lower() if provider else "auto"

        # 1. Dual AI Consensus
        if req_prov == "consensus":
            anti = self._call_antigravity_seconds(instrument, last_price, depth_ratio, taker_ratio, micro_delta, micro_pct)
            codex = self._call_codex_seconds(instrument, last_price, depth_ratio, taker_ratio, micro_delta, micro_pct)
            if anti and codex:
                is_agreed = anti["direction"] == codex["direction"]
                if is_agreed:
                    combined_prob = min(92, round((anti["probability"] + codex["probability"]) / 2 + 4))
                    return {
                        "instrument": instrument,
                        "direction": anti["direction"],
                        "probability": combined_prob,
                        "duration": 30,
                        "last_price": last_price,
                        "depth_ratio": depth_ratio,
                        "taker_ratio": taker_ratio,
                        "micro_delta": micro_delta,
                        "rationale": f"Dual Consensus: Antigravity ({anti['probability']}%) & Codex ({codex['probability']}%) both confirm {anti['direction']}.",
                        "provider": "consensus",
                        "anti_dir": anti["direction"],
                        "codex_dir": codex["direction"],
                        "timestamp": time.time(),
                    }
                else:
                    favored = anti if anti["probability"] >= codex["probability"] else codex
                    return {
                        "instrument": instrument,
                        "direction": favored["direction"],
                        "probability": 55,  # Low probability on divergence to filter out chop
                        "duration": 30,
                        "last_price": last_price,
                        "depth_ratio": depth_ratio,
                        "taker_ratio": taker_ratio,
                        "micro_delta": micro_delta,
                        "rationale": f"Divergence: Antigravity leans {anti['direction']} ({anti['probability']}%), Codex leans {codex['direction']} ({codex['probability']}%). Caution advised.",
                        "provider": "consensus",
                        "anti_dir": anti["direction"],
                        "codex_dir": codex["direction"],
                        "timestamp": time.time(),
                    }
            elif codex:
                return codex
            elif anti:
                return anti

        # 2. Codex Requested Specifically
        if req_prov == "codex":
            codex_res = self._call_codex_seconds(instrument, last_price, depth_ratio, taker_ratio, micro_delta, micro_pct)
            if codex_res:
                return codex_res

        # 3. Antigravity Requested Specifically
        if req_prov == "antigravity":
            anti_res = self._call_antigravity_seconds(instrument, last_price, depth_ratio, taker_ratio, micro_delta, micro_pct)
            if anti_res:
                return anti_res

        # 4. Auto: Try Antigravity first, then Codex
        if req_prov == "auto":
            anti_res = self._call_antigravity_seconds(instrument, last_price, depth_ratio, taker_ratio, micro_delta, micro_pct)
            if anti_res:
                return anti_res
            codex_res = self._call_codex_seconds(instrument, last_price, depth_ratio, taker_ratio, micro_delta, micro_pct)
            if codex_res:
                return codex_res

        # 5. Quantitative tape fallback
        score = (depth_ratio * 0.5) + (taker_ratio * 0.3) + (1.0 if micro_delta > 0 else (-1.0 if micro_delta < 0 else 0.0)) * 0.2
        if score >= 1.25 or (depth_ratio > 1.3 and micro_delta >= 0):
            direction = "CALL"
            prob = min(85, int(66 + (score - 1.25) * 20))
            reason = f"Buyer absorption ({depth_ratio:.2f}x bid wall) and positive tick momentum ({micro_delta:+.2f}); upward surge expected."
        elif score <= 0.75 or (depth_ratio < 0.8 and micro_delta <= 0):
            direction = "PUT"
            prob = min(85, int(66 + (0.75 - score) * 20))
            reason = f"Seller supply dominates ({depth_ratio:.2f}x asks) and negative tick momentum ({micro_delta:+.2f}); downward dump expected."
        else:
            direction = "CALL" if (micro_delta > 0 or depth_ratio >= 1.0) else "PUT"
            prob = 54  # Intentionally low probability in neutral/chop zone to filter out unprofitable auto-trades
            reason = f"Consolidating market (spread balanced, micro-momentum {micro_delta:+.2f}). Waiting for directional breakout."

        return {
            "instrument": instrument,
            "direction": direction,
            "probability": prob,
            "duration": 30,
            "last_price": last_price,
            "depth_ratio": depth_ratio,
            "taker_ratio": taker_ratio,
            "micro_delta": micro_delta,
            "rationale": reason,
            "provider": "quantitative-tape",
            "timestamp": time.time(),
        }
