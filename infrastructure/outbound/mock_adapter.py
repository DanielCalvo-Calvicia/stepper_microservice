import asyncio
import time
from typing import Any
from application.ports.adapter_outbound_port import AdapterOutboundPort
from application.dtos.adapter_outbound_dtos import InitOutboundAdapterDto, MotorCommandDto, MotorStatusDto
from runtime.logger import get_logger

logger = get_logger("infrastructure.outbound.mock")

class MockStepperAdapter(AdapterOutboundPort):
    def __init__(self, config: InitOutboundAdapterDto):
        self.config = config
        self.active_tasks: dict[str, asyncio.Task] = {}
        self.stop_events: dict[str, asyncio.Event] = {
            stepper_id: asyncio.Event() for stepper_id in config.steppers.keys()
        }
        logger.info("MockStepperAdapter initialized with %d steppers.", len(config.steppers))

    async def _simulate_movement(self, request: MotorCommandDto) -> MotorStatusDto:
        stop_event = self.stop_events.get(request.stepper_id)
        if not stop_event:
            return MotorStatusDto(success=False, message=f"Invalid stepper_id: {request.stepper_id}")
            
        stop_event.clear()
        
        # Calculate delay
        if request.speed_steps_per_sec <= 0:
            return MotorStatusDto(success=False, message="Speed must be greater than 0")
            
        delay_per_step = 1.0 / request.speed_steps_per_sec
        logger.info("Mock motor %s starting movement: %d steps @ %f steps/sec", request.stepper_id, request.steps, request.speed_steps_per_sec)

        steps_completed = 0
        for i in range(request.steps):
            if stop_event.is_set():
                logger.warning("Mock motor %s emergency stopped after %d steps.", request.stepper_id, steps_completed)
                return MotorStatusDto(success=True, message=f"Stopped early at {steps_completed}/{request.steps} steps.")
                
            await asyncio.sleep(delay_per_step)
            steps_completed += 1

        logger.info("Mock motor %s completed movement.", request.stepper_id)
        return MotorStatusDto(success=True, message=f"Successfully completed {request.steps} steps.")

    async def execute_movement(self, request: MotorCommandDto) -> MotorStatusDto:
        # Create a task to simulate the movement
        task = asyncio.create_task(self._simulate_movement(request))
        self.active_tasks[request.stepper_id] = task
        try:
            return await task
        except asyncio.CancelledError:
            return MotorStatusDto(success=False, message="Movement task was cancelled.")
        finally:
            if self.active_tasks.get(request.stepper_id) == task:
                del self.active_tasks[request.stepper_id]

    async def emergency_stop(self, stepper_id: str) -> MotorStatusDto:
        stop_event = self.stop_events.get(stepper_id)
        if stop_event:
            stop_event.set()
            logger.info("Emergency stop signal sent to mock motor %s", stepper_id)
            return MotorStatusDto(success=True, message="Stop signal dispatched.")
        return MotorStatusDto(success=False, message="Invalid stepper_id")

    async def cleanup(self) -> MotorStatusDto:
        logger.info("Cleaning up mock adapter resources.")
        for stepper_id, event in self.stop_events.items():
            event.set()
        # Wait briefly for tasks to complete
        await asyncio.sleep(0.1)
        return MotorStatusDto(success=True, message="Cleanup completed successfully.")
