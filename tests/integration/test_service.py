"""Integration tests: model lifecycle through the ASGI app, plus a real uvicorn server over TCP."""

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

import app.main as main
from app.config import load_settings
from app.main import create_app
from app.model_loader import LoadedModel, load_model

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

pytestmark = pytest.mark.integration


def test_model_is_loaded_once_not_per_request(
    model_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    real = load_model

    def counting(path: Path) -> LoadedModel:
        nonlocal calls
        calls += 1
        return real(path)

    monkeypatch.setattr(main, "load_model", counting)
    with TestClient(create_app(load_settings({"MODEL_DIR": str(model_dir)}))) as c:
        for _ in range(5):
            assert c.post("/predict", json={"instances": [CUSTOMER]}).status_code == 200
            assert c.get("/health/ready").status_code == 200
    assert calls == 1


def test_readiness_transitions_with_artifact_state(model_dir: Path) -> None:
    """The same directory is not ready while corrupted and ready once restored (after restart)."""
    artifact = model_dir / "model.joblib"
    good = artifact.read_bytes()
    settings = load_settings({"MODEL_DIR": str(model_dir)})

    artifact.write_bytes(good + b"corruption")
    with TestClient(create_app(settings)) as c:
        assert c.get("/health/live").status_code == 200
        assert c.get("/health/ready").status_code == 503
        assert c.post("/predict", json={"instances": [CUSTOMER]}).status_code == 503
        assert "model_loaded 0.0" in c.get("/metrics").text

    artifact.write_bytes(good)
    with TestClient(create_app(settings)) as c:
        assert c.get("/health/ready").status_code == 200
        assert c.post("/predict", json={"instances": [CUSTOMER]}).status_code == 200


def test_no_in_place_reload_when_artifact_changes_while_running(model_dir: Path) -> None:
    with TestClient(create_app(load_settings({"MODEL_DIR": str(model_dir)}))) as c:
        (model_dir / "model.joblib").write_bytes(b"replaced while running")
        assert c.get("/health/ready").status_code == 200
        assert c.post("/predict", json={"instances": [CUSTOMER]}).status_code == 200


@pytest.fixture
def live_server(model_dir: Path) -> Iterator[str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(load_settings({"MODEL_DIR": str(model_dir)})),
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "uvicorn did not start"
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def test_over_a_real_socket(live_server: str) -> None:
    assert httpx.get(f"{live_server}/health/ready").status_code == 200
    r = httpx.post(f"{live_server}/predict", json={"instances": [CUSTOMER]})
    assert r.status_code == 200 and r.json()["predictions"][0]["churn"] is True
    bad = httpx.post(f"{live_server}/predict", json={"instances": [{**CUSTOMER, "contract": "x"}]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    too_big = httpx.post(f"{live_server}/predict", content=b"x" * (300 * 1024))
    assert too_big.status_code == 413
