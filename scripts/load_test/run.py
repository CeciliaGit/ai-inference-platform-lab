#!/usr/bin/env python3
"""
Milestone 5 load test: sustained /ask throughput with p95 latency reporting.

Usage:
    python scripts/load_test/run.py [options]

Options:
    --url       Base URL of router_api  (default: http://localhost:8000)
    --workers   Concurrent async workers (default: 20)
    --duration  Test duration in seconds (default: 30)
    --rps       Target requests/sec across all workers, 0 = unlimited (default: 0)
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter
from typing import NamedTuple

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

QUERIES = [
    "What is retrieval-augmented generation?",
    "How does pgvector support semantic search?",
    "Explain the inference batching strategy.",
    "What latency budget does the retrieval service enforce?",
    "How does the degradation ladder work?",
    "What Prometheus metrics does the router expose?",
    "Describe the Redis cache fallback mechanism.",
    "What happens when the inference queue is full?",
    "How are embeddings stored in PostgreSQL?",
    "What is the default top-k for retrieval?",
]

PAYLOAD_TEMPLATE = {
    "tenant": "demo",
    "top_k": 5,
    "max_tokens": 64,
    "cache_ttl_s": 300,
}


# ---------------------------------------------------------------------------
# Result record
# ---------------------------------------------------------------------------


class Result(NamedTuple):
    latency_ms: float
    http_status: int
    outcome: str  # ok | degraded | rejected | error | exception


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


async def worker(
    client: httpx.AsyncClient,
    url: str,
    results: list[Result],
    stop_event: asyncio.Event,
    rps_limiter: asyncio.Semaphore | None,
    query_cycle: list[str],
) -> None:
    idx = 0
    while not stop_event.is_set():
        if rps_limiter is not None:
            await rps_limiter.acquire()

        query = query_cycle[idx % len(query_cycle)]
        idx += 1
        payload = {**PAYLOAD_TEMPLATE, "query": query}

        t0 = time.perf_counter()
        try:
            resp = await client.post(f"{url}/ask", json=payload)
            latency_ms = (time.perf_counter() - t0) * 1000

            if resp.status_code == 200:
                body = resp.json()
                outcome = body.get("source", "ok")  # "tier1" or "degraded"
            elif resp.status_code == 429:
                outcome = "rejected"
            elif resp.status_code == 503:
                outcome = "rejected"
            else:
                outcome = "error"

            results.append(
                Result(latency_ms=latency_ms, http_status=resp.status_code, outcome=outcome)
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            results.append(Result(latency_ms=latency_ms, http_status=0, outcome="exception"))
            print(f"  [warn] request exception: {exc}")


# ---------------------------------------------------------------------------
# Rate limiter ticker
# ---------------------------------------------------------------------------


async def rps_ticker(sem: asyncio.Semaphore, target_rps: float, stop_event: asyncio.Event) -> None:
    interval = 1.0 / target_rps
    while not stop_event.is_set():
        sem.release()
        await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _pct(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    return statistics.quantiles(data, n=100)[int(p) - 1]


def print_report(results: list[Result], duration_s: float, workers: int) -> None:
    total = len(results)
    rps = total / duration_s if duration_s else 0

    latencies = [r.latency_ms for r in results]
    latencies_ok = [r.latency_ms for r in results if r.outcome in ("tier1", "degraded", "ok")]

    outcomes = Counter(r.outcome for r in results)
    statuses = Counter(r.http_status for r in results)

    print()
    print("=" * 60)
    print("  Milestone 5 — Load Test Results")
    print("=" * 60)
    print(f"  Duration      : {duration_s:.1f} s")
    print(f"  Workers       : {workers}")
    print(f"  Total requests: {total}")
    print(f"  Throughput    : {rps:.1f} req/s")
    print()
    print("  Latency (all requests, ms):")
    if latencies:
        print(f"    p50  : {_pct(latencies, 50):.1f}")
        print(f"    p90  : {_pct(latencies, 90):.1f}")
        print(f"    p95  : {_pct(latencies, 95):.1f}")
        print(f"    p99  : {_pct(latencies, 99):.1f}")
        print(f"    max  : {max(latencies):.1f}")
    print()
    if latencies_ok:
        print("  Latency (200 OK only, ms):")
        print(f"    p50  : {_pct(latencies_ok, 50):.1f}")
        print(f"    p90  : {_pct(latencies_ok, 90):.1f}")
        print(f"    p95  : {_pct(latencies_ok, 95):.1f}")
        print(f"    p99  : {_pct(latencies_ok, 99):.1f}")
        print(f"    max  : {max(latencies_ok):.1f}")
        print()
    print("  Outcomes:")
    for k, v in sorted(outcomes.items()):
        pct = 100 * v / total if total else 0
        print(f"    {k:<12}: {v:>6}  ({pct:.1f}%)")
    print()
    print("  HTTP status codes:")
    for k, v in sorted(statuses.items()):
        print(f"    {k:<6}: {v}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="router_api load test")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument(
        "--rps", type=float, default=0, help="Target RPS across all workers (0 = unlimited)"
    )
    args = parser.parse_args()

    print(
        f"Load test: {args.url}/ask  workers={args.workers}  "
        f"duration={args.duration}s  rps={'unlimited' if args.rps == 0 else args.rps}"
    )

    results: list[Result] = []
    stop_event = asyncio.Event()

    rps_sem: asyncio.Semaphore | None = None
    ticker_task = None
    if args.rps > 0:
        # Pre-fill semaphore with a few tokens so workers don't stall on startup
        rps_sem = asyncio.Semaphore(0)
        ticker_task = asyncio.create_task(rps_ticker(rps_sem, args.rps, stop_event))

    # Stagger query offsets across workers so they don't all send identical queries
    async with httpx.AsyncClient(timeout=10.0) as client:
        worker_tasks = [
            asyncio.create_task(
                worker(
                    client,
                    args.url,
                    results,
                    stop_event,
                    rps_sem,
                    QUERIES[i % len(QUERIES) :] + QUERIES[: i % len(QUERIES)],
                )
            )
            for i in range(args.workers)
        ]

        t_start = time.perf_counter()
        await asyncio.sleep(args.duration)
        duration_actual = time.perf_counter() - t_start

        stop_event.set()
        if ticker_task:
            ticker_task.cancel()
        await asyncio.gather(*worker_tasks, return_exceptions=True)

    print_report(results, duration_actual, args.workers)


if __name__ == "__main__":
    asyncio.run(main())
