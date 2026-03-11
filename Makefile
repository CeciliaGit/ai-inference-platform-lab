SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= python3
INGEST_VENV := .venv-ingest
INGEST_PYTHON := $(INGEST_VENV)/bin/python
INGEST_SCRIPT := jobs/ingest/ingest.py

LOADTEST_VENV := .venv-loadtest
LOADTEST_PYTHON := $(LOADTEST_VENV)/bin/python
LOADTEST_SCRIPT := scripts/load_test/run.py

LINT_VENV := .venv-lint
LINT_RUFF := $(LINT_VENV)/bin/ruff

TEST_VENV := .venv-test
TEST_PYTEST := $(TEST_VENV)/bin/pytest

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

$(INGEST_PYTHON):
	$(PYTHON) -m venv $(INGEST_VENV)
	$(INGEST_PYTHON) -m pip install -q -r jobs/ingest/requirements.txt

ingest: $(INGEST_PYTHON)
	@test -f $(INGEST_SCRIPT) || (echo "Missing $(INGEST_SCRIPT)"; exit 1)
	$(INGEST_PYTHON) $(INGEST_SCRIPT)

$(LOADTEST_PYTHON):
	$(PYTHON) -m venv $(LOADTEST_VENV)
	$(LOADTEST_PYTHON) -m pip install -q httpx==0.28.1

loadtest: $(LOADTEST_PYTHON)
	@test -f $(LOADTEST_SCRIPT) || (echo "Missing $(LOADTEST_SCRIPT)"; exit 1)
	$(LOADTEST_PYTHON) $(LOADTEST_SCRIPT)

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
	@echo ""
	@echo "  # Which services are up (1 = up, 0 = down)"
	@echo "  up"
	@echo ""
	@echo "  # Request rate split by outcome (tier1 / degraded / rejected / error)"
	@echo "  sum by (outcome) (rate(ask_requests_total[30s]))"
	@echo ""
	@echo "  # Live concurrent requests hitting the router (cap = MAX_CONCURRENCY 64)"
	@echo "  router_in_flight_requests"
	@echo ""
	@echo "  # p95 end-to-end latency in ms across all /ask requests"
	@echo "  histogram_quantile(0.95, rate(ask_latency_ms_bucket[30s]))"
	@echo ""
	@echo "  # p95 end-to-end latency in ms across all /ask requests with aggregated label"
	@echo "  histogram_quantile(0.95, sum by (le) (rate(ask_latency_ms_bucket[30s])))"
	@echo ""
	@echo "  # Inference queue depth — watch for saturation (cap = MAX_QUEUE_SIZE 32)"
	@echo "  inference_queue_depth"
	@echo ""
	@echo "  # Rate of degradation events by reason (retrieval_failed / inference_rejected). Total per second rate of degradation events"
	@echo "  sum by (reason) (rate(degradation_total[30s]))"
	@echo ""
	@echo "  # Retrieval source breakdown — how often DB vs cache vs timeout is hit"
	@echo "  sum by (outcome) (rate(retrieval_requests_total[30s]))"

$(LINT_RUFF):
	$(PYTHON) -m venv $(LINT_VENV)
	$(LINT_VENV)/bin/pip install -q ruff

lint: $(LINT_RUFF)
	$(LINT_RUFF) check .
	$(LINT_RUFF) format --check .

$(TEST_PYTEST):
	$(PYTHON) -m venv $(TEST_VENV)
	$(TEST_VENV)/bin/pip install -q \
		pytest pytest-asyncio \
		-r services/router_api/requirements.txt \
		-r services/retrieval_service/requirements.txt \
		-r services/inference_worker/requirements.txt \
		-r jobs/ingest/requirements.txt

test: $(TEST_PYTEST)
	@echo "--- router_api ---"
	PYTHONPATH=services/router_api $(TEST_PYTEST) -q services/router_api/tests
	@echo "--- inference_worker ---"
	PYTHONPATH=services/inference_worker $(TEST_PYTEST) -q services/inference_worker/tests
	@echo "--- retrieval_service ---"
	PYTHONPATH=services/retrieval_service \
	POSTGRES_URL=postgresql://rag:rag@localhost:5432/rag \
	REDIS_URL=redis://localhost:6379/0 \
	$(TEST_PYTEST) -q services/retrieval_service/tests
	@echo "--- ingest ---"
	PYTHONPATH=jobs/ingest \
	POSTGRES_URL=postgresql://rag:rag@localhost:5432/rag \
	$(TEST_PYTEST) -q jobs/ingest/tests

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
