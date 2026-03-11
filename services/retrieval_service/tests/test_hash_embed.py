import os

os.environ.setdefault("POSTGRES_URL", "postgresql://rag:rag@localhost:5432/rag")

from app.main import hash_embed


def test_hash_embed_is_deterministic():
    v1 = hash_embed("Hello world")
    v2 = hash_embed("Hello world")
    assert v1 == v2


def test_hash_embed_has_expected_dim():
    vec = hash_embed("Hello world")
    assert len(vec) == 384


def test_hash_embed_is_normalized():
    vec = hash_embed("Hello world")
    norm = sum(x * x for x in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-6
