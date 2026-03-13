# AI Inference Platform Lab
![CI](https://github.com/CeciliaGit/ai-inference-platform-lab/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Docker](https://img.shields.io/badge/docker-compose-blue)

## Purpose

This repository demonstrates a distributed AI inference platform designed to explore how modern LLM systems protect latency SLOs under burst traffic. It focuses on platform-level concerns such as This repository explores the platform architecture required to operate large-scale AI inference systems reliably under burst traffic and multi-tenant workloads. The focus is on platform reliability mechanisms such as admission control, fairness scheduling, bounded queues, and latency protection rather than model development.

The project models the control-plane mechanisms required to operate a multi-tenant inference platform reliably under unpredictable workloads.

---

## Purpose

Modern AI applications rely on large language model inference services that must serve highly variable requests while maintaining predictable latency.

Unlike traditional web services, inference workloads vary widely depending on prompt size, context retrieval, and generation length.

This lab focuses on **platform-level architecture mechanisms** used to maintain system stability and predictable latency under burst traffic.

---

## Why This Project Matters

Large inference systems face several operational challenges:
- protecting latency SLOs under burst traffic
- isolating tenants to prevent noisy-neighbor effects
- handling variable request cost
- maintaining predictable system behavior under overload

This repository demonstrates architectural mechanisms used in real inference platforms to address these challenges.

---

## Architectural Goals

The platform is designed to achieve the following objectives:

- maintain predictable latency under burst traffic conditions
- isolate tenants through fairness scheduling
- prevent latency collapse using bounded queues
- degrade gracefully when inference capacity is saturated
- expose internal system behavior through observability metrics

---

## System Properties

The platform is designed around the following operational properties:


| Property                      | Description                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| Latency Protection           | Admission control and bounded queues prevent latency collapse during bursts |
| Fairness                     | Tenant-aware scheduling ensures one tenant cannot starve others            |
| Predictable Overload Behavior| The system sheds excess traffic instead of buffering requests indefinitely |
| Graceful Degradation         | Retrieval budgets and generation limits can be reduced under load          |
| Observability                | Metrics expose queue depth, rejection rate, and latency distributions      |

---
### SLO Target

The system models a platform designed to protect latency targets such as:



|   **Metric**         | **Target**                      |
| ---------------- | -------------------------------- |
|   p95 latency    | < target threshold                   |
|   queue depth    | bounded                          |
|   failure mode   | fast fail or degraded response   |

The architecture prioritizes **latency protection over maximum throughput**.

---

## What This Repository Demonstrates

This lab models several architectural mechanisms used in large-scale inference systems:
- distributed inference routing
- retrieval-augmented generation pipeline
- admission control at the platform boundary
- bounded queues and backpressure
- fairness scheduling across tenants
- graceful degradation under overload
- observability of platform behavior

The goal is to explore **platform reliability and behavior**, not model optimization.

---

## Architecture Overview

The platform simulates a distributed inference system composed of routing, retrieval, and inference layers.

Requests enter through a routing layer that enforces admission control, tenant isolation, and fairness policies before interacting with retrieval and inference services.

The architecture separates control-plane responsibilities (routing, scheduling, and admission control) from execution-plane components (retrieval and inference workers) to maintain predictable latency under burst traffic.The platform simulates a distributed inference system composed of routing, retrieval, and inference layers.

Requests enter through a routing layer that enforces admission control and fairness policies before interacting with retrieval and inference services.


---

## Architecture Diagram

```mermaid
flowchart TD
    A[Client / Tenant]

    B[Router API<br/>Admission Control<br/>Rate Limits]

    C[Fairness Scheduler<br/>Tenant Queues]

    D[Retrieval Service<br/>Vector Search]

    E[Inference Worker Pool<br/>Batching / Execution]

    F[(PostgreSQL + pgvector)]

    G[(Redis Cache)]

    H[(Prometheus Metrics)]

    A --> B
    B --> C
    B --> D
    D --> F
    D --> G
    C --> E
    B --> H
    D --> H
    E --> H
```

---


## Failure & Backpressure Flow

The platform protects latency SLOs using admission control and bounded queues.

<p align="center">
  <img src="docs/architecture/failure-and-backpressure.png" alt="Failure & Backpressure Flow" height="1300">
</p>

---

The architecture implements several core platform mechanisms to protect latency and ensure predictable system behavior under burst traffic:

- **Admission control** – deadline-aware request admission to protect latency SLOs  
- **Fairness scheduling** – tenant-aware request queues to prevent noisy-neighbor effects  
- **Bounded queues** – controlled queue sizes to avoid latency collapse under overload  
- **Retrieval latency budgeting** – limiting retrieval work to preserve inference deadlines  
- **Inference batching** – grouping requests to improve worker throughput  
- **Graceful degradation** – reducing workload cost when capacity is constrained  
- **Observability** – system metrics exposing queue depth, latency, and rejection rates

---

## Platform Controls

The platform exposes several tunable controls that influence system behavior under load.

| Control | Description |
|------|------|
| MAX_QUEUE_SIZE | Maximum requests waiting for inference |
| MAX_BATCH_SIZE | Maximum batch size for inference workers |
| BATCH_TIMEOUT_MS | Maximum batching delay before execution |
| RETRIEVAL_BUDGET_MS | Maximum time allowed for retrieval operations |
| ADMISSION_SAFETY_MARGIN | Buffer applied to latency SLO when admitting requests |
| CACHE_TTL_S | Lifetime of cached retrieval results |

---

## Design Tradeoffs

The architecture prioritizes predictable latency and system stability over maximum throughput. Several key design tradeoffs were made to achieve this behavior.

### Latency Protection vs Maximum Throughput

The platform favors early request rejection over buffering excess traffic.

Large queues can temporarily absorb burst traffic but lead to severe tail latency and wasted compute resources when requests exceed client timeouts. By enforcing bounded queues and admission control, the system preserves responsiveness for admitted requests.

### Simplicity vs Optimal Scheduling

The platform models fairness scheduling using Deficit Round Robin (DRR).

More mathematically precise algorithms such as Weighted Fair Queuing (WFQ) provide stronger theoretical fairness guarantees but introduce higher scheduling overhead. DRR offers practical fairness with constant-time scheduling, which is better suited for latency-sensitive gateway systems.

### Local Autonomy vs Global Consistency

In distributed inference systems, enforcing strict global quota checks would introduce additional latency on every request.

Instead, the platform favors local decision-making with bounded inconsistencies. Admission and fairness decisions occur locally at the gateway to keep the request path fast and resilient.

### Graceful Degradation vs Perfect Response Quality

Under heavy load, the system reduces workload cost before rejecting traffic.

Examples include limiting retrieval depth, truncating context, or capping generation length. This approach preserves system availability while accepting temporary reductions in response fidelity.

### Observability Overhead vs Operational Visibility

The platform exposes detailed metrics for queue depth, admission decisions, latency distributions, and degradation behavior.

Although metrics collection introduces small overhead, it enables operators to understand system behavior and detect overload conditions before they escalate into failures.

---

## Architecture at a glance


## Architecture Diagram
The architecture prioritizes **latency protection over maximum throughput**.

---

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
## What This Repository Demonstrates

This lab models several architectural mechanisms used in large-scale inference systems:
- distributed inference routing
- retrieval-augmented generation pipeline
- admission control at the platform boundary
- bounded queues and backpressure
- fairness scheduling across tenants
- graceful degradation under overload
- observability of platform behavior

The goal is to explore **platform reliability and behavior**, not model optimization.

---

## Architecture Overview

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
The platform simulates a distributed inference system composed of routing, retrieval, and inference layers.

Requests enter through a routing layer that enforces admission control, tenant isolation, and fairness policies before interacting with retrieval and inference services.

The architecture separates control-plane responsibilities (routing, scheduling, and admission control) from execution-plane components (retrieval and inference workers) to maintain predictable latency under burst traffic.The platform simulates a distributed inference system composed of routing, retrieval, and inference layers.

Requests enter through a routing layer that enforces admission control and fairness policies before interacting with retrieval and inference services.


---

## Architecture Diagram

```mermaid
flowchart TD
    A[Client / Tenant]

    B[Router API<br/>Admission Control<br/>Rate Limits]

    C[Fairness Scheduler<br/>Tenant Queues]

    D[Retrieval Service<br/>Vector Search]

    E[Inference Worker Pool<br/>Batching / Execution]

    F[(PostgreSQL + pgvector)]

    G[(Redis Cache)]

    H[(Prometheus Metrics)]

    A --> B
    B --> C
    B --> D
    D --> F
    D --> G
    C --> E
    B --> H
    D --> H
    E --> H
```

> **Note:** `hash_embed()` is duplicated verbatim in `jobs/ingest/ingest.py` and `services/retrieval_service/app/main.py`; both files must be updated together if the embedding function changes.

---

# Observability
---


## Failure & Backpressure Flow

The platform protects latency SLOs using admission control and bounded queues.

<p align="center">
  <img src="docs/architecture/failure-and-backpressure.png" alt="Failure & Backpressure Flow" height="1300">
</p>

---

## Key Platform Mechanisms

The architecture implements several core platform mechanisms to protect latency and ensure predictable system behavior under burst traffic:

- **Admission control** – deadline-aware request admission to protect latency SLOs  
- **Fairness scheduling** – tenant-aware request queues to prevent noisy-neighbor effects  
- **Bounded queues** – controlled queue sizes to avoid latency collapse under overload  
- **Retrieval latency budgeting** – limiting retrieval work to preserve inference deadlines  
- **Inference batching** – grouping requests to improve worker throughput  
- **Graceful degradation** – reducing workload cost when capacity is constrained  
- **Observability** – system metrics exposing queue depth, latency, and rejection rates

---

## Platform Controls

The platform exposes several tunable controls that influence system behavior under load.

| Control | Description |
|------|------|
| MAX_QUEUE_SIZE | Maximum requests waiting for inference |
| MAX_BATCH_SIZE | Maximum batch size for inference workers |
| BATCH_TIMEOUT_MS | Maximum batching delay before execution |
| RETRIEVAL_BUDGET_MS | Maximum time allowed for retrieval operations |
| ADMISSION_SAFETY_MARGIN | Buffer applied to latency SLO when admitting requests |
| CACHE_TTL_S | Lifetime of cached retrieval results |

---

## Design Tradeoffs

The architecture prioritizes predictable latency and system stability over maximum throughput. Several key design tradeoffs were made to achieve this behavior.

### Latency Protection vs Maximum Throughput

The platform favors early request rejection over buffering excess traffic.

Large queues can temporarily absorb burst traffic but lead to severe tail latency and wasted compute resources when requests exceed client timeouts. By enforcing bounded queues and admission control, the system preserves responsiveness for admitted requests.

### Simplicity vs Optimal Scheduling

The platform models fairness scheduling using Deficit Round Robin (DRR).

More mathematically precise algorithms such as Weighted Fair Queuing (WFQ) provide stronger theoretical fairness guarantees but introduce higher scheduling overhead. DRR offers practical fairness with constant-time scheduling, which is better suited for latency-sensitive gateway systems.

### Local Autonomy vs Global Consistency

In distributed inference systems, enforcing strict global quota checks would introduce additional latency on every request.

Instead, the platform favors local decision-making with bounded inconsistencies. Admission and fairness decisions occur locally at the gateway to keep the request path fast and resilient.

### Graceful Degradation vs Perfect Response Quality

Under heavy load, the system reduces workload cost before rejecting traffic.

Examples include limiting retrieval depth, truncating context, or capping generation length. This approach preserves system availability while accepting temporary reductions in response fidelity.

### Observability Overhead vs Operational Visibility

The platform exposes detailed metrics for queue depth, admission decisions, latency distributions, and degradation behavior.

Although metrics collection introduces small overhead, it enables operators to understand system behavior and detect overload conditions before they escalate into failures.

---

## Load Testing Summary

The platform was load tested using **Locust** to simulate burst traffic scenarios.

Load tests evaluate:
- queue saturation behavior
- latency distribution under load
- admission control effectiveness
- degradation behavior during overload

Metrics were collected using **Prometheus**.

Example results:

| Scenario | Users | RPS | p95 Latency | Failure Rate |
| ----------------------- | ----- | --- | ----------- | ------------ |
| Baseline | X     | X   | X           | X            |
| Burst    | X     | X   | X           | X            |

---

## Architecture Documentation

A detailed architecture description is available in the repository: `docs/architecture/` [AI Inference Platform Architecture](docs/architecture/AI-Inference-Platform-Architecture-Description.md).

This document provides a TOGAF-style architecture description including:
- architecture principles
- application architecture
- data architecture
- technology architecture
- deployment model
- architecture tradeoffs

---

## Architecture Decisions

Key architectural decisions are documented as Architecture Decision Records (ADRs):

- [ADR 001 – Admission Control Strategy](docs/adr/001-admission-control.md)
- [ADR 002 – Bounded Queues](docs/adr/002-bounded-queues.md)
- [ADR 003 – Multi-Tenant Fairness Scheduling](docs/adr/003-fairness-scheduling.md)
- [ADR 004 – Graceful Degradation Strategy](docs/adr/004-degradation-strategy.md)

---

## Quick Start

Run the platform locally:


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
The system starts the router, retrieval service, inference worker, data stores, and metrics stack.

Configuration defaults are documented in `.env.example`. 
Copy this file to `.env` to override runtime settings locally.

---

## Observability

Each service exposes metrics for system behavior analysis.

Metrics include:
- request latency
- queue depth
- admission rejection rate
- degradation events

Metrics are collected using **Prometheus**.

Services expose both liveness (`/health`) and readiness (`/health/ready`) endpoints, and Docker Compose health checks enforce dependency-aware startup ordering across the stack.

---

## System Limits

This lab models several architectural behaviors of AI inference platforms, but it intentionally simplifies some aspects of production systems.

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
### 1. Simulated Inference Execution

The inference worker simulates model latency rather than executing real GPU-backed inference.  
This allows the platform behavior—admission control, queueing, and scheduling—to be evaluated independently of model performance.

### 2. Single-Region Deployment

The current implementation runs in a single-region environment.  
Production inference platforms typically operate in active-active multi-region deployments with regional routing and failover.

### 3. Simplified Fairness Scheduling

The scheduler models fairness behavior conceptually but does not yet implement a full production-grade multi-tenant scheduling algorithm such as hierarchical DRR or WFQ.

### 4. Simplified Cost Model

Request cost is estimated using simplified heuristics rather than real token accounting.  
Production inference platforms track precise token usage and GPU memory consumption.

### 5. No Persistent Semantic Cache

The retrieval layer includes caching behavior, but a full semantic cache with embedding similarity lookup is not implemented in this version of the lab.

---

## Failure Modes

The platform is designed to fail in controlled and predictable ways under stress conditions.

### 1. Queue Saturation

When inference queues reach their configured capacity, new requests are rejected immediately.

This prevents queue buildup and protects latency for admitted requests.

Client behavior:  
Requests receive HTTP 429 or 503 responses and should retry with backoff.



### 2. Retrieval Timeout

If retrieval exceeds its latency budget, the system falls back to degraded behavior.

Fallback options include:

- serving cached responses
- reducing retrieval context
- skipping retrieval entirely

This prevents retrieval latency from propagating to inference workers.



### 3. Inference Worker Overload

If inference workers reject requests due to queue pressure, the router may retry once with reduced context.

If the retry also fails, the request is rejected.

This protects the inference worker pool from cascading overload.



### 4. Burst Traffic

Under sudden traffic spikes, the admission control layer sheds excess requests.

This ensures that admitted requests maintain acceptable latency rather than being delayed by large queues.



### 5. Metric System Failure

If observability systems (e.g., Prometheus) fail, request processing continues normally.

Metrics collection is intentionally isolated from the request path so that monitoring outages do not impact service availability.


---


## Future Work

Potential extensions to this lab include:

- hierarchical fairness scheduling
- deadline-aware admission policies
- semantic caching layers
- GPU-backed inference workers
- multi-region inference routing
- advanced batching strategies

