import pytest
from fastapi.testclient import TestClient
from shared_logging.testing import capture

from composition_root.containers import http_container
from composition_root.dependencies import stepper_dependencies as deps
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stepper_config import StepperConfig
from infrastructure.outbound.mock_motor.mock_motor_driver import MockMotorDriver

TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
TRACEPARENT = f"00-{TRACE_ID}-b7ad6b7169203331-01"


def _container(env=None):
    return http_container.new_http_container(
        ServerConfig.from_env({}), StepperConfig.from_env({"MOCK_HARDWARE": "1", **(env or {})})
    )


def test_container_wires_an_app_that_answers_health():
    container = _container()
    body = TestClient(container.app).get("/health").json()
    assert body["status"] == "success" and body["action"] == "health_check"
    assert container.stepper.is_available() is True


def test_mock_hardware_selects_the_mock_driver():
    driver = deps.new_motor_driver(StepperConfig.from_env({"MOCK_HARDWARE": "1"}))
    assert isinstance(driver, MockMotorDriver)


def test_without_gpio_the_mock_driver_is_used_even_when_not_forced(monkeypatch):
    monkeypatch.setattr(deps, "GPIO_AVAILABLE", False)
    assert isinstance(deps.new_motor_driver(StepperConfig.from_env({})), MockMotorDriver)


def test_incoming_trace_is_continued_and_logged_with_the_service_name():
    client = TestClient(_container().app)
    with capture("stepper") as logs:
        response = client.get("/health", headers={"traceparent": TRACEPARENT})

    assert response.status_code == 200
    assert response.headers["x-trace-id"] == TRACE_ID
    request_logs = [r for r in logs.records if r["logger"] == "shared_logging.http"]
    assert request_logs and {r["trace_id"] for r in request_logs} == {TRACE_ID}
    assert {r["service"] for r in logs.records} == {"stepper"}


@pytest.mark.parametrize("path", ["/available", "/control/stepper_1/stop"])
def test_no_route_needs_credentials(path):
    client = TestClient(_container().app)
    response = client.get(path) if path == "/available" else client.post(path)
    assert response.status_code == 200
