import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


def _key(name: str, labels: dict[str, str]) -> str:
    if not labels:
        return name
    ordered = ",".join(f"{k}={labels[k]}" for k in sorted(labels))
    return f"{name}{{{ordered}}}"


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._histograms: dict[str, dict[str, float]] = {}

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._histograms.clear()

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = _key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + value

    def observe(self, name: str, value: float, **labels: str) -> None:
        key = _key(name, labels)
        with self._lock:
            stats = self._histograms.setdefault(
                key, {"count": 0.0, "sum": 0.0, "max": 0.0}
            )
            stats["count"] += 1
            stats["sum"] += value
            stats["max"] = max(stats["max"], value)

    @contextmanager
    def timer(self, name: str, **labels: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, time.perf_counter() - start, **labels)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self._counters)
            histograms = {
                key: {
                    "count": int(stats["count"]),
                    "sum": round(stats["sum"], 6),
                    "avg": round(stats["sum"] / stats["count"], 6)
                    if stats["count"]
                    else 0.0,
                    "max": round(stats["max"], 6),
                }
                for key, stats in self._histograms.items()
            }
        return {"counters": counters, "histograms": histograms}


METRICS = Metrics()
