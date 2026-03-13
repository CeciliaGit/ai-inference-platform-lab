# ADR 001 – Admission Control Strategy

## Status
Accepted

## Context
Inference workloads are highly variable in cost and bursty in arrival patterns. 
Requests may differ significantly in compute cost depending on prompt size, retrieval context, and generation length.

Allowing all incoming requests into the system without control can cause queue growth, latency collapse, and resource exhaustion.

In inference systems, protecting latency SLOs is more important than maximizing request admission.

## Decision
The router enforces admission control and rejects requests when queue pressure or predicted wait time exceeds safe operating thresholds.

Admission checks occur before requests enter the inference queue.

Typical rejection responses:
- HTTP 429 (rate limit exceeded)
- HTTP 503 (system overloaded)

## Rationale
Requests that cannot realistically meet latency SLOs should be rejected early rather than allowed to consume scarce GPU or inference worker capacity.

Failing fast preserves latency guarantees for admitted traffic and prevents cascading failures in downstream services.

## Consequences

### Positive
- Protects latency SLOs
- Prevents queue buildup
- Maintains stable system behavior during bursts

### Negative
- Some requests are rejected during overload
- Clients must implement retry and backoff logic
