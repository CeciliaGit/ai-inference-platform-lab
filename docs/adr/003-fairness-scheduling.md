# ADR 003 – Multi-Tenant Fairness Scheduling

## Status
Accepted

## Context
Inference platforms are multi-tenant systems where different customers submit requests simultaneously.

Requests may vary in cost depending on token count, prompt length, and model complexity.

Without fairness scheduling, high-volume tenants or large requests may monopolize inference capacity and starve other tenants.

## Decision
The platform models fairness scheduling using Deficit Round Robin (DRR).

Each tenant has a queue, and requests are scheduled based on a credit-based system that approximates fair resource distribution.

Request cost is estimated based on token usage.

## Rationale
DRR provides practical fairness with constant-time scheduling overhead, making it suitable for high-throughput gateways.

Compared to Weighted Fair Queuing (WFQ), DRR avoids priority queue sorting overhead while still delivering predictable fairness behavior.

## Consequences

### Positive
- Prevents noisy-neighbor effects
- Ensures fair resource allocation across tenants
- Supports multi-tenant platform guarantees

### Negative
- Scheduling logic is more complex than FIFO
- Requires request cost estimation
