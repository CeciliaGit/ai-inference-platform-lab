"""Tests for pure helper functions in ingest.py — no database required."""

import os

import pytest

# ingest.py checks POSTGRES_URL at import time; provide a dummy value.
os.environ.setdefault("POSTGRES_URL", "postgresql://rag:rag@localhost:5432/rag")

from ingest import (  # noqa: E402
    MODEL_ID,
    build_chunk_rows,
    build_document_row,
    build_embedding_rows,
    chunk_id,
    chunk_text,
    hash_embed,
    to_vector_literal,
)

# ---------------------------------------------------------------------------
# hash_embed
# ---------------------------------------------------------------------------


def test_hash_embed_is_deterministic():
    assert hash_embed("Hello world") == hash_embed("Hello world")


def test_hash_embed_dim():
    assert len(hash_embed("Hello world")) == 384


def test_hash_embed_is_unit_normalised():
    vec = hash_embed("retrieval augmented generation")
    norm = sum(x * x for x in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_hash_embed_differs_for_different_text():
    assert hash_embed("foo") != hash_embed("bar")


def test_hash_embed_empty_string_returns_zero_vector():
    # No tokens → vec stays all-zeros → norm defaults to 1.0 → all zeros returned.
    vec = hash_embed("")
    assert all(x == 0.0 for x in vec)


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------


def test_chunk_text_no_overlap():
    assert chunk_text("abcdef", chunk_size=2, overlap=0) == ["ab", "cd", "ef"]


def test_chunk_text_with_overlap():
    # step = 3 - 1 = 2 → ["abc", "cde", "e"]
    assert chunk_text("abcde", chunk_size=3, overlap=1) == ["abc", "cde", "e"]


def test_chunk_text_shorter_than_chunk_size():
    assert chunk_text("hello", chunk_size=100) == ["hello"]


def test_chunk_text_empty_returns_empty_list():
    assert chunk_text("", chunk_size=10) == []


def test_chunk_text_default_overlap_is_zero():
    assert chunk_text("abcd", chunk_size=2) == ["ab", "cd"]


def test_chunk_text_invalid_chunk_size_raises():
    with pytest.raises(ValueError, match="chunk_size"):
        chunk_text("text", chunk_size=0)


def test_chunk_text_overlap_equals_chunk_size_raises():
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("text", chunk_size=3, overlap=3)


def test_chunk_text_negative_overlap_raises():
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("text", chunk_size=3, overlap=-1)


def test_chunk_text_exact_multiple():
    # 6 chars, chunk_size=3, no overlap → exactly 2 full chunks, no tail
    chunks = chunk_text("abcdef", chunk_size=3, overlap=0)
    assert chunks == ["abc", "def"]


def test_chunk_text_preserves_all_content():
    text = "hello world"
    chunks = chunk_text(text, chunk_size=4, overlap=1)
    # Reconstruct: each chunk starts at step=3 from the last
    # Verify all characters are reachable in at least one chunk.
    combined = "".join(chunks)
    for ch in text:
        assert ch in combined


# ---------------------------------------------------------------------------
# chunk_id
# ---------------------------------------------------------------------------


def test_chunk_id_zero_padded():
    assert chunk_id("doc-001", 0) == "doc-001-chunk-000"
    assert chunk_id("doc-001", 9) == "doc-001-chunk-009"
    assert chunk_id("doc-001", 12) == "doc-001-chunk-012"


def test_chunk_id_includes_doc_id():
    assert chunk_id("my-doc", 3).startswith("my-doc-")


def test_chunk_id_unique_per_index():
    assert chunk_id("doc-001", 0) != chunk_id("doc-001", 1)


# ---------------------------------------------------------------------------
# to_vector_literal
# ---------------------------------------------------------------------------


def test_vector_literal_brackets():
    lit = to_vector_literal([1.0, -0.5, 0.0])
    assert lit.startswith("[") and lit.endswith("]")


def test_vector_literal_six_decimal_places():
    assert "1.000000" in to_vector_literal([1.0])


def test_vector_literal_negative_values():
    assert "-0.500000" in to_vector_literal([-0.5])


def test_vector_literal_element_count():
    vec = list(range(10))
    inner = to_vector_literal(vec)[1:-1]
    assert len(inner.split(",")) == len(vec)


# ---------------------------------------------------------------------------
# build_document_row
# ---------------------------------------------------------------------------


def test_build_document_row_keys():
    row = build_document_row("doc-001", "sample/intro.txt", "v1")
    assert row == {"doc_id": "doc-001", "source": "sample/intro.txt", "version": "v1"}


def test_build_document_row_values_are_strings():
    row = build_document_row("d", "s", "v")
    assert all(isinstance(v, str) for v in row.values())


# ---------------------------------------------------------------------------
# build_chunk_rows
# ---------------------------------------------------------------------------


def test_build_chunk_rows_count():
    rows = build_chunk_rows("doc-001", ["a", "b", "c"], "v1")
    assert len(rows) == 3


def test_build_chunk_rows_fields():
    rows = build_chunk_rows("doc-001", ["hello"], "v1")
    row = rows[0]
    assert row["chunk_id"] == "doc-001-chunk-000"
    assert row["doc_id"] == "doc-001"
    assert row["chunk_index"] == 0
    assert row["text"] == "hello"
    assert row["version"] == "v1"


def test_build_chunk_rows_sequential_ids():
    rows = build_chunk_rows("doc-001", ["a", "b", "c"], "v1")
    assert [r["chunk_id"] for r in rows] == [
        "doc-001-chunk-000",
        "doc-001-chunk-001",
        "doc-001-chunk-002",
    ]


def test_build_chunk_rows_chunk_index_matches_position():
    rows = build_chunk_rows("doc-001", ["x", "y", "z"], "v1")
    for i, row in enumerate(rows):
        assert row["chunk_index"] == i


def test_build_chunk_rows_empty_chunks_list():
    assert build_chunk_rows("doc-001", [], "v1") == []


# ---------------------------------------------------------------------------
# build_embedding_rows
# ---------------------------------------------------------------------------


def test_build_embedding_rows_count():
    chunk_rows = build_chunk_rows("doc-001", ["text a", "text b"], "v1")
    assert len(build_embedding_rows(chunk_rows)) == len(chunk_rows)


def test_build_embedding_rows_fields():
    chunk_rows = build_chunk_rows("doc-001", ["hello world"], "v1")
    row = build_embedding_rows(chunk_rows)[0]
    assert row["chunk_id"] == "doc-001-chunk-000"
    assert row["model_id"] == MODEL_ID
    assert row["vector_literal"].startswith("[")
    assert row["vector_literal"].endswith("]")


def test_build_embedding_rows_are_deterministic():
    chunk_rows = build_chunk_rows("doc-001", ["same text"], "v1")
    assert build_embedding_rows(chunk_rows) == build_embedding_rows(chunk_rows)


def test_build_embedding_rows_differ_for_different_text():
    rows_a = build_embedding_rows(build_chunk_rows("doc-001", ["foo"], "v1"))
    rows_b = build_embedding_rows(build_chunk_rows("doc-001", ["bar"], "v1"))
    assert rows_a[0]["vector_literal"] != rows_b[0]["vector_literal"]


def test_build_embedding_rows_chunk_ids_match_input():
    chunk_rows = build_chunk_rows("doc-001", ["a", "b"], "v1")
    emb_rows = build_embedding_rows(chunk_rows)
    assert [e["chunk_id"] for e in emb_rows] == [c["chunk_id"] for c in chunk_rows]


def test_build_embedding_rows_empty_input():
    assert build_embedding_rows([]) == []
