from fastapi.testclient import TestClient

from app.core.metrics import METRICS
from app.main import app


def test_counter_accumulates() -> None:
    METRICS.reset()
    METRICS.increment("events", stage="a", status="ok")
    METRICS.increment("events", stage="a", status="ok")
    METRICS.increment("events", value=3, stage="a", status="error")

    snap = METRICS.snapshot()
    assert snap["counters"]['events{stage=a,status=ok}'] == 2
    assert snap["counters"]['events{stage=a,status=error}'] == 3


def test_histogram_stats() -> None:
    METRICS.reset()
    for value in (1.0, 2.0, 3.0):
        METRICS.observe("latency", value, kind="chat")

    snap = METRICS.snapshot()
    stats = snap["histograms"]["latency{kind=chat}"]
    assert stats["count"] == 3
    assert stats["sum"] == 6.0
    assert stats["avg"] == 2.0
    assert stats["max"] == 3.0


def test_timer_records_elapsed() -> None:
    METRICS.reset()
    with METRICS.timer("op_seconds", stage="x"):
        pass

    stats = METRICS.snapshot()["histograms"]["op_seconds{stage=x}"]
    assert stats["count"] == 1
    assert stats["sum"] >= 0


def test_metrics_endpoint_returns_snapshot() -> None:
    METRICS.reset()
    METRICS.increment("probe_metric")

    client = TestClient(app)
    body = client.get("/metrics").json()

    assert body["counters"]["probe_metric"] == 1
    assert "histograms" in body
