import asyncio
from collections.abc import AsyncIterator, Sequence

from shared_logging import get_logger

from application.dtos.command_result_outbound import CommandResultOutboundDTO
from application.dtos.motor_command_outbound import MotorCommandOutboundDTO
from application.dtos.move_command_inbound import MoveCommandInboundDTO
from application.errors import ApplicationError, MotorFailed, StepperBusy, UnknownStepper
from application.ports.inbound.stepper_control_port import StepperControlPort
from application.ports.outbound.motor_driver_port import MotorDriverPort
from domain.errors import InvalidMovement
from domain.operations.conversion import movement_for

logger = get_logger(__name__)


class StepperService(StepperControlPort):
    """Orchestrates the motor use cases. The unit conversions and validations live in the domain."""

    def __init__(
        self,
        driver: MotorDriverPort,
        stepper_ids: Sequence[str],
        default_max_speed: float = 1000.0,
        steps_per_revolution: int = 400,
        name: str = "Stepper",
    ) -> None:
        self.name = name
        self._driver = driver
        self._stepper_ids = tuple(stepper_ids)
        self._default_max_speed = default_max_speed
        # Number of STEP pulses for one full shaft revolution (full steps x microsteps).
        self._steps_per_revolution = steps_per_revolution
        # One lock per motor: commands on the same motor never overlap.
        self._locks = {stepper_id: asyncio.Lock() for stepper_id in self._stepper_ids}
        logger.info(
            "StepperService initialized",
            steppers=list(self._stepper_ids),
            steps_per_revolution=steps_per_revolution,
        )

    def ensure_stepper(self, stepper_id: str) -> None:
        if stepper_id not in self._locks:
            raise UnknownStepper(
                f"Unknown stepper_id: {stepper_id}. Configured steppers: {list(self._stepper_ids)}"
            )

    async def execute(self, command: MoveCommandInboundDTO) -> CommandResultOutboundDTO:
        logger.info("Command received", stepper_id=command.stepper_id, action=command.action)
        self.ensure_stepper(command.stepper_id)

        if command.action == "stop":
            # An emergency stop bypasses the movement lock: it must interrupt at once.
            status = await self._driver.emergency_stop(command.stepper_id)
            if not status.success:
                raise MotorFailed(status.message)
            return CommandResultOutboundDTO(action="stop", success=True, message=status.message)

        movement = movement_for(
            command.action,
            command.value,
            command.speed,
            command.direction,
            self._steps_per_revolution,
            self._default_max_speed,
        )
        lock = self._locks[command.stepper_id]
        if lock.locked():
            raise StepperBusy(f"Stepper {command.stepper_id} is already busy moving.")
        async with lock:
            logger.info(
                "Executing movement",
                stepper_id=command.stepper_id,
                steps=movement.steps,
                speed_steps_per_second=movement.speed_steps_per_second,
                forward=movement.forward,
            )
            status = await self._driver.execute_movement(
                MotorCommandOutboundDTO(
                    stepper_id=command.stepper_id,
                    steps=movement.steps,
                    speed_steps_per_second=movement.speed_steps_per_second,
                    forward=movement.forward,
                )
            )
        if not status.success:
            raise MotorFailed(status.message)
        return CommandResultOutboundDTO(action=command.action, success=True, message=status.message)

    async def run_commands(
        self, stepper_id: str, commands: AsyncIterator[MoveCommandInboundDTO]
    ) -> AsyncIterator[CommandResultOutboundDTO]:
        self.ensure_stepper(stepper_id)
        async for command in commands:
            try:
                yield await self.execute(command)
            except (ApplicationError, InvalidMovement) as error:
                logger.warning(
                    "Stream command failed; the rest of the stream is ignored",
                    stepper_id=stepper_id,
                    action=command.action,
                    error=error,
                )
                yield CommandResultOutboundDTO(
                    action=command.action, success=False, message=str(error)
                )
                return

    async def stop_and_cleanup(self) -> None:
        logger.info("Cleanup requested; forwarding to the motor driver")
        status = await self._driver.cleanup()
        if not status.success:
            raise MotorFailed(status.message)

    def is_available(self) -> bool:
        return self._driver.is_available()
