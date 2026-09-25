"""The JSON shape of every non-stream answer is the project contract ``ApiEnvelope``; ``data`` is
the endpoint's contract dataclass (``contracts.api.microservices``), matching every other
OBLIVION service. Uses the real DI container (MockStepperAdapter), not a hand-rolled fake.
"""
import os
import sys

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MOCK_HARDWARE", "1")
    from composition_root.containers.container import BuildContainer

    container = BuildContainer(name="Stepper Microservice")
    return TestClient(container.stepper_dependency.adapter_inbound.app)


def _envelope_keys(body: dict) -> set:
    return set(body)


def test_health(client):
    response = client.get("/health")
    body = response.json()

    assert response.status_code == 200
    assert _envelope_keys(body) == {"action", "status", "status_code", "message", "timestamp", "data"}
    assert body["action"] == "health_check"
    assert body["status"] == "success"
    assert body["data"] == {"healthy": True}


def test_available_with_mock_hardware(client):
    response = client.get("/available")
    body = response.json()

    assert response.status_code == 200
    assert body["action"] == "check_availability"
    assert body["data"] == {"is_available": True, "reason": None}


def test_rotate_success(client):
    # Small rotation, very high rpm: the mock adapter sleeps per step, keep this test fast.
    response = client.post("/control/stepper_1/rotate", params={"rotations": 0.005, "rpm": 6000, "direction": "forward"})
    body = response.json()

    assert response.status_code == 200
    assert body["action"] == "rotate"
    assert body["status"] == "success"
    assert body["data"]["success"] is True
    assert isinstance(body["data"]["message"], str)


def test_rotate_unknown_stepper_is_a_failure_envelope(client):
    response = client.post("/control/no_such_stepper/rotate", params={"rotations": 1.0})
    body = response.json()

    assert response.status_code == 400
    assert body["status"] == "error"
    assert body["data"]["success"] is False
    assert "no_such_stepper" in body["data"]["message"]


def test_stop(client):
    response = client.post("/control/stepper_1/stop")
    body = response.json()

    assert response.status_code == 200
    assert body["action"] == "stop"
    assert body["data"] == {"success": True, "message": "Stop signal dispatched."}
