#!/usr/bin/env bash
set -uo pipefail

TARGET_HOST="${TARGET_HOST:-http://localhost:8000}"
RUN_TIME_BASE="${RUN_TIME_BASE:-3m}"
RUN_TIME_SPIKE="${RUN_TIME_SPIKE:-2m}"
RUN_TIME_RECOVER="${RUN_TIME_RECOVER:-3m}"

echo "Target: ${TARGET_HOST}"

# Baseline
locust -f scripts/load_test/locustfile.py \
  --headless \
  --host "${TARGET_HOST}" \
  -u 200 -r 50 \
  --run-time "${RUN_TIME_BASE}" \
  --csv docs/locust_baseline --csv-full-history

# Spike
locust -f scripts/load_test/locustfile.py \
  --headless \
  --host "${TARGET_HOST}" \
  -u 600 -r 150 \
  --run-time "${RUN_TIME_SPIKE}" \
  --csv docs/locust_spike --csv-full-history

# Recovery
locust -f scripts/load_test/locustfile.py \
  --headless \
  --host "${TARGET_HOST}" \
  -u 200 -r 50 \
  --run-time "${RUN_TIME_RECOVER}" \
  --csv docs/locust_recover --csv-full-history
