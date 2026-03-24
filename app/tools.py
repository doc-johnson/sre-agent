import time

import httpx

from app.config import PROMETHEUS_URL, TEST_APP_URL

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_services",
            "description": (
                "List all monitored services and their basic status. "
                "Start investigations with this tool to get an overview."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_health",
            "description": "Get detailed health status of a specific service including uptime, active failure modes, and request statistics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name, e.g. 'api-service'",
                    },
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_metrics",
            "description": "Query Prometheus metrics using PromQL. Useful for checking error rates, latency percentiles, and resource usage over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL query, e.g. 'rate(http_requests_total{status=~\"5..\"}[5m])'",
                    },
                    "duration": {
                        "type": "string",
                        "description": "Time range for range queries, e.g. '15m', '1h'. If omitted, returns instant value.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_container_logs",
            "description": "Get recent logs from a service container. Returns the last N log lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name, e.g. 'api-service'",
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines to retrieve (default 50, max 200)",
                    },
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_deployments",
            "description": "Get recent deployments for a service. Check this to correlate incidents with code changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name, e.g. 'api-service'",
                    },
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_config",
            "description": "Read the current configuration of a service including environment variables, resource limits, and feature flags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name, e.g. 'api-service'",
                    },
                },
                "required": ["service"],
            },
        },
    },
]

_http = httpx.Client(timeout=10)


def _safe_request(method: str, url: str, **kwargs) -> dict:
    try:
        resp = _http.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"}
    except Exception as e:
        return {"success": False, "error": str(e)[:500]}


def list_services() -> dict:
    data = _safe_request("GET", f"{TEST_APP_URL}/admin/services")
    if "error" in data:
        return data
    return {"success": True, "services": data.get("services", [])}


def get_service_health(service: str) -> dict:
    data = _safe_request("GET", f"{TEST_APP_URL}/admin/health")
    if "error" in data:
        return data
    return {"success": True, "service": service, **data}


def query_metrics(query: str, duration: str | None = None) -> dict:
    if duration:
        end = time.time()
        seconds = _parse_duration(duration)
        start = end - seconds
        data = _safe_request(
            "GET",
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "step": "15s"},
        )
    else:
        data = _safe_request(
            "GET",
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
        )

    if "error" in data:
        return data

    results = data.get("data", {}).get("result", [])
    truncated = _truncate_results(results, max_series=5, max_points=20)
    return {"success": True, "query": query, "results": truncated}


def get_container_logs(service: str, lines: int = 50) -> dict:
    lines = min(lines, 200)
    data = _safe_request(
        "GET", f"{TEST_APP_URL}/admin/logs", params={"lines": lines}
    )
    if "error" in data:
        return data
    return {"success": True, "service": service, "logs": data.get("logs", [])}


def get_recent_deployments(service: str) -> dict:
    data = _safe_request("GET", f"{TEST_APP_URL}/admin/deployments")
    if "error" in data:
        return data
    return {"success": True, "service": service, "deployments": data.get("deployments", [])}


def read_config(service: str) -> dict:
    data = _safe_request("GET", f"{TEST_APP_URL}/admin/config")
    if "error" in data:
        return data
    return {"success": True, "service": service, "config": data}


TOOL_HANDLERS = {
    "list_services": lambda args: list_services(),
    "get_service_health": lambda args: get_service_health(args.get("service", "")),
    "query_metrics": lambda args: query_metrics(args.get("query", ""), args.get("duration")),
    "get_container_logs": lambda args: get_container_logs(args.get("service", ""), args.get("lines", 50)),
    "get_recent_deployments": lambda args: get_recent_deployments(args.get("service", "")),
    "read_config": lambda args: read_config(args.get("service", "")),
}


def _parse_duration(d: str) -> int:
    d = d.strip()
    if d.endswith("h"):
        return int(d[:-1]) * 3600
    if d.endswith("m"):
        return int(d[:-1]) * 60
    if d.endswith("s"):
        return int(d[:-1])
    return 900


def _truncate_results(results: list, max_series: int = 5, max_points: int = 20) -> list:
    truncated = []
    for series in results[:max_series]:
        s = {**series}
        if "values" in s and len(s["values"]) > max_points:
            step = len(s["values"]) // max_points
            s["values"] = s["values"][::step][:max_points]
            s["_truncated"] = True
        truncated.append(s)
    if len(results) > max_series:
        truncated.append({"_note": f"Showing {max_series} of {len(results)} series"})
    return truncated
