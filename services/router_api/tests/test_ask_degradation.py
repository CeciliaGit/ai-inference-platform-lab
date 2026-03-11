import pytest
from app.main import _infer_with_retry


class DummyResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


@pytest.mark.asyncio
async def test_infer_retries_without_context(monkeypatch):
    calls = []

    async def fake_infer_once(prompt, max_tokens, tenant):
        calls.append(prompt)
        if len(calls) == 1:
            return DummyResponse(429)
        return DummyResponse(200, {"text": "ok", "served_ms": 12.3})

    monkeypatch.setattr("app.main._infer_once", fake_infer_once)

    resp, had_context = await _infer_with_retry(
        query="hello",
        chunks=[{"text": "ctx"}],
        max_tokens=128,
        tenant="demo",
    )

    assert resp.status_code == 200
    assert had_context is False
    assert len(calls) == 2
    assert "CONTEXT:" in calls[0]
    assert "CONTEXT:" not in calls[1]
