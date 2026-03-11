SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= python3
INGEST_SCRIPT := jobs/ingest/ingest.py
LOADTEST_SCRIPT := scripts/load_test/run.py

.PHONY: help up dev down logs ingest loadtest metrics lint test clean clean-all

help:
	@echo "Available targets:"
	@echo "  make up         Start the local stack with rebuild"
	@echo "  make dev        Start stack and stream logs"
	@echo "  make down       Stop the local stack"
	@echo "  make logs       Follow container logs"
	@echo "  make ingest     Run the offline ingest job once"
	@echo "  make loadtest   Run the load test script"
	@echo "  make metrics    Print Prometheus URL and useful queries"
	@echo "  make lint       Run Ruff lint + format checks"
	@echo "  make test       Run pytest"
	@echo "  make clean      Remove Python caches and temp files"
	@echo "  make clean-all  Full reset (containers, volumes, caches)"

up:
	docker compose up --build -d
	@echo ""
	@echo "Stack starting..."
	@echo "  Router API:        http://localhost:8000/docs"
	@echo "  Retrieval Service: http://localhost:8001/docs"
	@echo "  Inference Worker:  http://localhost:8002/docs"
	@echo "  Prometheus:        http://localhost:9090"

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

ingest:
	@test -f $(INGEST_SCRIPT) || (echo "Missing $(INGEST_SCRIPT)"; exit 1)
	$(PYTHON) $(INGEST_SCRIPT)

loadtest:
	@test -f $(LOADTEST_SCRIPT) || (echo "Missing $(LOADTEST_SCRIPT)"; exit 1)
	$(PYTHON) $(LOADTEST_SCRIPT)

metrics:
	@echo "Prometheus URL:"
	@echo "  http://localhost:9090"
	@echo ""
	@echo "Metric endpoints:"
	@echo "  http://localhost:8000/metrics"
	@echo "  http://localhost:8001/metrics"
	@echo "  http://localhost:8002/metrics"
	@echo ""
	@echo "Common PromQL queries:"
	@echo "  up"
	@echo "  rate(http_requests_total[1m])"
	@echo "  histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))"
	@echo "  sum(rate(http_requests_total{status_code=~\"5..\"}[5m]))"
	@echo "  sum(rate(http_requests_total{status_code=\"429\"}[5m]))"

lint:
	ruff check .
	ruff format --check .

test:
	pytest

clean:
	@echo "Removing Python caches..."
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Cache cleanup complete."

clean-all:
	@echo "Stopping containers and removing volumes..."
	docker compose down -v --remove-orphans
	@$(MAKE) clean
	@echo "Full cleanup complete."
