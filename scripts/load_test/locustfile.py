import os
import random

from locust import HttpUser, between, task

HOST = os.environ.get("TARGET_HOST", "http://localhost:8000")

QUERIES = [
    "pgvector nearest neighbour search",
    "retrieval augmented generation",
    "IVFFLAT index recall speed",
    "vector embeddings postgres extension",
    "dynamic batching latency p95",
    "queue backpressure overload 429",
]


class AskUser(HttpUser):
    host = HOST
    wait_time = between(0.0, 0.02)  # effectively constant pressure

    @task
    def ask(self):
        q = random.choice(QUERIES)
        payload = {
            "query": q,
            "tenant": "demo",
            "top_k": 5,
            "cache_ttl_s": 300,
            "max_tokens": 128,
        }
        with self.client.post("/ask", json=payload, catch_response=True) as resp:
            if resp.status_code == 200:
                body = resp.json()
                # treat degraded as success but trackable in metrics via Prometheus
                if "text" in body:
                    resp.success()
                else:
                    resp.failure("missing text")
            elif resp.status_code in (503, 429):
                resp.failure(f"overload {resp.status_code}")
            else:
                resp.failure(f"unexpected {resp.status_code}")
