import os

APP_ENV = os.environ.get("APP_ENV", "development")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

MAX_QUEUE_SIZE = int(os.environ.get("MAX_QUEUE_SIZE", "32"))
MAX_BATCH_SIZE = int(os.environ.get("MAX_BATCH_SIZE", "8"))
BATCH_TIMEOUT_MS = int(os.environ.get("BATCH_TIMEOUT_MS", "10"))
INFERENCE_LATENCY_MS = int(os.environ.get("INFERENCE_LATENCY_MS", "50"))
