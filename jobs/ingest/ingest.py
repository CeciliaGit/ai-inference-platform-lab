"""
Milestone 1 ingestion job.

Inserts a small set of sample documents → chunks → embeddings into Postgres.
Embeddings are produced by hash_embed(): a deterministic, dependency-free
384-dim unit vector derived from token hashes.  Good enough for v1 wiring;
swap in a real encoder in Milestone 3.

Usage:
    pip install asyncpg
    POSTGRES_URL=postgresql://rag:rag@localhost:5432/rag python ingest.py
"""

import asyncio
import hashlib
import math
import os
import re

import asyncpg

POSTGRES_URL = os.environ.get("POSTGRES_URL")
if not POSTGRES_URL:
    raise RuntimeError("POSTGRES_URL must be set (demo: postgresql://rag:rag@localhost:5432/rag)")
MODEL_ID = "hash-embed-v1"
EMBED_DIM = 384


# ---------------------------------------------------------------------------
# Pure helpers — no I/O, fully testable without a database
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _stable_hash(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16)


def hash_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Return a deterministic, L2-normalised *dim*-dimensional embedding."""
    tokens = _TOKEN_RE.findall(text.lower())
    vec = [0.0] * dim
    for t in tokens:
        h = _stable_hash(t)
        idx = h % dim
        sign = -1.0 if ((h >> 8) & 1) else 1.0
        w = 1.0 + min(len(t), 12) / 12.0
        vec[idx] += sign * w
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def chunk_text(text: str, chunk_size: int, overlap: int = 0) -> list[str]:
    """Split *text* into overlapping character-level chunks.

    Returns an empty list for empty input. The final chunk may be shorter
    than *chunk_size* when the text length is not a multiple of the step.

    Args:
        text: Source text to split.
        chunk_size: Maximum characters per chunk (must be > 0).
        overlap: Characters shared between adjacent chunks (0 <= overlap < chunk_size).
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be > 0, got {chunk_size}")
    if not (0 <= overlap < chunk_size):
        raise ValueError(
            f"overlap must satisfy 0 <= overlap < chunk_size, "
            f"got overlap={overlap}, chunk_size={chunk_size}"
        )
    if not text:
        return []
    step = chunk_size - overlap
    return [text[i : i + chunk_size] for i in range(0, len(text), step)]


def chunk_id(doc_id: str, idx: int) -> str:
    return f"{doc_id}-chunk-{idx:03d}"


def to_vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"


def build_document_row(doc_id: str, source: str, version: str) -> dict:
    """Return a dict matching the *documents* table columns."""
    return {"doc_id": doc_id, "source": source, "version": version}


def build_chunk_rows(doc_id: str, chunks: list[str], version: str) -> list[dict]:
    """Return one dict per chunk, matching the *chunks* table columns."""
    return [
        {
            "chunk_id": chunk_id(doc_id, idx),
            "doc_id": doc_id,
            "chunk_index": idx,
            "text": text,
            "version": version,
        }
        for idx, text in enumerate(chunks)
    ]


def build_embedding_rows(chunk_rows: list[dict]) -> list[dict]:
    """Return one dict per chunk row, ready for the *embeddings* table.

    Each dict contains *chunk_id*, *vector_literal* (pgvector string), and *model_id*.
    """
    return [
        {
            "chunk_id": row["chunk_id"],
            "vector_literal": to_vector_literal(hash_embed(row["text"])),
            "model_id": MODEL_ID,
        }
        for row in chunk_rows
    ]


# ---------------------------------------------------------------------------
# Sample corpus
# ---------------------------------------------------------------------------

DOCUMENTS = [
    {
        "doc_id": "doc-001",
        "source": "sample/intro.txt",
        "version": "v1",
        "chunks": [
            "Retrieval-Augmented Generation combines a retriever with a language model.",
            "The retriever finds relevant passages from a document store.",
            "The language model uses those passages as grounded context.",
        ],
    },
    {
        "doc_id": "doc-002",
        "source": "sample/pgvector.txt",
        "version": "v1",
        "chunks": [
            "pgvector is a Postgres extension for storing and querying vector embeddings.",
            "It supports exact and approximate nearest-neighbour search.",
            "IVFFLAT indexes trade recall for speed at query time.",
        ],
    },
]


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

async def ingest(conn: asyncpg.Connection, doc: dict) -> None:
    doc_row = build_document_row(doc["doc_id"], doc["source"], doc["version"])
    chunk_rows = build_chunk_rows(doc["doc_id"], doc["chunks"], doc["version"])
    embedding_rows = build_embedding_rows(chunk_rows)

    await conn.execute(
        """
        INSERT INTO documents (doc_id, source, version)
        VALUES ($1, $2, $3)
        ON CONFLICT (doc_id) DO UPDATE
          SET source = EXCLUDED.source,
              version = EXCLUDED.version
        """,
        doc_row["doc_id"], doc_row["source"], doc_row["version"],
    )

    for crow, erow in zip(chunk_rows, embedding_rows):
        await conn.execute(
            """
            INSERT INTO chunks (chunk_id, doc_id, chunk_index, text, version)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (chunk_id) DO UPDATE
              SET text = EXCLUDED.text,
                  version = EXCLUDED.version,
                  updated_at = now()
            """,
            crow["chunk_id"], crow["doc_id"], crow["chunk_index"], crow["text"], crow["version"],
        )

        await conn.execute(
            """
            INSERT INTO embeddings (chunk_id, embedding, model_id)
            VALUES ($1, $2::vector, $3)
            ON CONFLICT (chunk_id) DO UPDATE
              SET embedding = EXCLUDED.embedding,
                  model_id  = EXCLUDED.model_id,
                  created_at = now()
            """,
            erow["chunk_id"], erow["vector_literal"], erow["model_id"],
        )

        print(f"  ingested {crow['chunk_id']}")


async def main() -> None:
    conn = await asyncpg.connect(POSTGRES_URL)
    await conn.execute("SET search_path TO public")

    for doc in DOCUMENTS:
        print(f"ingesting {doc['doc_id']} ({len(doc['chunks'])} chunks)…")
        await ingest(conn, doc)

    print("analyzing embeddings table for ivfflat…")
    await conn.execute("ANALYZE embeddings;")
    print("done.")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
