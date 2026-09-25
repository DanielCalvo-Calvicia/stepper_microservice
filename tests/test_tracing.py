import os
import sys

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient  # noqa: E402
from shared_logging.testing import capture  # noqa: E402

TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
TRACEPARENT = f"00-{TRACE_ID}-b7ad6b7169203331-01"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MOCK_HARDWARE", "1")
    from composition_root.containers.container import BuildContainer

    container = BuildContainer(name="Stepper Microservice")
    return TestClient(container.stepper_dependency.adapter_inbound.app)


def test_incoming_trace_is_continued_and_logged_with_the_service_name(client):
    with capture("stepper") as logs:
        response = client.get("/health", headers={"traceparent": TRACEPARENT})

    assert response.status_code == 200
    assert response.headers["x-trace-id"] == TRACE_ID
    request_logs = [r for r in logs.records if r["logger"] == "shared_logging.http"]
    assert request_logs and {r["trace_id"] for r in request_logs} == {TRACE_ID}
    assert {r["service"] for r in logs.records} == {"stepper"}
