import asyncio
from unittest.mock import MagicMock


def _full_queue(size: int = 32) -> MagicMock:
    """Return a mock Queue whose full() always returns True."""
    q = MagicMock(spec=asyncio.Queue)
    q.full.return_value = True
    q.qsize.return_value = size
    return q


def _race_queue(size: int = 32) -> MagicMock:
    """Return a mock Queue that passes the full() guard but raises on put_nowait.

    Models the race window between the full() check and the actual enqueue.
    """
    q = MagicMock(spec=asyncio.Queue)
    q.full.return_value = False
    q.put_nowait.side_effect = asyncio.QueueFull()
    q.qsize.return_value = size
    return q


def test_full_queue_returns_429(client, monkeypatch):
    monkeypatch.setattr("app.main._queue", _full_queue())
    resp = client.post("/infer", json={"prompt": "test", "max_tokens": 32, "tenant": "demo"})
    assert resp.status_code == 429
    assert "queue" in resp.json()["detail"].lower()


def test_full_queue_detail_message(client, monkeypatch):
    monkeypatch.setattr("app.main._queue", _full_queue())
    resp = client.post("/infer", json={"prompt": "test"})
    assert resp.json()["detail"] == "Inference queue full"


def test_put_nowait_race_returns_429(client, monkeypatch):
    """Covers the race between the full() check and put_nowait()."""
    monkeypatch.setattr("app.main._queue", _race_queue())
    resp = client.post("/infer", json={"prompt": "test"})
    assert resp.status_code == 429
