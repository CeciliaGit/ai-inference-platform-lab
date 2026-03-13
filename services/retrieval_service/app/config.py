import os

APP_ENV = os.environ.get("APP_ENV", "development")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

POSTGRES_URL = os.environ.get("POSTGRES_URL")
if not POSTGRES_URL:
    raise RuntimeError("POSTGRES_URL must be set (demo: postgresql://rag:rag@postgres:5432/rag)")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
RETRIEVAL_BUDGET_MS = int(os.environ.get("RETRIEVAL_BUDGET_MS", "40"))
CACHE_TTL_S = int(os.environ.get("CACHE_TTL_S", "300"))
