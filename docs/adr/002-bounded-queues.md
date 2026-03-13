# ADR 002 – Bounded Queues

## Status
Accepted

## Context
Inference workloads experience burst traffic and unpredictable request costs.

A common approach to burst absorption is large request queues. However, large queues introduce significant latency and cause requests to wait far longer than client timeout budgets.

This leads to "bufferbloat" where requests appear accepted but ultimately fail after consuming compute resources.

## Decision
All inference queues are bounded.

When the queue is full, new requests are rejected immediately instead of being buffered indefinitely.

## Rationale
Bounded queues prevent the system from converting overload into invisible latency debt.

It is better for a request to fail fast than to wait in a queue for a response that will arrive after the client timeout.

## Consequences

### Positive
- Predictable latency behavior
- Faster failure feedback to clients
- Protection of downstream inference workers

### Negative
- Increased rejection rate during bursts
- Requires client retry logic
