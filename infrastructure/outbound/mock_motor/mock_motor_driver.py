import asyncio
from collections.abc import Mapping

from shared_logging import get_logger

from application.dtos.motor_command_outbound import MotorCommandOutboundDTO, MotorStatusOutboundDTO
from application.ports.outbound.motor_driver_port import MotorDriverPort
from infrastructure.config.stepper_config import StepperPins

logger = get_logger(__name__)


class MockMotorDriver(MotorDriverPort):
    """Simulates the motors: each step is a sleep. Used on machines without GPIO and in tests."""

    def __init__(self, steppers: Mapping[str, StepperPins]) -> None:
        self._stop_events = {stepper_id: asyncio.Event() for stepper_id in steppers}
        logger.info("MockMotorDriver initialized", steppers_count=len(steppers))

    async def execute_movement(self, command: MotorCommandOutboundDTO) -> MotorStatusOutboundDTO:
        stop_event = self._stop_events.get(command.stepper_id)
        if stop_event is None:
            return MotorStatusOutboundDTO(False, f"Invalid stepper_id: {command.stepper_id}")
        if command.speed_steps_per_second <= 0:
            return MotorStatusOutboundDTO(False, "Speed must be greater than 0")

        stop_event.clear()
        delay_per_step = 1.0 / command.speed_steps_per_second
        logger.info(
            "Mock motor starting movement",
            stepper_id=command.stepper_id,
            steps=command.steps,
            speed_steps_per_second=command.speed_steps_per_second,
        )
        steps_completed = 0
        for _ in range(command.steps):
            if stop_event.is_set():
                logger.warning(
                    "Mock motor emergency stopped",
                    stepper_id=command.stepper_id,
                    steps_completed=steps_completed,
                )
                return MotorStatusOutboundDTO(
                    True, f"Stopped early at {steps_completed}/{command.steps} steps."
                )
            await asyncio.sleep(delay_per_step)
            steps_completed += 1
        logger.info("Mock motor completed movement", stepper_id=command.stepper_id)
        return MotorStatusOutboundDTO(True, f"Successfully completed {command.steps} steps.")

    async def emergency_stop(self, stepper_id: str) -> MotorStatusOutboundDTO:
        stop_event = self._stop_events.get(stepper_id)
        if stop_event is None:
            return MotorStatusOutboundDTO(False, "Invalid stepper_id")
        stop_event.set()
        logger.info("Emergency stop signal sent to mock motor", stepper_id=stepper_id)
        return MotorStatusOutboundDTO(True, "Stop signal dispatched.")

    async def cleanup(self) -> MotorStatusOutboundDTO:
        logger.info("Cleaning up mock driver resources")
        for event in self._stop_events.values():
            event.set()
        await asyncio.sleep(0.1)  # let a running simulated movement notice the stop
        return MotorStatusOutboundDTO(True, "Cleanup completed successfully.")

    def is_available(self) -> bool:
        return True
