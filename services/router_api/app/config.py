import os

APP_ENV = os.environ.get("APP_ENV", "development")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

RETRIEVAL_SERVICE_URL = os.environ.get("RETRIEVAL_SERVICE_URL", "http://retrieval_service:8000")
INFERENCE_WORKER_URL = os.environ.get("INFERENCE_WORKER_URL", "http://inference_worker:8000")
HTTP_TIMEOUT_S = float(os.environ.get("HTTP_TIMEOUT_S", "5.0"))
MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "64"))
ADMISSION_SAFETY_MARGIN = float(os.environ.get("ADMISSION_SAFETY_MARGIN", "0.8"))
