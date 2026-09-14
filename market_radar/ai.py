"""Optional structured AI commentary; deterministic scoring remains authoritative."""

from __future__ import annotations

import json
import os
import urllib.request


def explain_with_ai(result: dict, fallback: dict, sentiment_summary: dict | None = None) -> dict:
    if os.getenv("MARKET_RADAR_AI_ENABLED", "false").lower() != "true":
        return fallback
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {**fallback, "status": "unavailable", "ai_error": "OPENAI_API_KEY is not configured"}
    safe_snapshot = {
        key: result[key]
        for key in (
            "symbol", "score", "rating", "change_24h", "spread_bps", "rsi_14",
            "return_6h", "return_24h", "hourly_volatility", "risk_penalty", "components", "flags",
        )
    }
    if sentiment_summary:
        safe_snapshot["market_sentiment"] = {
            "composite_score": sentiment_summary.get("composite_score"),
            "sentiment_label": sentiment_summary.get("sentiment_label"),
            "fear_and_greed": sentiment_summary.get("fear_and_greed", {}).get("classification"),
            "recent_headlines": [h.get("title") for h in sentiment_summary.get("recent_headlines", [])[:4]],
        }

    payload = {
        "model": os.getenv("MARKET_RADAR_AI_MODEL", "gpt-5-mini"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "Explain the supplied numeric crypto research signal and verified news sentiment. "
                    "Do not recommend buying or selling, invent unverified news, predict certainty, change the score, "
                    "or provide order parameters. Synthesize whether technical indicators align with recent market sentiment. "
                    "Return JSON with summary (string), risks (array of strings), catalysts (array of strings), "
                    "sentiment (number or null), and sentiment_label (string)."
                ),
            },
            {"role": "user", "content": json.dumps(safe_snapshot, separators=(",", ":"))},
        ],
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.load(response)
        explanation = json.loads(body["choices"][0]["message"]["content"])
        sentiment_val = explanation.get("sentiment")
        if sentiment_val is None and sentiment_summary:
            sentiment_val = sentiment_summary.get("composite_score")

        sentiment_lbl = explanation.get("sentiment_label")
        if not sentiment_lbl and sentiment_summary:
            sentiment_lbl = sentiment_summary.get("sentiment_label")

        catalysts = [str(c) for c in explanation.get("catalysts", [])][:4]
        if not catalysts and sentiment_summary:
            catalysts = [h.get("title") for h in sentiment_summary.get("recent_headlines", [])[:3]]

        return {
            "status": "ai",
            "summary": str(explanation["summary"]),
            "risks": [str(value) for value in explanation.get("risks", [])][:6],
            "catalysts": catalysts,
            "sentiment": sentiment_val,
            "sentiment_label": str(sentiment_lbl or "Neutral"),
            "disclaimer": fallback["disclaimer"],
        }
    except Exception as error:  # fail closed to the deterministic explanation
        return {**fallback, "status": "fallback", "ai_error": type(error).__name__}
