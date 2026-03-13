import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Literal

from app.config import (
    BATCH_TIMEOUT_MS,
    INFERENCE_LATENCY_MS,
    LOG_LEVEL,
    MAX_BATCH_SIZE,
    MAX_QUEUE_SIZE,
)
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from pydantic import BaseModel, Field

logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

INFERENCE_REQUESTS = Counter(
    "inference_requests_total",
    "Total inference requests",
    ["outcome"],  # outcome: ok | rejected | error
)
INFERENCE_BATCH_SIZE = Histogram(
    "inference_batch_size",
    "Number of items processed per batch",
    buckets=(1, 2, 4, 8, 16, 32),
)
INFERENCE_LATENCY_MS_HIST = Histogram(
    "inference_latency_ms",
    "End-to-end inference latency per request in ms",
    buckets=(5, 10, 20, 40, 80, 160, 320, 640, 1000),
)
QUEUE_DEPTH = Gauge(
    "inference_queue_depth",
    "Current number of items waiting in the inference queue",
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class InferRequest(BaseModel):
    prompt: str
    max_tokens: int = Field(default=256, ge=1, le=2048)
    tenant: str = "demo"


class InferResponse(BaseModel):
    text: str
    tokens: int
    batch_size: int
    served_ms: float
    source: Literal["inference"] = "inference"


# ---------------------------------------------------------------------------
# In-process queue and batch worker
# ---------------------------------------------------------------------------


class _PendingItem:
    __slots__ = ("req", "future", "enqueued_at")

    def __init__(self, req: InferRequest, future: asyncio.Future, enqueued_at: float):
        self.req = req
        self.future = future
        self.enqueued_at = enqueued_at


_queue: asyncio.Queue[_PendingItem] | None = None
_worker_task: asyncio.Task | None = None


async def _collect_batch(first: _PendingItem) -> list[_PendingItem]:
    """Fill a batch starting with *first*, waiting up to BATCH_TIMEOUT_MS for more."""
    batch: list[_PendingItem] = [first]
    deadline = time.perf_counter() + BATCH_TIMEOUT_MS / 1000.0
    while len(batch) < MAX_BATCH_SIZE:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        try:
            item = await asyncio.wait_for(_queue.get(), timeout=remaining)
            batch.append(item)
        except asyncio.TimeoutError:
            break
    return batch


def _resolve_batch(batch: list[_PendingItem]) -> None:
    """Resolve every future in the batch with a simulated InferResponse."""
    for item in batch:
        served_ms = (time.perf_counter() - item.enqueued_at) * 1000
        INFERENCE_LATENCY_MS_HIST.observe(served_ms)
        INFERENCE_REQUESTS.labels(outcome="ok").inc()
        tokens = min(item.req.max_tokens, max(1, len(item.req.prompt.split()) * 2))
        result = InferResponse(
            text=f"[simulated] {item.req.prompt[:80]}",
            tokens=tokens,
            batch_size=len(batch),
            served_ms=round(served_ms, 2),
        )
        if not item.future.done():
            item.future.set_result(result)


async def _batch_worker():
    """Drain the queue in batches, simulating inference latency per batch."""
    while True:
        try:
            first = await asyncio.wait_for(_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue

        batch = await _collect_batch(first)
        INFERENCE_BATCH_SIZE.observe(len(batch))

        # Simulate inference latency (one flat cost per batch, not per item)
        await asyncio.sleep(INFERENCE_LATENCY_MS / 1000.0)

        _resolve_batch(batch)
        for _ in batch:
            _queue.task_done()
        QUEUE_DEPTH.set(_queue.qsize())


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _queue, _worker_task
    _queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
    _worker_task = asyncio.create_task(_batch_worker())
    try:
        yield
    finally:
        if _worker_task:
            _worker_task.cancel()
            await asyncio.gather(_worker_task, return_exceptions=True)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="inference_worker", lifespan=lifespan)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


from fastapi import HTTPException


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    if _queue is None:
        raise HTTPException(status_code=503, detail="Queue not initialized")
    if _worker_task is None or _worker_task.done():
        raise HTTPException(status_code=503, detail="Worker task not running")
    return {"status": "ready"}


@app.post("/infer", response_model=InferResponse)
async def infer(req: InferRequest):
    if _queue is None:
        raise HTTPException(status_code=503, detail="Service not ready")

    if _queue.full():
        INFERENCE_REQUESTS.labels(outcome="rejected").inc()
        raise HTTPException(status_code=429, detail="Inference queue full")

    loop = asyncio.get_running_loop()
    future: asyncio.Future[InferResponse] = loop.create_future()
    item = _PendingItem(req=req, future=future, enqueued_at=time.perf_counter())

    try:
        _queue.put_nowait(item)
        QUEUE_DEPTH.set(_queue.qsize())
    except asyncio.QueueFull:
        INFERENCE_REQUESTS.labels(outcome="rejected").inc()
        raise HTTPException(status_code=429, detail="Inference queue full")

    try:
        return await future
    except asyncio.CancelledError:
        raise
    except Exception:
        INFERENCE_REQUESTS.labels(outcome="error").inc()
        raise HTTPException(status_code=500, detail="Inference failed")
