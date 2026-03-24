import asyncio
import random
import time
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response

app = FastAPI(title="Test App (api-service)")

FAILURE_MODES = {
    "error_rate": 0.0,
    "slow_requests": False,
    "db_connection_issues": False,
}

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["endpoint"])
DB_ERRORS = Counter("db_errors_total", "Database connection errors")

_logs: deque[str] = deque(maxlen=500)
_start_time = time.time()


def _log(level: str, msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _logs.append(f"{ts} [{level}] {msg}")


_log("INFO", "api-service started")


@app.get("/api/users")
async def get_users():
    start = time.time()
    endpoint = "/api/users"

    if FAILURE_MODES["db_connection_issues"]:
        DB_ERRORS.inc()
        _log("ERROR", "Failed to connect to database: connection refused (postgres:5432)")
        REQUEST_COUNT.labels("GET", endpoint, "500").inc()
        REQUEST_LATENCY.labels(endpoint).observe(time.time() - start)
        return Response(status_code=500, content='{"error": "database connection failed"}')

    if random.random() < FAILURE_MODES["error_rate"]:
        _log("ERROR", "Internal server error processing /api/users: NullPointerException in UserService.getAll()")
        REQUEST_COUNT.labels("GET", endpoint, "500").inc()
        REQUEST_LATENCY.labels(endpoint).observe(time.time() - start)
        return Response(status_code=500, content='{"error": "internal server error"}')

    if FAILURE_MODES["slow_requests"]:
        delay = random.uniform(2.0, 5.0)
        await asyncio.sleep(delay)
        _log("WARN", f"Slow response on /api/users: {delay:.1f}s")

    REQUEST_COUNT.labels("GET", endpoint, "200").inc()
    REQUEST_LATENCY.labels(endpoint).observe(time.time() - start)
    _log("INFO", "GET /api/users 200")
    return {"users": [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")


@app.post("/admin/failure-mode")
async def set_failure_mode(body: dict):
    for key in ["error_rate", "slow_requests", "db_connection_issues"]:
        if key in body:
            FAILURE_MODES[key] = body[key]
    _log("INFO", f"Failure modes updated: {FAILURE_MODES}")
    return {"success": True, "modes": FAILURE_MODES}


@app.get("/admin/health")
async def health():
    return {
        "status": "degraded" if any([
            FAILURE_MODES["error_rate"] > 0.1,
            FAILURE_MODES["slow_requests"],
            FAILURE_MODES["db_connection_issues"],
        ]) else "healthy",
        "uptime_seconds": round(time.time() - _start_time),
        "failure_modes": FAILURE_MODES,
    }


@app.get("/admin/logs")
async def logs(lines: int = 50):
    n = min(lines, 200)
    return {"logs": list(_logs)[-n:]}


@app.get("/admin/services")
async def services():
    return {
        "services": [
            {"name": "api-service", "type": "backend", "port": 8080},
            {"name": "postgres", "type": "database", "port": 5432},
            {"name": "prometheus", "type": "monitoring", "port": 9090},
        ]
    }


@app.get("/admin/deployments")
async def deployments():
    now = datetime.now(timezone.utc)
    return {
        "deployments": [
            {
                "version": "v1.2.3",
                "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "active",
                "changes": "Updated user query optimization, connection pool settings",
            },
            {
                "version": "v1.2.2",
                "timestamp": "2025-01-14T10:00:00Z",
                "status": "previous",
                "changes": "Added rate limiting middleware",
            },
        ]
    }


@app.get("/admin/config")
async def config():
    return {
        "service": "api-service",
        "environment": "production",
        "database": {"host": "postgres", "port": 5432, "pool_size": 10, "max_overflow": 5},
        "rate_limit": {"enabled": True, "requests_per_minute": 100},
        "feature_flags": {"new_user_flow": True, "cache_enabled": False},
        "resources": {"cpu_limit": "500m", "memory_limit": "512Mi"},
    }
