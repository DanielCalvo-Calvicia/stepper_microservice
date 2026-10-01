"""HTTP inbound adapter: decode -> call the inbound port -> encode. No business rules."""

from collections.abc import AsyncGenerator

from contracts.api.microservices.common.availability import AvailabilityResponse
from contracts.api.microservices.common.health_check import HealthCheckResponse
from contracts.api.microservices.stepper.batch import StepperBatchResult
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from shared_logging import get_logger
from starlette.requests import ClientDisconnect

from application.dtos.move_command_inbound import MoveCommandInboundDTO
from application.ports.inbound.stepper_control_port import StepperControlPort
from infrastructure.inbound.http.http_envelope import failure, success
from infrastructure.inbound.http.ndjson_command_decoder import NdjsonInputError, commands_from_body
from infrastructure.inbound.http.ndjson_events import NdjsonEventStream
from infrastructure.inbound.http.request_body_safe_streaming_response import (
    RequestBodySafeStreamingResponse,
)

logger = get_logger(__name__)


class StepperHandler:
    def __init__(self, port: StepperControlPort) -> None:
        self._port = port
        self.router = APIRouter()
        add = self.router.add_api_route
        add("/health", self.handle_health, methods=["GET"], tags=["Health"])
        add("/available", self.handle_available, methods=["GET"], tags=["Health"])
        add("/control/{stepper_id}/rotate", self.handle_rotate, methods=["POST"], tags=["Control"])
        add("/control/{stepper_id}/steps", self.handle_steps, methods=["POST"], tags=["Control"])
        add("/control/{stepper_id}/stop", self.handle_stop, methods=["POST"], tags=["Control"])
        add(
            "/process/stream/{stepper_id}/set",
            self.handle_set_stream,
            methods=["POST"],
            tags=["Control"],
            response_model=None,
        )

    async def handle_health(self) -> JSONResponse:
        return success(
            "health_check", "Stepper microservice is healthy", HealthCheckResponse(healthy=True)
        )

    async def handle_available(self) -> JSONResponse:
        available = self._port.is_available()
        reason = None if available else "the motor driver did not initialize"
        return success(
            "check_availability",
            "Availability checked successfully",
            AvailabilityResponse(is_available=available, reason=reason),
        )

    async def handle_rotate(
        self, stepper_id: str, rotations: float, rpm: float = 0.0, direction: str = "forward"
    ) -> JSONResponse:
        # rotate: rotations = full revolutions, rpm = rotational speed (the command's value/speed).
        return await self._control(
            "rotate", MoveCommandInboundDTO(stepper_id, "rotate", rotations, rpm, direction)
        )

    async def handle_steps(
        self, stepper_id: str, value: float, speed: float = 0.0, direction: str = "forward"
    ) -> JSONResponse:
        return await self._control(
            "steps", MoveCommandInboundDTO(stepper_id, "steps", value, speed, direction)
        )

    async def handle_stop(self, stepper_id: str) -> JSONResponse:
        return await self._control("stop", MoveCommandInboundDTO(stepper_id, "stop"))

    async def _control(self, action: str, command: MoveCommandInboundDTO) -> JSONResponse:
        try:
            result = await self._port.execute(command)
        except Exception as error:
            return failure(action, f"Failed to {action}", error)
        return success(
            action,
            result.message,
            StepperBatchResult(success=result.success, message=result.message),
        )

    async def handle_set_stream(self, request: Request, stepper_id: str) -> Response:
        """Accept a live stream of motor commands (``STEPPER_INBOUND`` events) and answer, as they
        run, with ``STEPPER_OUTBOUND`` events: ``stream_started``, one ``partial`` result per
        command, then ``completed`` (or ``error``)."""
        try:
            self._port.ensure_stepper(stepper_id)
        except Exception as error:
            return failure("set_stream", "Failed to set stream", error)
        return RequestBodySafeStreamingResponse(
            self._response_events(request, stepper_id),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"},
        )

    async def _response_events(
        self, request: Request, stepper_id: str
    ) -> AsyncGenerator[str, None]:
        events = NdjsonEventStream()
        yield events.stream_started(f"Command stream open for {stepper_id}.")
        commands = commands_from_body(request.stream(), stepper_id)
        failed = False
        count = 0
        try:
            async for result in self._port.run_commands(stepper_id, commands):
                count += 1
                yield events.result(result.action, result.success, result.message)
                failed = failed or not result.success
        except NdjsonInputError as error:
            logger.warning("Command stream rejected", stepper_id=stepper_id, error=error)
            await self._stop_quietly(stepper_id)
            yield events.error("invalid_stream", str(error))
            return
        except ClientDisconnect:
            logger.info("Command stream disconnected", stepper_id=stepper_id)
            await self._stop_quietly(stepper_id)
            return
        except Exception as error:
            logger.exception("Command stream failed", stepper_id=stepper_id)
            await self._stop_quietly(stepper_id)
            yield events.error("stream_failed", str(error))
            return
        yield events.completed(
            f"Stopped after a failed command ({count} commands run)."
            if failed
            else f"Stream completed ({count} commands run)."
        )

    async def _stop_quietly(self, stepper_id: str) -> None:
        """A stream that ends badly must not leave the motor running."""
        try:
            await self._port.execute(MoveCommandInboundDTO(stepper_id, "stop"))
        except Exception:
            logger.exception(
                "Emergency stop after a failed stream also failed", stepper_id=stepper_id
            )
