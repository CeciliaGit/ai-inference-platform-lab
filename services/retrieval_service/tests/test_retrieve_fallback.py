import os

from fastapi.testclient import TestClient

os.environ.setdefault("POSTGRES_URL", "postgresql://rag:rag@localhost:5432/rag")

from app.main import app


class DummyRedis:
    async def get(self, key):
        return '[{"chunk_id":"c1","doc_id":"d1","version":"v1","text":"cached","distance":0.1}]'

    async def set(self, key, value, ex=None):
        return True


client = TestClient(app)


def test_retrieve_timeout_uses_cache(monkeypatch):
    async def fake_query_db(vector_literal, top_k):
        raise TimeoutError()

    monkeypatch.setattr("app.main._query_db", fake_query_db)
    monkeypatch.setattr("app.main._redis", DummyRedis())
    monkeypatch.setattr("app.main._pool", object())

    resp = client.post(
        "/retrieve",
        json={"query": "test", "tenant": "demo", "top_k": 3, "cache_ttl_s": 300},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "cache"
    assert body["results"][0]["text"] == "cached"
