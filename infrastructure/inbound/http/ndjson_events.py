"""The NDJSON events the stepper answers ``POST /process/stream/{id}/set`` with."""

from typing import Any

from contracts.stream.codec import EventSequencer, encode_ndjson
from contracts.stream.common.error import ErrorEvent, ErrorEventDTO
from contracts.stream.common.heartbeat import HeartbeatEvent
from contracts.stream.microservices.stepper.outbound.completed import (
    StepperCompletedOutboundEvent,
    StepperCompletedOutboundEventDTO,
)
from contracts.stream.microservices.stepper.outbound.partial import (
    StepperPartialOutboundEvent,
    StepperPartialOutboundEventDTO,
)
from contracts.stream.microservices.stepper.outbound.stream_started import (
    StepperStreamStartedOutboundEvent,
    StepperStreamStartedOutboundEventDTO,
)


class NdjsonEventStream:
    """Builds the response events of one command stream with stream-local sequencing."""

    def __init__(self) -> None:
        self._events = EventSequencer()

    def stream_started(self, message: str) -> str:
        return self._line(
            StepperStreamStartedOutboundEvent, StepperStreamStartedOutboundEventDTO(message=message)
        )

    def result(self, action: str, success: bool, message: str) -> str:
        return self._line(
            StepperPartialOutboundEvent,
            StepperPartialOutboundEventDTO(action=action, success=success, message=message),
        )

    def completed(self, message: str) -> str:
        return self._line(
            StepperCompletedOutboundEvent, StepperCompletedOutboundEventDTO(message=message)
        )

    def error(self, code: str, message: str, *, recoverable: bool = False) -> str:
        return self._line(
            ErrorEvent, ErrorEventDTO(code=code, message=message, recoverable=recoverable)
        )

    def heartbeat(self) -> str:
        return self._line(HeartbeatEvent, None)

    def _line(self, event_cls: type, payload: Any) -> str:  # noqa: ANN401
        return encode_ndjson(self._events.next(event_cls, payload)).decode("utf-8")
