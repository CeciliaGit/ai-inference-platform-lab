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
# Deterministic embedding (no ML deps required for v1)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _stable_hash(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16)


def hash_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
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
    # Upsert document
    await conn.execute(
        """
        INSERT INTO documents (doc_id, source, version)
        VALUES ($1, $2, $3)
        ON CONFLICT (doc_id) DO UPDATE
          SET source = EXCLUDED.source,
              version = EXCLUDED.version
        """,
        doc["doc_id"], doc["source"], doc["version"],
    )

    for idx, text in enumerate(doc["chunks"]):
        chunk_id = f"{doc['doc_id']}-chunk-{idx:03d}"

        # Upsert chunk
        await conn.execute(
            """
            INSERT INTO chunks (chunk_id, doc_id, chunk_index, text, version)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (chunk_id) DO UPDATE
              SET text = EXCLUDED.text,
                  version = EXCLUDED.version,
                  updated_at = now()
            """,
            chunk_id, doc["doc_id"], idx, text, doc["version"],
        )

        # Upsert embedding
        embedding = hash_embed(text)
        vector_literal = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
        await conn.execute(
            """
            INSERT INTO embeddings (chunk_id, embedding, model_id)
            VALUES ($1, $2::vector, $3)
            ON CONFLICT (chunk_id) DO UPDATE
              SET embedding = EXCLUDED.embedding,
                  model_id  = EXCLUDED.model_id,
                  created_at = now()
            """,
            chunk_id, vector_literal, MODEL_ID,
        )

        print(f"  ingested {chunk_id}")


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
