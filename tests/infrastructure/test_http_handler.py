"""The HTTP adapter, through the real composition root with the mock motor driver."""

import json

import pytest
from contracts.stream.codec import EventSequencer, NdjsonDecoder, encode_ndjson
from contracts.stream.common.base import EventType
from contracts.stream.microservices.stepper.inbound.completed import (
    StepperCompletedInboundEvent,
    StepperCompletedInboundEventDTO,
)
from contracts.stream.microservices.stepper.inbound.partial import (
    StepperPartialInboundEvent,
    StepperPartialInboundEventDTO,
)
from contracts.stream.microservices.stepper.inbound.stream_started import (
    StepperStreamStartedInboundEvent,
    StepperStreamStartedInboundEventDTO,
)
from contracts.stream.schemas import STEPPER_OUTBOUND
from fastapi.testclient import TestClient

from composition_root.containers.http_container import new_http_container
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stepper_config import StepperConfig

ENVELOPE_KEYS = {"action", "status", "status_code", "message", "timestamp", "data"}


@pytest.fixture
def client():
    cfg = StepperConfig.from_env(
        {
            "MOCK_HARDWARE": "1",
            "STEPPER_CONFIGS": json.dumps(
                {"stepper_1": {"step": 17, "dir": 27, "en": 5}, "stepper_2": {"step": 23, "dir": 24, "en": 25}}
            ),
        }
    )
    container = new_http_container(ServerConfig.from_env({}), cfg)
    with TestClient(container.app) as client:
        yield client


def test_health(client):
    response = client.get("/health")
    body = response.json()
    assert response.status_code == 200
    assert set(body) == ENVELOPE_KEYS
    assert body["action"] == "health_check" and body["status"] == "success"
    assert body["data"] == {"healthy": True}


def test_available_with_mock_hardware(client):
    body = client.get("/available").json()
    assert body["action"] == "check_availability"
    assert body["data"] == {"is_available": True, "reason": None}


def test_rotate_success(client):
    # Small rotation, very high rpm: the mock driver sleeps per step, keep this test fast.
    response = client.post(
        "/control/stepper_1/rotate", params={"rotations": 0.005, "rpm": 6000, "direction": "forward"}
    )
    body = response.json()
    assert response.status_code == 200
    assert body["action"] == "rotate" and body["status"] == "success"
    assert body["data"]["success"] is True and isinstance(body["data"]["message"], str)


def test_steps_success(client):
    response = client.post("/control/stepper_2/steps", params={"value": 5, "speed": 5000})
    assert response.status_code == 200
    assert response.json()["data"]["success"] is True


def test_unknown_stepper_is_404_with_a_failure_envelope(client):
    response = client.post("/control/no_such_stepper/rotate", params={"rotations": 1.0})
    body = response.json()
    assert response.status_code == 404
    assert body["status"] == "error" and body["status_code"] == 404
    assert body["data"]["success"] is False and "no_such_stepper" in body["data"]["message"]


def test_invalid_command_is_422(client):
    response = client.post(
        "/control/stepper_1/steps", params={"value": 5, "speed": 100, "direction": "sideways"}
    )
    assert response.status_code == 422
    assert response.json()["data"]["success"] is False


def test_negative_speed_is_422(client):
    response = client.post("/control/stepper_1/steps", params={"value": 5, "speed": -1})
    assert response.status_code == 422


def test_stop(client):
    response = client.post("/control/stepper_1/stop")
    body = response.json()
    assert response.status_code == 200 and body["action"] == "stop"
    assert body["data"] == {"success": True, "message": "Stop signal dispatched."}


def _upload(*events) -> bytes:
    sequencer = EventSequencer()
    return b"".join(encode_ndjson(sequencer.next(cls, dto)) for cls, dto in events)


def _answer(response) -> list:
    return list(NdjsonDecoder(STEPPER_OUTBOUND).feed(response.content))


def test_a_command_stream_runs_every_command_and_answers_with_contract_events(client):
    body = _upload(
        (StepperStreamStartedInboundEvent, StepperStreamStartedInboundEventDTO(stepper_id="stepper_1")),
        (StepperPartialInboundEvent, StepperPartialInboundEventDTO(action="steps", steps=5, speed=5000)),
        (StepperPartialInboundEvent, StepperPartialInboundEventDTO(action="rotate", rotations=0.005, rpm=6000)),
        (StepperPartialInboundEvent, StepperPartialInboundEventDTO(action="stop")),
        (StepperCompletedInboundEvent, StepperCompletedInboundEventDTO()),
    )
    response = client.post(
        "/process/stream/stepper_1/set", content=body, headers={"content-type": "application/x-ndjson"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = _answer(response)
    assert [e.type for e in events] == [
        EventType.START_STREAM,
        EventType.PARTIAL,
        EventType.PARTIAL,
        EventType.PARTIAL,
        EventType.COMPLETED,
    ]
    assert [(e.payload.action, e.payload.success) for e in events[1:4]] == [
        ("steps", True),
        ("rotate", True),
        ("stop", True),
    ]


def test_a_failed_command_is_reported_and_stops_the_stream(client):
    body = _upload(
        (StepperStreamStartedInboundEvent, StepperStreamStartedInboundEventDTO(stepper_id="stepper_1")),
        (StepperPartialInboundEvent, StepperPartialInboundEventDTO(action="fly")),
        (StepperPartialInboundEvent, StepperPartialInboundEventDTO(action="steps", steps=5, speed=5000)),
    )
    events = _answer(client.post("/process/stream/stepper_1/set", content=body))
    partials = [e for e in events if e.type is EventType.PARTIAL]
    assert len(partials) == 1 and partials[0].payload.success is False
    assert events[-1].type is EventType.COMPLETED and "failed" in events[-1].payload.message


def test_a_stream_for_an_unknown_stepper_is_404(client):
    response = client.post("/process/stream/nope/set", content=b"")
    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_a_stream_naming_another_stepper_is_an_error_event(client):
    body = _upload(
        (StepperStreamStartedInboundEvent, StepperStreamStartedInboundEventDTO(stepper_id="stepper_2")),
    )
    events = _answer(client.post("/process/stream/stepper_1/set", content=body))
    assert events[-1].type is EventType.ERROR
    assert events[-1].payload.code == "invalid_stream" and events[-1].payload.recoverable is False


def test_a_stream_that_breaks_the_contract_is_an_error_event(client):
    events = _answer(client.post("/process/stream/stepper_1/set", content=b"not json\n"))
    assert events[-1].type is EventType.ERROR
