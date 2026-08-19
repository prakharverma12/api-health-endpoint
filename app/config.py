import os

from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "10"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "4"))
BACKOFF_BASE_SECONDS = float(os.getenv("BACKOFF_BASE_SECONDS", "1"))

DATABASE_URL = os.getenv("DATABASE_URL")

HISTORY_DB_PATH = os.getenv("HISTORY_DB_PATH", "sentinel_history.db")
AUDIT_DB_PATH = os.getenv("AUDIT_DB_PATH", "sentinel_audit.db")
REGISTRY_DB_PATH = os.getenv("REGISTRY_DB_PATH", "sentinel_registry.db")
DRIFT_MIN_SAMPLES = int(os.getenv("DRIFT_MIN_SAMPLES", "5"))
DRIFT_ZSCORE_THRESHOLD = float(os.getenv("DRIFT_ZSCORE_THRESHOLD", "4.0"))

TREND_WINDOW = int(os.getenv("TREND_WINDOW", "10"))
TREND_MIN_SAMPLES = int(os.getenv("TREND_MIN_SAMPLES", "6"))
TREND_SLOPE_THRESHOLD_MS = float(os.getenv("TREND_SLOPE_THRESHOLD_MS", "5.0"))
