import itertools
import logging
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

APP_URL = "http://test-app:8080"
SCENARIO_DURATION = 120

SCENARIOS = [
    {"name": "normal", "modes": {"error_rate": 0.0, "slow_requests": False, "db_connection_issues": False}},
    {"name": "high_error", "modes": {"error_rate": 0.7, "slow_requests": False, "db_connection_issues": False}},
    {"name": "slow", "modes": {"error_rate": 0.0, "slow_requests": True, "db_connection_issues": False}},
    {"name": "db_issues", "modes": {"error_rate": 0.0, "slow_requests": False, "db_connection_issues": True}},
    {"name": "normal", "modes": {"error_rate": 0.0, "slow_requests": False, "db_connection_issues": False}},
]

client = httpx.Client(timeout=10)


def set_failure_mode(modes: dict):
    try:
        client.post(f"{APP_URL}/admin/failure-mode", json=modes)
    except Exception as e:
        logger.error(f"Failed to set failure mode: {e}")


def send_request():
    try:
        resp = client.get(f"{APP_URL}/api/users")
        return resp.status_code
    except Exception:
        return 0


def main():
    logger.info("Traffic generator starting, waiting for test-app...")
    for _ in range(30):
        try:
            client.get(f"{APP_URL}/admin/health")
            break
        except Exception:
            time.sleep(2)
    else:
        logger.error("test-app not available after 60s")
        return

    logger.info("test-app is ready")

    for scenario in itertools.cycle(SCENARIOS):
        logger.info(f"Scenario: {scenario['name']}")
        set_failure_mode(scenario["modes"])

        end_time = time.time() + SCENARIO_DURATION
        while time.time() < end_time:
            status = send_request()
            if status >= 500:
                logger.warning(f"Request failed: {status}")
            time.sleep(1)


if __name__ == "__main__":
    main()
