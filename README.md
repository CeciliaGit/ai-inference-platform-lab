# AI Inference Platform Lab

![CI](https://github.com/CeciliaGit/ai-inference-platform-lab/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Docker](https://img.shields.io/badge/docker-compose-blue)

## Purpose

This repository demonstrates a distributed AI inference platform designed to explore how modern LLM systems protect latency SLOs under burst traffic. It focuses on platform-level concerns such as admission control, multi-tenant fairness, bounded queues, graceful degradation, and observability rather than model development.

## Why this project matters

This lab models the control-plane problems found in real AI platforms:
- protecting p95 latency under burst traffic
- isolating tenants so noisy workloads do not starve others
- degrading gracefully when inference capacity is saturated
- making overload behavior observable and measurable


## Architectural Goals

- Demonstrate SLO protection under load
- Model backpressure vs tail latency tradeoffs
- Implement bounded concurrency and degradation
- Separate retrieval, routing, and inference layers
- Instrument full-stack observability

### SLO Target

- Protect p95 latency under saturation
- Prefer fast-fail (429/503) over tail-latency inflation

> **Note:** Inference latency is simulated to isolate concurrency and backpressure behavior independent of model execution cost.

## What this repo demonstrates

- **RAG-style pipeline** — pgvector-backed retrieval and inference services wired end-to-end via `/ask`.
- **Microservice decomposition** — three independently deployable FastAPI services (router, retrieval, inference) communicate over HTTP, making each layer replaceable and scalable on its own.
- **Observability-first design** — Prometheus metrics exposed per service and scraped every 15 s.

## Architecture Overview

## Key platform mechanisms

- Deadline-aware admission control at the router
- Bounded queues to prevent tail-latency collapse
- Retrieval latency budget with cache fallback
- Dynamic batching in the inference worker
- Graceful degradation when workers reject overloaded requests
- Prometheus metrics for queue depth, latency, and degradation events


The architecture models the key layers of a production inference stack: API gateway, request orchestration, retrieval pipeline, and inference execution.


## Architecture at a glance

| Container | Role |
|---|---|
| `router_api` | Admission control + orchestration (`/ask` in Milestone 4) |
| `retrieval_service` | pgvector top-k retrieval with latency budget + cache fallback |
| `inference_worker` | Queue cap + dynamic batching + simulated inference latency |
| `postgres` (pgvector) | Document / chunk / embedding store |
| `redis` | Retrieval cache + semantic cache (Milestone 2+) |
| `prometheus` | Scrapes metrics from all three services every 15 s |

## Architecture Diagram

```mermaid
graph TB
    client["Client / Load Test"]

    subgraph app["Application Services"]
        router["router_api :8000\nMAX_CONCURRENCY = 64\nHTTP_TIMEOUT_S = 2.0"]
        retrieval["retrieval_service :8001\nBUDGET_MS = 40\nhash-embed-v1 · 384-dim"]
        inference["inference_worker :8002\nQUEUE = 32 · BATCH = 8\nBATCH_TIMEOUT_MS = 10"]
    end

    subgraph data["Data Stores"]
        postgres["PostgreSQL 16 / pgvector :5432\ndocuments · chunks · embeddings"]
        redis["Redis 7 :6379\nretrieval cache · TTL = 300 s"]
    end

    subgraph obs["Observability"]
        prometheus["Prometheus :9090\nscrape interval = 15 s"]
    end

    client -->|"POST /ask"| router
    router -->|"POST /retrieve"| retrieval
    router -->|"POST /infer"| inference
    retrieval -->|"vector search (cosine)"| postgres
    retrieval <-->|"cache read / write"| redis
    prometheus -.->|"/metrics"| router
    prometheus -.->|"/metrics"| retrieval
    prometheus -.->|"/metrics"| inference
```

## End-to-End Request Flow

1. Client sends query to **Router API**

        POST /ask

2. Router calls **Retrieval Service**

3. Retrieval performs:

    - query embedding
    - vector similarity search
    - Redis cache lookup

4. Router builds prompt with retrieved context

5. Router sends prompt to **Inference Worker**

6. Inference Worker executes model and returns response

7. Router returns final response to the client

---

### Request flow — `/ask` and the degradation ladder

```mermaid
sequenceDiagram
    participant C  as Client
    participant R  as router_api
    participant RS as retrieval_service
    participant IW as inference_worker
    participant PG as PostgreSQL
    participant RD as Redis

    C->>R: POST /ask {query, tenant, top_k}
    Note over R: Gate: _in_flight < MAX_CONCURRENCY (64)<br/>→ 503 if full

    R->>RS: POST /retrieve
    RS->>RD: GET cache key

    alt Cache hit
        RD-->>RS: cached chunks (JSON)
        RS-->>R: {source:"cache", results}
    else Cache miss — query DB within 40 ms budget
        RS->>PG: SELECT … ORDER BY embedding <=> $1 LIMIT $2
        PG-->>RS: top-k chunks
        RS->>RD: SET cache (TTL = 300 s)
        RS-->>R: {source:"db", results}
    else DB timeout — stale-cache fallback
        RS->>RD: GET cache key
        RS-->>R: {source:"cache", results} or 503
    end

    R->>IW: POST /infer (prompt with retrieved context)

    alt Queue has capacity (< 32)
        Note over IW: Batch collector waits up to 10 ms<br/>Dispatches batch of ≤ 8 · 50 ms simulated latency
        IW-->>R: {response, served_ms}
        R-->>C: 200 {outcome:"tier1"}
    else Queue full → 429, retry without context
        R->>IW: POST /infer (prompt only, no context)
        alt Queue has capacity
            IW-->>R: {response, served_ms}
            R-->>C: 200 {outcome:"degraded"}
        else Still full
            R-->>C: 503 system overloaded
        end
    end
```

## Degradation Strategy

The router protects latency SLOs using graceful degradation.

If inference returns **429**:

1. Retry request **without retrieval context**
2. Attempt smaller prompt
3. Return degraded response if successful
4. Otherwise return **503**

---

## Performance and Scaling Model

The gateway, retrieval layer, and inference workers are designed to scale independently.

| Layer | Scaling Strategy |
|------|------------------|
| Router API | Stateless replicas |
| Retrieval Service | Horizontal scaling |
| Inference Worker | Horizontal workers |
| Postgres | Vertical scale / read replicas |
| Redis | Distributed cache |

---

### Latency Composition

- Retrieval: 10–40 ms
- Prompt build: <5 ms
- Inference: dominant latency

---

## Failure Modes

| Failure | System Behavior |
|-------|----------------|
| Retrieval timeout | fallback to Redis cache |
| Redis unavailable | DB retrieval only |
| Inference queue full | router retry without context |
| System overload | router returns 503 |
| DB timeout | stale cache used |

---
## Load Testing

This lab demonstrates that bounded queues and admission control preserve end-to-end responsiveness under burst traffic by shedding excess load rather than allowing unbounded latency growth.

The platform was load tested using a custom async `httpx` script to simulate burst traffic and validate system behavior under concurrency.

Key behaviors explored:

- admission control under burst load
- queue saturation and backpressure
- latency SLO protection
- degradation behavior when workers are saturated

Metrics were collected using Prometheus and analyzed to observe p95 latency behavior and failure modes.


Script: `scripts/load_test/run.py` — async httpx, configurable workers/duration/RPS.

```bash
# Install dependency (one-time)
python3 -m venv /tmp/lt_venv && /tmp/lt_venv/bin/pip install httpx==0.28.1 -q

# Default run: 20 workers, 30 seconds, unlimited RPS
/tmp/lt_venv/bin/python3 scripts/load_test/run.py

# Throttled: 50 RPS cap
/tmp/lt_venv/bin/python3 scripts/load_test/run.py --rps 50
```

| Flag | Default | Description |
|---|---|---|
| `--url` | `http://localhost:8000` | Base URL of `router_api` |
| `--workers` | `20` | Concurrent async workers |
| `--duration` | `30` | Test duration in seconds |
| `--rps` | `0` (unlimited) | Target requests/sec; `0` = unlimited |

### Baseline results (20 workers, 30 s, default docker-compose config)

| Metric | Value |
|---|---|
| Throughput | **134.9 req/s** |
| p50 latency | 150.8 ms |
| p90 latency | 205.6 ms |
| p95 latency | **253.3 ms** |
| p99 latency | 319.6 ms |
| max latency | 446.4 ms |
| 200 OK | 100 % (4 046 / 4 046) |
| outcome: tier1 | 89.5 % |
| outcome: degraded | 10.5 % |
| 503 / errors | 0 |

Degraded responses occur intentionally when the retrieval latency budget expires, allowing the system to preserve end-to-end responsiveness under load.

Under higher load (≥ 200 concurrent users), queue saturation produces visible rejection (429/503) rather than unbounded latency growth, enforcing the declared SLO policy.


---

## Quick Start

The repository uses a Makefile to standardize common developer and testing workflows.

Start the full platform:
```
make up
```
Seed the database:
```
make ingest
```
Run load test:
```
make loadtest
```
Stop services:
```
make down
```
---

## Developer Commands

Run:
```
make help
```

Commands

```
make up
make dev
make logs
make down
make ingest
make loadtest
make lint
make test
make clean
make clean-all
```

---
## Offline Ingest Pipeline

The ingest job is a **one-shot offline script**.

Prerequisites:
```bash
# One-time: install ingest dependency
pip install -r jobs/ingest/requirements.txt

# Set the connection URL (matches the running docker-compose stack)
export POSTGRES_URL=postgresql://rag:rag@localhost:5432/rag
```

Run:
```
make ingest
```
---

This executes:
```
python jobs/ingest/ingest.py
```

Pipeline:

1. read source documents
2. chunk text
3. compute embeddings
4. insert rows into:
    - documents
    - chunks
    - embeddings

---

### Ingest pipeline (offline)

```mermaid
graph LR
    src["Source documents\n(text files)"]
    job["jobs/ingest/ingest.py"]
    embed["hash_embed()\n384-dim · L2-normalised"]

    subgraph pg["PostgreSQL (rag db)"]
        tdocs["documents\ndoc_id · source · version"]
        tchunks["chunks\nchunk_id · text · chunk_index"]
        tembed["embeddings\nvector(384) · model_id"]
    end

    src --> job
    job -->|"upsert"| tdocs
    job -->|"upsert"| tchunks
    job --> embed
    embed -->|"upsert vector\nmodel_id = hash-embed-v1"| tembed
    tchunks -->|"chunk_id FK"| tembed
```

> **Note:** `hash_embed()` is duplicated verbatim in `jobs/ingest/ingest.py` and `services/retrieval_service/app/main.py`; both files must be updated together if the embedding function changes.

---

# Observability


## Metrics and Observability

Prometheus UI:
```
    http://localhost:9090
```
Metric endpoints:
```
    http://localhost:8000/metrics
    http://localhost:8001/metrics
    http://localhost:8002/metrics
```
Example queries:
```
up
ask_requests_total
rate(ask_requests_total[1m])
ask_latency_ms
inference_queue_depth
retrieval_requests_total
```

## Endpoints

| Service | URL | Description |
|---|---|---|
| router_api | http://localhost:8000/health | Health check |
| router_api | http://localhost:8000/metrics | Prometheus metrics |
| router_api | http://localhost:8000/docs | OpenAPI UI |
| retrieval_service | http://localhost:8001/health | Health check |
| retrieval_service | http://localhost:8001/metrics | Prometheus metrics |
| retrieval_service | http://localhost:8001/docs | OpenAPI UI |
| inference_worker | http://localhost:8002/health | Health check |
| inference_worker | http://localhost:8002/metrics | Prometheus metrics |
| inference_worker | http://localhost:8002/docs | OpenAPI UI |
| Prometheus | http://localhost:9090 | Metrics dashboard |
| PostgreSQL | localhost:5432 | DB `rag`, user `rag`, pass `rag` |
| Redis | localhost:6379 | Default database 0 |

> Demo credentials are intentionally non-secret and for local use only.

---


---


## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every PR and push to `main`.

| Job | What it does |
|---|---|
| `lint` | `ruff check` + `ruff format --check` |
| `test-router-api` | pytest for router service |
| `test-retrieval-service` | pytest for retrieval service |
| `test-inference-worker` | pytest for inference worker |
| `build-router-api` | Docker image build |
| `build-retrieval-service` | Docker image build |
| `build-inference-worker` | Docker image build |
| `compose-build` | Full `docker compose build` |

All eight jobs are required status checks on `main`.

---

## Testing

Each service has a `tests/` directory. Run them without a live stack:

```bash
# router_api
pip install pytest pytest-asyncio -r services/router_api/requirements.txt
pytest -q services/router_api/tests

# inference_worker
pip install pytest -r services/inference_worker/requirements.txt
pytest -q services/inference_worker/tests

# retrieval_service — needs Postgres + Redis reachable
pip install pytest -r services/retrieval_service/requirements.txt
POSTGRES_URL=postgresql://rag:rag@localhost:5432/rag \
  REDIS_URL=redis://localhost:6379/0 \
  pytest -q services/retrieval_service/tests

# ingest helpers — pure functions, no live DB needed
pip install pytest -r jobs/ingest/requirements.txt
POSTGRES_URL=postgresql://rag:rag@localhost:5432/rag \
  pytest -q jobs/ingest/tests
```

Or run everything at once: `make test` (requires all deps installed).

---

## Architecture Experiments

This lab explores several architectural tradeoffs commonly found in large-scale AI inference systems:

- admission control vs queue buffering
- fairness scheduling across tenants
- latency protection under burst traffic
- cache usage to reduce inference load
- observability of inference pipelines

The goal is to model platform-level behavior rather than model quality.

## Future Work

Potential extensions to this lab include:

- GPU-backed inference workers
- semantic caching layers
- multi-region inference routing
- vector search optimizations
- hierarchical DRR scheduling for tenant fairness
- deadline-aware admission control based on queue wait prediction

---
## Extended Architecture Documentation

A TOGAF-style architecture view of the platform is available in `docs/` [TOGAF-Style Architecture Definition](docs/ai_inference_platform_lab_TOGAF_architecture.md).

---
