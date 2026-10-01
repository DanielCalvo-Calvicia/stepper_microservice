"""The motor commands carried by a request body of Stepper inbound contract events (NDJSON)."""

from collections.abc import AsyncIterable, AsyncIterator, Iterator
from typing import Any

from contracts.stream.codec import NdjsonDecoder
from contracts.stream.common.base import BaseEvent, ContractViolation, EventType
from contracts.stream.schemas import STEPPER_INBOUND

from application.dtos.move_command_inbound import MoveCommandInboundDTO


class NdjsonInputError(ValueError):
    """A streamed NDJSON command request violates the input contract."""


class NdjsonCommandDecoder:
    """Stateful decoder of byte chunks into motor commands.

    The contract rules (sequence 1..n, ``stream_started`` first and only once, well-formed events)
    are enforced by the shared codec; this class only turns events into commands:

    * ``stream_started`` -> must name the stepper of the URL
    * ``partial``        -> one command (``rotate``, ``steps`` or ``stop``)
    * ``completed``      -> the sender is done
    * ``heartbeat``      -> nothing
    * ``error``          -> the sender failed, so the stream fails too
    """

    def __init__(self, stepper_id: str) -> None:
        self._decoder = NdjsonDecoder(STEPPER_INBOUND)
        self._stepper_id = stepper_id
        self.completed = False

    def feed(self, chunk: bytes) -> Iterator[MoveCommandInboundDTO]:
        try:
            for event in self._decoder.feed(chunk):
                yield from self._commands_of(event)
        except ContractViolation as error:
            raise NdjsonInputError(str(error)) from error

    def finish(self) -> Iterator[MoveCommandInboundDTO]:
        try:
            for event in self._decoder.finish():
                yield from self._commands_of(event)
        except ContractViolation as error:
            raise NdjsonInputError(str(error)) from error

    def _commands_of(self, event: BaseEvent[Any]) -> Iterator[MoveCommandInboundDTO]:
        if event.type is EventType.START_STREAM:
            if event.payload.stepper_id != self._stepper_id:
                raise NdjsonInputError(
                    f"stream_started names stepper {event.payload.stepper_id!r}, "
                    f"but the request is for {self._stepper_id!r}"
                )
        elif event.type is EventType.PARTIAL:
            yield _command_of(self._stepper_id, event.payload)
        elif event.type is EventType.COMPLETED:
            self.completed = True
        elif event.type is EventType.ERROR:
            raise NdjsonInputError(f"the sender failed: {event.payload.message}")


def _command_of(stepper_id: str, payload: Any) -> MoveCommandInboundDTO:  # noqa: ANN401
    if payload.action == "rotate":
        return MoveCommandInboundDTO(
            stepper_id,
            "rotate",
            value=payload.rotations,
            speed=payload.rpm,
            direction=payload.direction,
        )
    if payload.action == "steps":
        return MoveCommandInboundDTO(
            stepper_id,
            "steps",
            value=payload.steps,
            speed=payload.speed,
            direction=payload.direction,
        )
    return MoveCommandInboundDTO(stepper_id, payload.action, direction=payload.direction)


async def commands_from_body(
    body: AsyncIterable[bytes], stepper_id: str
) -> AsyncIterator[MoveCommandInboundDTO]:
    """The commands of a request body, as they arrive."""
    decoder = NdjsonCommandDecoder(stepper_id)
    async for chunk in body:
        if chunk:
            for command in decoder.feed(chunk):
                yield command
    for command in decoder.finish():
        yield command
