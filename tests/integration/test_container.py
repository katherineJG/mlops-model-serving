"""Tests against the built image; skipped unless MSS_IMAGE names one (`make docker-test`)."""

import json
import os
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator

import httpx
import pytest

IMAGE = os.environ.get("MSS_IMAGE")
pytestmark = [
    pytest.mark.container,
    pytest.mark.skipif(not IMAGE, reason="set MSS_IMAGE to test a built image"),
]

CUSTOMER = {
    "senior_citizen": 0,
    "tenure_months": 3,
    "monthly_charges": 80.0,
    "total_charges": 240.0,
    "gender": "female",
    "partner": "no",
    "contract": "month-to-month",
    "internet_service": "fiber",
    "payment_method": "electronic-check",
    "paperless_billing": "yes",
}


def _docker(*args: str) -> str:
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True, timeout=60
    ).stdout.strip()


def _logs(name: str) -> str:
    done = subprocess.run(["docker", "logs", name], capture_output=True, text=True, check=True)
    return done.stdout + done.stderr


@pytest.fixture
def run_container() -> Iterator[Callable[..., tuple[str, str]]]:
    """Start the image hardened like production; returns (container name, base URL)."""
    started: list[str] = []

    def start(*env: str) -> tuple[str, str]:
        name = f"mss-test-{uuid.uuid4().hex[:8]}"
        args = ["run", "-d", "--name", name, "-p", "127.0.0.1::8000", "--read-only"]
        args += ["--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
        for item in env:
            args += ["-e", item]
        _docker(*args, str(IMAGE))
        started.append(name)
        port = _docker("port", name, "8000/tcp").splitlines()[0].rsplit(":", 1)[1]
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{url}/health/live", timeout=2).status_code == 200:
                    return name, url
            except httpx.TransportError:
                time.sleep(0.3)
        raise AssertionError(f"container did not become live: {_logs(name)}")

    yield start
    for name in started:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


def test_runs_as_non_root(run_container: Callable[..., tuple[str, str]]) -> None:
    name, _ = run_container()
    assert _docker("exec", name, "id", "-u") != "0"
    assert json.loads(_docker("inspect", name, "--format", "{{json .Config.User}}")) not in (
        "",
        "0",
        "root",
    )


def test_smoke_ready_version_predict(run_container: Callable[..., tuple[str, str]]) -> None:
    _, url = run_container("SOURCE_REVISION=smoke")
    assert httpx.get(f"{url}/health/ready").status_code == 200
    version = httpx.get(f"{url}/version").json()
    assert (version["model_id"], version["source_revision"]) == ("churn-v1", "smoke")
    r = httpx.post(f"{url}/predict", json={"instances": [CUSTOMER]})
    assert r.status_code == 200 and r.json()["predictions"][0]["churn"] is True
    assert httpx.post(f"{url}/predict", json={"instances": []}).status_code == 422


def test_missing_model_is_alive_but_not_ready(
    run_container: Callable[..., tuple[str, str]],
) -> None:
    name, url = run_container("MODEL_DIR=/nonexistent")
    assert httpx.get(f"{url}/health/live").status_code == 200
    assert httpx.get(f"{url}/health/ready").status_code == 503
    assert httpx.post(f"{url}/predict", json={"instances": [CUSTOMER]}).status_code == 503
    assert "manifest_missing" in _logs(name)
    assert "/nonexistent" not in httpx.get(f"{url}/version").text


def test_invalid_config_stops_the_container() -> None:
    """Bad configuration must fail fast at startup instead of serving with a wrong setting."""
    name = f"mss-test-{uuid.uuid4().hex[:8]}"
    try:
        _docker("run", "-d", "--name", name, "-e", "MAX_BATCH_SIZE=banana", str(IMAGE))
        for _ in range(50):
            if _docker("inspect", name, "--format", "{{.State.Status}}") == "exited":
                break
            time.sleep(0.2)
        assert _docker("inspect", name, "--format", "{{.State.ExitCode}}") != "0"
        assert "MAX_BATCH_SIZE must be an integer" in _logs(name)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


def test_docker_health_reflects_model_readiness() -> None:
    """HEALTHCHECK probes /health/ready, so a container without a model reports unhealthy."""

    def health_after(name: str, *env: str) -> str:
        flags = ["--health-interval", "2s", "--health-retries", "2", "--health-start-period", "1s"]
        _docker("run", "-d", "--name", name, *flags, *env, str(IMAGE))
        for _ in range(60):
            status = _docker("inspect", name, "--format", "{{.State.Health.Status}}")
            if status != "starting":
                return status
            time.sleep(0.5)
        return "starting"

    good, bad = (f"mss-test-{uuid.uuid4().hex[:8]}" for _ in range(2))
    try:
        assert health_after(good) == "healthy"
        assert health_after(bad, "-e", "MODEL_DIR=/nonexistent") == "unhealthy"
    finally:
        subprocess.run(["docker", "rm", "-f", good, bad], capture_output=True, check=False)
