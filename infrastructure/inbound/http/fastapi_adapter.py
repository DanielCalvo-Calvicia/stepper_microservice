import asyncio
import json
import base64
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from starlette.requests import ClientDisconnect

from contracts.api.common.envelope import ApiEnvelope
from contracts.api.microservices.common.availability import AvailabilityResponse
from contracts.api.microservices.common.health_check import HealthCheckResponse
from contracts.api.microservices.stepper.batch import StepperBatchResult

from application.ports.adapter_inbound_port import AdapterInboundPort
from application.ports.service_port import StepperServicePort

from application.dtos.adapter_inbound_dtos import (
    InitInboundAdapterDto,
    StepperBatchRequestDto,
    StepperStreamRequestDto,
)
from application.dtos.mapper.adapter_inbound_to_service import (
    map_inbound_to_service_batch_request,
    map_inbound_to_service_stream_request
)
from application.dtos.mapper.service_to_adapter_inbound import (
    map_service_to_inbound_batch_response,
    map_service_to_inbound_stream_response
)
from shared_logging import get_logger

logger = get_logger("infrastructure.inbound")

class NdjsonInputError(ValueError):
    """Raised when a streamed NDJSON request violates the input contract."""

class NdjsonEventStream:
    """Build newline-delimited JSON protocol events with stream-local sequencing."""
    def __init__(self) -> None:
        self._sequence = 0

    def line(self, event_type: str, payload: dict[str, Any]) -> str:
        self._sequence += 1
        event = {
            "type": event_type,
            "sequence": self._sequence,
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "payload": payload,
        }
        return json.dumps(event, separators=(",", ":")) + "\n"

class RequestBodySafeStreamingResponse(Response):
    """
    Stream response bytes without concurrently reading the ASGI receive channel.
    """
    def __init__(
        self,
        content: AsyncGenerator[str, None],
        media_type: str,
        headers: dict[str, str] | None = None,
        status_code: int = status.HTTP_200_OK,
    ) -> None:
        super().__init__(content=None, status_code=status_code, headers=headers, media_type=media_type)
        self.body_iterator = content
        self.raw_headers = [
            (name, value)
            for name, value in self.raw_headers
            if name.lower() != b"content-length"
        ]

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        async for chunk in self.body_iterator:
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk.encode(self.charset),
                    "more_body": True,
                }
            )
        await send({"type": "http.response.body", "body": b"", "more_body": False})


