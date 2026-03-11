import os

os.environ.setdefault("POSTGRES_URL", "postgresql://rag:rag@localhost:5432/rag")

from app.main import _cache_key


def test_cache_key_changes_with_inputs():
    k1 = _cache_key("q1", "demo", 5)
    k2 = _cache_key("q2", "demo", 5)
    k3 = _cache_key("q1", "other", 5)
    k4 = _cache_key("q1", "demo", 10)

    assert k1 != k2
    assert k1 != k3
    assert k1 != k4
