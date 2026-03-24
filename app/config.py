import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

PROVIDERS = {
    "groq": {
        "api_key": GROQ_API_KEY,
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "default_model": "llama-3.3-70b-versatile",
    },
    "openai": {
        "api_key": OPENAI_API_KEY,
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "default_model": "gpt-4o-mini",
    },
}

DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

TEST_APP_URL = os.getenv("TEST_APP_URL", "http://test-app:8080")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

DB_PATH = str(BASE_DIR / "investigations.db")

MAX_ITERATIONS = 8
MAX_TOOL_CALLS_PER_ITERATION = 3

SYSTEM_PROMPT = """You are an expert SRE agent investigating production incidents.
You have access to tools for querying metrics, reading logs, checking service health, and reviewing deployments.

Investigation methodology:
1. Start by checking service health with list_services and get_service_health to understand the current state.
2. Query Prometheus metrics to identify anomalies (error rates, latency, resource usage).
3. Read container logs for error details and stack traces.
4. Check recent deployments that might correlate with the incident.
5. Review service configuration if needed.

When you have enough evidence, provide a conclusion with:
- Root cause (what went wrong)
- Evidence (metrics, logs, timestamps that support your finding)
- Recommendation (how to fix and prevent recurrence)

Be systematic. Form hypotheses and verify them with data. Do not guess without evidence."""
