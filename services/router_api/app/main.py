import logging
import time
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from pydantic import BaseModel, Field

from app.config import HTTP_TIMEOUT_S, INFERENCE_WORKER_URL, LOG_LEVEL, MAX_CONCURRENCY, RETRIEVAL_SERVICE_URL

logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

ASK_REQUESTS = Counter(
    "ask_requests_total",
    "Total /ask requests",
    ["outcome"],  # outcome: ok | degraded | rejected | error
)
ROUTER_IN_FLIGHT = Gauge(
    "router_in_flight_requests",
    "Requests currently being processed by the router",
)
ASK_LATENCY_MS = Histogram(
    "ask_latency_ms",
    "End-to-end /ask latency in ms",
    buckets=(100, 250, 500, 1000, 2000, 4000, 8000, 15000, 30000, 60000),
)
RETRIEVAL_CALL_LATENCY_MS = Histogram(
    "retrieval_call_latency_ms",
    "Router→retrieval_service round-trip latency in ms",
    buckets=(1, 5, 10, 25, 50, 100, 200, 400, 800),
)
INFERENCE_CALL_LATENCY_MS = Histogram(
    "inference_call_latency_ms",
    "Router→inference_worker round-trip latency in ms",
    buckets=(5, 10, 25, 50, 100, 200, 400, 800, 1600),
)
DEGRADATION = Counter(
    "degradation_total",
    "Degradation events by reason",
    ["reason"],  # reason: retrieval_failed | inference_rejected | inference_error
)


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

_http: httpx.AsyncClient | None = None
_in_flight: int = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http
    _http = httpx.AsyncClient(timeout=HTTP_TIMEOUT_S)
    try:
        yield
    finally:
        if _http:
            await _http.aclose()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="router_api", lifespan=lifespan)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /ask
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    query: str
    tenant: str = "demo"
    top_k: int = Field(default=5, ge=1, le=20)
    cache_ttl_s: int = Field(default=300, ge=1)
    max_tokens: int = Field(default=256, ge=1, le=2048)


class AskResponse(BaseModel):
    text: str
    source: Literal["tier1", "degraded"]
    retrieval_source: Literal["db", "cache", "skipped"]
    top_k_used: int
    served_ms: float
    retrieval_ms: float
    inference_served_ms: float | None


_MAX_CONTEXT_CHARS = 2000


def _build_prompt(query: str, chunks: list[dict]) -> str:
    if not chunks:
        return f"SYSTEM: Answer using context if present.\nUSER: {query}"
    lines: list[str] = []
    budget = _MAX_CONTEXT_CHARS
    for c in chunks:
        line = f"- {c['text']}"
        if len(line) > budget:
            break
        lines.append(line)
        budget -= len(line)
    context_block = "\nCONTEXT:\n" + "\n".join(lines) if lines else ""
    return f"SYSTEM: Answer using context if present.{context_block}\nUSER: {query}"


async def _retrieve(
    req: AskRequest,
) -> tuple[list[dict], Literal["db", "cache", "skipped"], float]:
    chunks: list[dict] = []
    retrieval_source: Literal["db", "cache", "skipped"] = "skipped"
    start = time.perf_counter()
    try:
        r_resp = await _http.post(
            f"{RETRIEVAL_SERVICE_URL}/retrieve",
            json={
                "query": req.query,
                "tenant": req.tenant,
                "top_k": req.top_k,
                "cache_ttl_s": req.cache_ttl_s,
            },
        )
        if r_resp.status_code == 200:
            body = r_resp.json()
            retrieval_source = body["source"]
            chunks = body["results"]
        else:
            DEGRADATION.labels(reason="retrieval_failed").inc()
            logger.warning("retrieval_service returned %d", r_resp.status_code)
    except Exception:
        DEGRADATION.labels(reason="retrieval_failed").inc()
        logger.exception("retrieval_service call failed")
    finally:
        retrieval_ms = (time.perf_counter() - start) * 1000
        RETRIEVAL_CALL_LATENCY_MS.observe(retrieval_ms)
    return chunks, retrieval_source, retrieval_ms


async def _infer_once(
    prompt: str, max_tokens: int, tenant: str
) -> httpx.Response | None:
    """POST to inference_worker; observe latency; return response or None on exception."""
    start = time.perf_counter()
    try:
        return await _http.post(
            f"{INFERENCE_WORKER_URL}/infer",
            json={"prompt": prompt, "max_tokens": max_tokens, "tenant": tenant},
        )
    except Exception:
        logger.exception("inference_worker call failed")
        return None
    finally:
        INFERENCE_CALL_LATENCY_MS.observe((time.perf_counter() - start) * 1000)


async def _infer_with_retry(
    query: str, chunks: list[dict], max_tokens: int, tenant: str
) -> tuple[httpx.Response | None, bool]:
    """Call inference. If 429 and context was used, retry once without context.

    Returns (response_or_None, context_was_used_for_this_response).
    """
    i_resp = await _infer_once(_build_prompt(query, chunks), max_tokens, tenant)
    if i_resp is None:
        return None, False
    if i_resp.status_code != 429:
        return i_resp, bool(chunks)
    if not chunks:
        return i_resp, False
    # 429 with context → one retry stripped of context
    DEGRADATION.labels(reason="inference_rejected").inc()
    logger.warning("inference_worker 429 with context — retrying without context")
    return await _infer_once(_build_prompt(query, []), max_tokens, tenant), False


def _make_ok_response(
    i_body: dict,
    had_context: bool,
    chunks: list[dict],
    retrieval_source: Literal["db", "cache", "skipped"],
    retrieval_ms: float,
    req_start: float,
) -> AskResponse:
    source: Literal["tier1", "degraded"] = "tier1" if had_context else "degraded"
    served_ms = round((time.perf_counter() - req_start) * 1000, 2)
    ASK_REQUESTS.labels(outcome="ok" if had_context else "degraded").inc()
    ASK_LATENCY_MS.observe(served_ms)
    return AskResponse(
        text=i_body["text"],
        source=source,
        retrieval_source=retrieval_source,
        top_k_used=len(chunks) if had_context else 0,
        served_ms=served_ms,
        retrieval_ms=round(retrieval_ms, 2),
        inference_served_ms=i_body.get("served_ms"),
    )


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    global _in_flight
    if _http is None:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Concurrency gate: shed load immediately rather than queuing at the router.
    if _in_flight >= MAX_CONCURRENCY:
        ASK_REQUESTS.labels(outcome="rejected").inc()
        raise HTTPException(status_code=503, detail="system overloaded")

    _in_flight += 1
    ROUTER_IN_FLIGHT.set(_in_flight)
    req_start = time.perf_counter()
    try:
        chunks, retrieval_source, retrieval_ms = await _retrieve(req)
        i_resp, had_context = await _infer_with_retry(req.query, chunks, req.max_tokens, req.tenant)

        if i_resp is not None and i_resp.status_code == 200:
            return _make_ok_response(i_resp.json(), had_context, chunks,
                                     retrieval_source, retrieval_ms, req_start)

        rejected = i_resp is not None and i_resp.status_code == 429
        if rejected:
            ASK_REQUESTS.labels(outcome="rejected").inc()
        else:
            DEGRADATION.labels(reason="inference_error").inc()
            ASK_REQUESTS.labels(outcome="error").inc()
        ASK_LATENCY_MS.observe(round((time.perf_counter() - req_start) * 1000, 2))
        raise HTTPException(status_code=503, detail="system overloaded")
    finally:
        _in_flight -= 1
        ROUTER_IN_FLIGHT.set(_in_flight)
