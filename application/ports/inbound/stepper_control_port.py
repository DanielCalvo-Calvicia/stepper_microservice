from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from application.dtos.command_result_outbound import CommandResultOutboundDTO
from application.dtos.move_command_inbound import MoveCommandInboundDTO


class StepperControlPort(ABC):
    """What the outside world may ask of the application."""

    @abstractmethod
    async def execute(self, command: MoveCommandInboundDTO) -> CommandResultOutboundDTO:
        """Run one command. Raises UnknownStepper, StepperBusy, InvalidMovement or MotorFailed."""

    @abstractmethod
    def ensure_stepper(self, stepper_id: str) -> None:
        """Raises UnknownStepper unless ``stepper_id`` is a configured motor."""

    @abstractmethod
    def run_commands(
        self, stepper_id: str, commands: AsyncIterator[MoveCommandInboundDTO]
    ) -> AsyncIterator[CommandResultOutboundDTO]:
        """Run the commands of a stream one after the other, yielding the result of each.

        A command that fails is reported as a result with ``success=False`` and ends the stream:
        going on would leave the arm somewhere the sequence did not intend.
        """

    @abstractmethod
    async def stop_and_cleanup(self) -> None:
        """Stop every motor and release the device."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if the motor driver is ready to accept commands."""
