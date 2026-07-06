import json
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from config import OBSERVABILITY_EVENTS_PATH


class MetricsRecorder:
    """Lightweight JSONL observability recorder for demos and interviews."""

    def __init__(self, path: Path = OBSERVABILITY_EVENTS_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, event_type: str, **payload: Any) -> None:
        event = {
            "ts": time.time(),
            "event_type": event_type,
            **payload,
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def load_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in lines if line.strip()]
        return events[-limit:]

    def summary(self) -> Dict[str, Any]:
        events = self.load_events(limit=10000)
        counts = Counter(event["event_type"] for event in events)
        retrieval_events = [event for event in events if event["event_type"] == "retrieval"]
        task_events = [event for event in events if event["event_type"].startswith("task_")]

        avg_retrieval_latency = 0
        if retrieval_events:
            avg_retrieval_latency = sum(
                event.get("latency_ms", 0) for event in retrieval_events
            ) / len(retrieval_events)

        return {
            "event_counts": dict(counts),
            "retrieval_count": len(retrieval_events),
            "task_event_count": len(task_events),
            "avg_retrieval_latency_ms": round(avg_retrieval_latency, 2),
            "latest_events": events[-10:],
        }


metrics_recorder = MetricsRecorder()

