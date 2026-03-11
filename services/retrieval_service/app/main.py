import asyncio
import hashlib
import json
import logging
import math
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Literal

import asyncpg
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

POSTGRES_URL = os.environ.get("POSTGRES_URL")
if not POSTGRES_URL:
    raise RuntimeError("POSTGRES_URL must be set (demo: postgresql://rag:rag@postgres:5432/rag)")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
RETRIEVAL_BUDGET_MS = int(os.environ.get("RETRIEVAL_BUDGET_MS", "40"))
CACHE_TTL_S = int(os.environ.get("CACHE_TTL_S", "300"))
EMBED_DIM = 384
EMBED_MODEL_ID = "hash-embed-v1"


# ---------------------------------------------------------------------------
# Deterministic embedding (mirrors jobs/ingest/ingest.py — swap together)
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


def _cache_key(query: str, tenant: str, top_k: int) -> str:
    h = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return f"retrieval:v1:{tenant}:{top_k}:{h}"


# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

RETRIEVAL_REQUESTS = Counter(
    "retrieval_requests_total",
    "Total retrieval requests",
    ["outcome"],  # outcome: db | cache | timeout | error
)
RETRIEVAL_DB_LATENCY_MS = Histogram(
    "retrieval_db_latency_ms",
    "DB retrieval latency in ms",
    buckets=(1, 2, 5, 10, 20, 40, 80, 160, 320, 640, 1000),
)
CACHE_HIT = Counter("retrieval_cache_hit_total", "Total cache hits")
CACHE_MISS = Counter("retrieval_cache_miss_total", "Total cache misses")
CACHE_WRITE = Counter("retrieval_cache_write_total", "Total cache writes")


# ---------------------------------------------------------------------------
# Connection pool + Redis client
# ---------------------------------------------------------------------------

_pool: asyncpg.Pool | None = None
_redis: Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, _redis
    _pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)
    _redis = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        yield
    finally:
        if _redis:
            await _redis.close()
        if _pool:
            await _pool.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="retrieval_service", lifespan=lifespan)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /retrieve
# ---------------------------------------------------------------------------


class RetrieveRequest(BaseModel):
    query: str
    tenant: str = "demo"
    top_k: int = Field(default=5, ge=1, le=20)
    cache_ttl_s: int = Field(default=CACHE_TTL_S, ge=1)


class ChunkResult(BaseModel):
    chunk_id: str
    doc_id: str
    version: str
    text: str
    distance: float


class RetrieveResponse(BaseModel):
    source: Literal["db", "cache"]
    results: list[ChunkResult]


async def _query_db(vector_literal: str, top_k: int) -> list[ChunkResult]:
    rows = await _pool.fetch(
        """
        SELECT c.chunk_id,
               c.doc_id,
               c.version,
               c.text,
               (e.embedding <=> $1::vector) AS distance
        FROM   embeddings e
        JOIN   chunks c ON c.chunk_id = e.chunk_id
        WHERE  e.model_id = $3
        ORDER  BY e.embedding <=> $1::vector
        LIMIT  $2
        """,
        vector_literal,
        top_k,
        EMBED_MODEL_ID,
    )
    return [
        ChunkResult(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            version=r["version"],
            text=r["text"],
            distance=r["distance"],
        )
        for r in rows
    ]


async def _try_cache(key: str) -> RetrieveResponse | None:
    """Return a cache-hit response, or None if the cache is empty or unparseable."""
    cached = await _redis.get(key)
    if not cached:
        CACHE_MISS.inc()
        return None
    try:
        results = [ChunkResult(**item) for item in json.loads(cached)]
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.exception("cache entry corrupt, ignoring", extra={"key": key})
        CACHE_MISS.inc()
        return None
    CACHE_HIT.inc()
    RETRIEVAL_REQUESTS.labels(outcome="cache").inc()
    return RetrieveResponse(source="cache", results=results)


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(req: RetrieveRequest):
    if _pool is None or _redis is None:
        raise HTTPException(status_code=503, detail="Service not ready")

    key = _cache_key(req.query, req.tenant, req.top_k)
    embedding = hash_embed(req.query)
    vector_literal = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
    budget_s = RETRIEVAL_BUDGET_MS / 1000.0

    try:
        start = time.perf_counter()
        results = await asyncio.wait_for(_query_db(vector_literal, req.top_k), timeout=budget_s)
        RETRIEVAL_DB_LATENCY_MS.observe((time.perf_counter() - start) * 1000)
        await _redis.set(key, json.dumps([r.model_dump() for r in results]), ex=req.cache_ttl_s)
        CACHE_WRITE.inc()
        RETRIEVAL_REQUESTS.labels(outcome="db").inc()
        return RetrieveResponse(source="db", results=results)

    except TimeoutError:
        RETRIEVAL_DB_LATENCY_MS.observe((time.perf_counter() - start) * 1000)
        RETRIEVAL_REQUESTS.labels(outcome="timeout").inc()
        hit = await _try_cache(key)
        if hit:
            return hit
        raise HTTPException(status_code=503, detail="retrieval timeout and cache miss") from None

    except Exception:
        RETRIEVAL_REQUESTS.labels(outcome="error").inc()
        logger.exception(
            "retrieval db error",
            extra={
                "tenant": req.tenant,
                "top_k": req.top_k,
                "query_hash": hashlib.sha256(req.query.encode()).hexdigest()[:16],
            },
        )
        hit = await _try_cache(key)
        if hit:
            return hit
        raise HTTPException(status_code=503, detail="retrieval error and cache miss") from None
