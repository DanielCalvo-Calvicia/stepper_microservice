from abc import ABC, abstractmethod

from application.dtos.motor_command_outbound import MotorCommandOutboundDTO, MotorStatusOutboundDTO


class MotorDriverPort(ABC):
    """What the application needs from the motor hardware (or its simulation)."""

    @abstractmethod
    async def execute_movement(self, command: MotorCommandOutboundDTO) -> MotorStatusOutboundDTO:
        """Move one motor and return when the movement ended (or was stopped)."""

    @abstractmethod
    async def emergency_stop(self, stepper_id: str) -> MotorStatusOutboundDTO:
        """Immediately halt the movement of one motor."""

    @abstractmethod
    async def cleanup(self) -> MotorStatusOutboundDTO:
        """Release the hardware resources."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if the driver initialized well enough to attempt a movement. No pulse is sent."""