class FastApiAdapter(AdapterInboundPort):
    def __init__(self, service_port: StepperServicePort, app: FastAPI, config: InitInboundAdapterDto):
        self.service_port = service_port
        self.app = app
        self.config = config
        
        logger.info("Initializing FastApiAdapter", allow_origins=config.allow_origins)
        self.register_routes(self.app)

    def register_routes(self, app: FastAPI) -> None:
        logger.info("Registering FastAPI inbound routes.")

        @app.get("/health", tags=["Health"])
        async def health_check() -> JSONResponse:
            envelope = ApiEnvelope.success("health_check", "Stepper microservice is healthy", HealthCheckResponse(healthy=True))
            return JSONResponse(status_code=status.HTTP_200_OK, content=envelope.to_dict())

        @app.get("/available", tags=["Health"])
        async def available() -> JSONResponse:
            is_available = self.service_port.is_available()
            reason = None if is_available else "the motor driver did not initialize"
            envelope = ApiEnvelope.success(
                "check_availability", "Availability checked successfully",
                AvailabilityResponse(is_available=is_available, reason=reason),
            )
            return JSONResponse(status_code=status.HTTP_200_OK, content=envelope.to_dict())

        @app.post("/control/{stepper_id}/rotate", tags=["Control"])
        async def rotate_stepper(stepper_id: str, rotations: float, rpm: float = 0.0, direction: str = "forward") -> JSONResponse:
            # rotate: rotations = full revolutions, rpm = rotational speed.
            # These map onto the generic batch DTO fields value/speed respectively.
            inbound_req = StepperBatchRequestDto(stepper_id=stepper_id, action="rotate", value=rotations, speed=rpm, direction=direction)
            res = await self.process_batch(inbound_req)
            return self._batch_response("rotate", res)

        @app.post("/control/{stepper_id}/steps", tags=["Control"])
        async def steps_stepper(stepper_id: str, value: float, speed: float = 0.0, direction: str = "forward") -> JSONResponse:
            inbound_req = StepperBatchRequestDto(stepper_id=stepper_id, action="steps", value=value, speed=speed, direction=direction)
            res = await self.process_batch(inbound_req)
            return self._batch_response("steps", res)

        @app.post("/control/{stepper_id}/stop", tags=["Control"])
        async def stop_stepper(stepper_id: str) -> JSONResponse:
            inbound_req = StepperBatchRequestDto(stepper_id=stepper_id, action="stop")
            res = await self.process_batch(inbound_req)
            return self._batch_response("stop", res)

        @app.post("/process/stream/{stepper_id}/set", tags=["Control"])
        async def set_stream_http(request: Request, stepper_id: str) -> Response:
            event_stream = NdjsonEventStream()

            async def ndjson_command_generator() -> AsyncGenerator[dict[str, Any], None]:
                buffer = b""
                try:
                    async for chunk in request.stream():
                        if not chunk: continue
                        buffer += chunk
                        while b"\\n" in buffer:
                            line_bytes, buffer = buffer.split(b"\\n", 1)
                            line = line_bytes.decode("utf-8").strip()
                            if not line: continue
                            
                            try:
                                event = json.loads(line)
                                # Basic validation
                                if "type" in event and "payload" in event:
                                    yield event
                            except json.JSONDecodeError:
                                pass # Or raise error
                except ClientDisconnect:
                    logger.info("HTTP Stream disconnected.")
                except Exception as e:
                    logger.error("Error reading stream", e=e)
                    raise

            setup_future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
            inbound_request = StepperStreamRequestDto(
                stepper_id=stepper_id,
                command_stream=ndjson_command_generator(),
                setup_future=setup_future
            )
            
            stream_task = asyncio.create_task(self.process_stream(inbound_request))

            done, _ = await asyncio.wait(
                {setup_future, stream_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            
            if setup_future in done:
                setup_response = setup_future.result()
            else:
                try:
                    setup_response = await stream_task
                except Exception as e:
                    return JSONResponse(status_code=500, content={"message": str(e)})

            if not setup_response.success:
                return JSONResponse(status_code=400, content={"message": setup_response.message})

            async def response_stream() -> AsyncGenerator[str, None]:
                yield event_stream.line("stream_started", {"message": setup_response.message})
                try:
                    while not stream_task.done():
                        # Heartbeat while we process the stream
                        yield event_stream.line("heartbeat", {})
                        await asyncio.sleep(5.0) 
                    
                    response = await stream_task
                    if not response.success:
                        yield event_stream.line("error", {"message": response.message})
                    else:
                        yield event_stream.line("completed", {"message": response.message})
                except Exception as e:
                    yield event_stream.line("error", {"message": str(e)})

            return RequestBodySafeStreamingResponse(
                response_stream(),
                media_type="application/x-ndjson"
            )

    @property
    def get_app(self) -> Any:
        return self.app

    @staticmethod
    def _batch_response(action: str, res) -> JSONResponse:
        status_code = status.HTTP_200_OK if res.success else status.HTTP_400_BAD_REQUEST
        data = StepperBatchResult(success=res.success, message=res.message)
        make = ApiEnvelope.success if res.success else (
            lambda a, m, d: ApiEnvelope.failure(a, m, status_code, d))
        envelope = make(action, res.message, data)
        return JSONResponse(status_code=status_code, content=envelope.to_dict())

    async def process_batch(self, request: StepperBatchRequestDto):
        service_req = map_inbound_to_service_batch_request(request)
        service_res = await self.service_port.execute_batch(service_req)
        return map_service_to_inbound_batch_response(service_res)

    async def process_stream(self, request: StepperStreamRequestDto):
        service_req = map_inbound_to_service_stream_request(request)
        service_res = await self.service_port.execute_stream(service_req)
        return map_service_to_inbound_stream_response(service_res)
