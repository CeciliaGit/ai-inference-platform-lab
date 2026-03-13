# ADR 004 – Graceful Degradation Strategy

## Status
Accepted

## Context
Inference capacity cannot scale instantly during traffic spikes.

During bursts or infrastructure failures, the system must remain stable while protecting latency-sensitive workloads.

Allowing the system to accept all requests leads to queue buildup, GPU thrashing, and cascading failures.

## Decision
The platform implements a degradation ladder that progressively reduces workload cost during overload conditions.

Examples of degradation steps include:

- reducing retrieval context size
- lowering top_k in retrieval
- tightening semantic cache thresholds
- capping maximum generation tokens
- routing long prompts to smaller models
- shedding low-priority traffic

## Rationale
Reducing marginal workload cost preserves system responsiveness and protects high-priority requests.

It is preferable to degrade response quality slightly rather than allow the entire platform to fail.

## Consequences

### Positive
- Maintains platform availability under load
- Protects latency-sensitive workloads
- Avoids cascading failures

### Negative
- Some responses may be truncated or simplified
- Lower-tier traffic may be rejected during extreme load
