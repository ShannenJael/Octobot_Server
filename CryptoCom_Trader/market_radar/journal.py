"""Append-only prediction/outcome journal and explicit paper-candidate queue."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path


class RadarJournal:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.getenv("MARKET_RADAR_DATA_DIR", "user/market_radar"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "prediction_events.jsonl"
        self.watchlist_path = self.root / "watchlist.json"
        self.paper_path = self.root / "paper_candidates.jsonl"
        self._lock = threading.Lock()

    def _append(self, path: Path, event: dict) -> None:
        line = json.dumps(event, separators=(",", ":"), sort_keys=True)
        with self._lock, path.open("a", encoding="utf-8") as output:
            output.write(line + "\n")

    def record_prediction(self, result: dict) -> None:
        seen = set()
        if self.events_path.exists():
            with self.events_path.open(encoding="utf-8") as events:
                for line in events:
                    try:
                        event = json.loads(line)
                        if event.get("type") == "prediction":
                            seen.add(event.get("signal_id"))
                    except (ValueError, OSError):
                        continue
        if result["signal_id"] not in seen:
            self._append(self.events_path, {"type": "prediction", "recorded_at": int(time.time()), **result})

    def record_outcome(self, signal_id: str, horizon_hours: int, realized_return_pct: float) -> None:
        self._append(
            self.events_path,
            {
                "type": "outcome",
                "signal_id": signal_id,
                "horizon_hours": horizon_hours,
                "realized_return_pct": round(realized_return_pct, 5),
                "recorded_at": int(time.time()),
            },
        )

    def resolve_due_outcomes(self, current_prices: dict[str, float], now: int | None = None) -> int:
        """Append each due 4h/24h/72h outcome once using current public prices."""
        now = now or int(time.time())
        events = self.recent_events(10000)
        completed = {
            (event.get("signal_id"), event.get("horizon_hours"))
            for event in events
            if event.get("type") == "outcome"
        }
        written = 0
        for event in events:
            if event.get("type") != "prediction":
                continue
            price_then = float(event.get("last_price") or 0)
            price_now = float(current_prices.get(event.get("instrument"), 0))
            if price_then <= 0 or price_now <= 0:
                continue
            origin = int(event.get("as_of_ms", 0)) // 1000
            for horizon in (4, 24, 72):
                key = (event.get("signal_id"), horizon)
                if key not in completed and now >= origin + horizon * 3600:
                    self.record_outcome(event["signal_id"], horizon, (price_now / price_then - 1) * 100)
                    completed.add(key)
                    written += 1
        return written

    def recent_events(self, limit: int = 100) -> list[dict]:
        if not self.events_path.exists():
            return []
        lines = self.events_path.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 1000)) :]
        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        return events

    def get_watchlist(self) -> list[str]:
        try:
            data = json.loads(self.watchlist_path.read_text(encoding="utf-8"))
            return sorted(set(str(value) for value in data if str(value).endswith("_USDT")))
        except (OSError, ValueError, TypeError):
            return []

    def set_watchlist(self, instruments: list[str]) -> list[str]:
        cleaned = sorted(set(value for value in instruments if value.endswith("_USDT") and value.replace("_", "").isalnum()))
        temporary = self.watchlist_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
        temporary.replace(self.watchlist_path)
        return cleaned

    def queue_paper_candidate(self, result: dict) -> dict:
        if os.getenv("MARKET_RADAR_PAPER_HANDOFF_ENABLED", "false").lower() != "true":
            raise PermissionError("Paper handoff is disabled; set MARKET_RADAR_PAPER_HANDOFF_ENABLED=true after validation")
        event = {
            "type": "paper_candidate",
            "queued_at": int(time.time()),
            "signal_id": result["signal_id"],
            "instrument": result["instrument"],
            "score": result["score"],
            "model_version": result["model_version"],
            "execution_status": "not_submitted",
        }
        self._append(self.paper_path, event)
        return event
