import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_NAME     = os.getenv("DB_NAME", "everwod_production")
DB_USER     = os.getenv("DB_USER", "everwod")
DB_PASSWORD = os.getenv("DB_PASSWORD", "everwod123")

OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
LLM_MODEL   = os.getenv("LLM_MODEL", "llama3.2:3b")

DBSCAN_EPS              = float(os.getenv("DBSCAN_EPS", "0.25"))
DBSCAN_MIN_SAMPLES      = int(os.getenv("DBSCAN_MIN_SAMPLES", "5"))
MAX_MESSAGES_PER_CLUSTER = int(os.getenv("MAX_MESSAGES_PER_CLUSTER", "10"))
DAYS_LOOKBACK           = int(os.getenv("DAYS_LOOKBACK", "90"))
LLM_TIMEOUT             = int(os.getenv("LLM_TIMEOUT", "300"))
LLM_RETRIES             = int(os.getenv("LLM_RETRIES", "3"))
