import asyncio
from typing import Any
from application.ports.service_port import StepperServicePort
from application.ports.adapter_outbound_port import AdapterOutboundPort
from application.dtos.services_dtos import ServiceBatchRequestDto, ServiceBatchResponseDto, ServiceStreamRequestDto, ServiceStreamResponseDto
from application.dtos.mapper.service_to_adapter_outbound import map_service_to_outbound_motor_command
from application.dtos.mapper.adapter_outbound_to_service import map_outbound_to_service_response
from runtime.logger import get_logger

logger = get_logger("application.service")

class StepperService(StepperServicePort):
    def __init__(self, outbound_port: AdapterOutboundPort, steppers_config: dict[str, Any], default_max_speed: float = 1000.0):
        self.outbound_port = outbound_port
        self.steppers_config = steppers_config
        self.default_max_speed = default_max_speed
        # Lock per stepper to prevent concurrent commands interfering
        self.locks: dict[str, asyncio.Lock] = {stepper_id: asyncio.Lock() for stepper_id in steppers_config.keys()}
        logger.info("StepperService initialized for steppers: %s", list(steppers_config.keys()))

    def _validate_stepper(self, stepper_id: str) -> str | None:
        if stepper_id not in self.steppers_config:
            return f"Unknown stepper_id: {stepper_id}. Configured steppers: {list(self.steppers_config.keys())}"
        return None

    def _validate_speed(self, speed: float) -> tuple[float, str | None]:
        if speed < 0:
            return speed, "Speed must be a positive value."
        # If speed is 0 or unprovided, use default max speed.
        if speed == 0.0:
            return self.default_max_speed, None
        return speed, None

    def _convert_rotate_to_steps(self, degrees: float) -> int:
        """
        Convert degrees to steps.
        Assuming standard 1.8 degree per step motor -> 200 steps per revolution.
        If microstepping is used (e.g. 16 microsteps), this calculation must be updated.
        We'll assume a configurable steps_per_revolution or hardcode 200 for now.
        """
        steps_per_rev = 200 # Standard full steps. 
        steps = int(abs(degrees) / 360.0 * steps_per_rev)
        return steps

    async def execute_batch(self, request: ServiceBatchRequestDto) -> ServiceBatchResponseDto:
        logger.info("Service received batch request for stepper %s: action=%s", request.stepper_id, request.action)
        
        error = self._validate_stepper(request.stepper_id)
        if error:
            return ServiceBatchResponseDto(success=False, message=error)

        if request.action == "stop":
            # For emergency stops, we bypass the movement lock to interrupt immediately.
            outbound_res = await self.outbound_port.emergency_stop(request.stepper_id)
            return map_outbound_to_service_response(outbound_res)

        # Validate speed and calculate steps
        speed, speed_err = self._validate_speed(request.speed)
        if speed_err:
            return ServiceBatchResponseDto(success=False, message=speed_err)

        actual_steps = 0
        if request.action == "rotate":
            actual_steps = self._convert_rotate_to_steps(request.value)
        elif request.action == "steps":
            actual_steps = int(abs(request.value))
        else:
            return ServiceBatchResponseDto(success=False, message=f"Unsupported action: {request.action}")

        # Execute physical movement
        outbound_command = map_service_to_outbound_motor_command(request, actual_steps, speed)
        
        lock = self.locks[request.stepper_id]
        if lock.locked():
            return ServiceBatchResponseDto(success=False, message=f"Stepper {request.stepper_id} is already busy moving.")

        async with lock:
            outbound_res = await self.outbound_port.execute_movement(outbound_command)
        
        return map_outbound_to_service_response(outbound_res)

    async def execute_stream(self, request: ServiceStreamRequestDto) -> ServiceStreamResponseDto:
        """
        Process a stream of events. We will start a background task or iterate here.
        For simplicity, since the stream is fully managed via async iterator by the inbound adapter,
        we just consume it within a lock to prevent other operations from interfering.
        """
        logger.info("Service received stream request for stepper %s", request.stepper_id)
        
        error = self._validate_stepper(request.stepper_id)
        if error:
            res = ServiceStreamResponseDto(success=False, message=error)
            if request.setup_future and not request.setup_future.done():
                request.setup_future.set_result(res)
            return res

        lock = self.locks[request.stepper_id]
        if lock.locked():
            res = ServiceStreamResponseDto(success=False, message=f"Stepper {request.stepper_id} is busy.")
            if request.setup_future and not request.setup_future.done():
                request.setup_future.set_result(res)
            return res

        # Setup successful
        success_res = ServiceStreamResponseDto(success=True, message=f"Stream session started for {request.stepper_id}.")
        if request.setup_future and not request.setup_future.done():
            request.setup_future.set_result(success_res)

        # Consume the stream within the lock
        async with lock:
            try:
                async for event in request.command_stream:
                    # In a real implementation, parse event and update speed/steps dynamically
                    # Example: if event["action"] == "stop", we call emergency_stop and break.
                    pass
            except Exception as e:
                logger.error("Error processing stream for %s: %s", request.stepper_id, e)
                await self.outbound_port.emergency_stop(request.stepper_id)
                return ServiceStreamResponseDto(success=False, message=f"Stream error: {e}")

        # Stream naturally ended
        return ServiceStreamResponseDto(success=True, message="Stream session completed successfully.")

    async def stop_and_cleanup(self) -> ServiceBatchResponseDto:
        logger.info("Service cleanup requested. Forwarding to hardware adapter.")
        outbound_res = await self.outbound_port.cleanup()
        return map_outbound_to_service_response(outbound_res)
